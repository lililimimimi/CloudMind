
# 作用：成本优化专员 Agent
# 通过 MCP 工具查询实例监控数据，给出降本建议
# 在 FinOps 工作流中接收 billing_agent 传来的实例数据
# 再调用 analyze_instance_usage 工具查监控数据做分析

import os
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from core.workflow.state import AgentState
from agents.billing_agent import UserIdInjector  # 复用 billing_agent 里的拦截器
from config.mcp_runtime import get_cloud_platform_mcp_connections

load_dotenv()


class FinOpsAgentNode:
    """
    成本优化专员 Agent。

    工作流程：
    1. 从对话历史或 metadata 里找实例 ID
    2. 调用 query_user_instances 获取实例列表（找不到时）
    3. 调用 analyze_instance_usage 查监控数据
    4. 根据监控数据给出降本建议
    """

    def __init__(self):
        self.llm = ChatOpenAI(
            api_key=os.getenv("SILICONFLOW_API_KEY"),
            base_url=os.getenv("SILICONFLOW_BASE_URL"),
            model=os.getenv("MODEL", "deepseek-ai/DeepSeek-V3"),
            temperature=0.1,
        )

        self.mcp_connections = get_cloud_platform_mcp_connections()

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        print("💡 [FinOpsAgent] 开始进行成本优化分析...")

        metadata = state.get("metadata", {})
        instance_data = metadata.get("instance_data", "")
        user_id = state.get("user_id", "unknown")
        config = {"configurable": {"user_id": user_id}}

        print(f"[FinOpsAgent] 实例数据：{instance_data[:80] if instance_data else '无'}...")

        system_prompt = f"""你是一个专业的云上FinOps成本优化专家。
    你刚刚接手了 BillingAgent 传递过来的实例数据。

    已获取到的实例数据：
    {instance_data if instance_data else "暂无，请先调用工具查询"}

    你的任务：
    1. 从上面的实例数据中提取实例ID
    2. 如果没有实例数据，先调用 query_user_instances 获取实例列表
    3. 优先选择 Running 状态的 ECS 实例进行分析
    4. 必须调用 analyze_instance_usage 工具查询每个实例的监控数据
    5. 根据监控数据给出具体的降本建议

    注意：
    - 调用工具时 user_id 传 "auto"，系统会自动注入真实用户ID
    - 严禁编造数据，必须基于工具返回结果
    - 用纯中文回答，不要用 markdown 格式，禁止用 ** 加粗，禁止用 ### 标题
    - 用普通文字和数字编号就好
    """

        client = MultiServerMCPClient(
            connections=self.mcp_connections,
            tool_interceptors=[UserIdInjector()]
        )

        all_tools = await client.get_tools()
        target_tools = {"query_user_instances", "analyze_instance_usage"}
        tools = [t for t in all_tools if t.name in target_tools]

        print(f"[FinOpsAgent] 可用工具：{[t.name for t in tools]}")

        inner_agent = create_react_agent(
            model=self.llm,
            tools=tools,
            prompt=system_prompt,
        )

        result = await inner_agent.ainvoke(
            {"messages": state["messages"]},
            config=config
        )

        final_message = result["messages"][-1]
        print(f"[FinOpsAgent] 回复：{final_message.content[:50]}...")

        return {
            "messages": [final_message],
            "next_agent": ""
        }


# 全局实例
finops_agent_node = FinOpsAgentNode()


async def finops_node(state: AgentState) -> Dict[str, Any]:
    return await finops_agent_node(state)
