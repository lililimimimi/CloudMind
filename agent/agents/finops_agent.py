
# 作用：成本优化专员 Agent
# 通过 MCP 工具查询实例监控数据，给出降本建议
# 在 FinOps 工作流中接收 billing_agent 传来的实例数据
# 再调用 analyze_instance_usage 工具查监控数据做分析

import os
import json
from typing import Dict, Any, Callable, Awaitable
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.interceptors import (
    ToolCallInterceptor,
    MCPToolCallRequest,
    MCPToolCallResult
)
from langgraph.prebuilt import create_react_agent

from core.workflow.state import AgentState
from agents.billing_agent import UserIdInjector  # 复用 billing_agent 里的拦截器

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

        # 读取 MCP 服务配置
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config', 'mcp_servers.json'
        )
        with open(config_path, 'r', encoding='utf-8') as f:
            self.mcp_config = json.load(f)

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        """
        LangGraph 节点调用入口。
        读取实例数据，分析成本，给出优化建议。
        """

        print("💡 [FinOpsAgent] 开始进行成本优化分析...")

        # 从 metadata 取出 billing_agent 查到的实例数据
        metadata = state.get("metadata", {})
        instance_data = metadata.get("instance_data", "")
        user_id = state.get("user_id", "unknown")

        print(f"[FinOpsAgent] 实例数据：{instance_data[:80] if instance_data else '无'}...")

        # 构建系统提示词
        system_prompt = f"""你是 CloudMind 云平台的成本优化专员（FinOps）。
你刚刚接手了 BillingAgent 传递过来的实例数据。

已获取到的实例数据：
{instance_data if instance_data else "暂无实例数据，请先调用 query_user_instances 获取"}

你的任务：
1. 仔细阅读上下文中的对话历史，优先提取用户想要优化的实例ID
2. 如果上下文中没有实例ID，先调用 query_user_instances 获取实例列表
   优先选择 Running 状态的 ECS 实例继续分析
   如果有多台实例，先给出清单并建议用户指定目标
3. 调用 analyze_instance_usage 工具获取目标实例近期 CPU、内存等监控数据
4. 根据监控数据分析该实例是否存在资源闲置（RESOURCES_IDLE）
5. 以云架构师的口吻给用户提出降本增效建议：
   - CPU 长期极低 → 建议降配规格
   - 估算每月可节省的费用比例
   - 语气专业诚恳，完全站在为用户省钱的角度


降本建议维度：
- CPU 长期低于 10% + 内存低于 30% → 资源闲置，建议降配规格
- 实例状态为 Stopped → 建议释放或转换计费方式
- 按量付费长期运行 → 建议转包年包月节省费用
- 估算每月可节省的费用比例

注意事项：
- 调用工具时 user_id 传 "auto"，系统会自动注入真实用户ID
- 严禁编造实例ID、监控指标和费用数据，必须基于工具返回结果
- 禁止说工具坏了或接口异常
- 用纯中文回答，不要用 markdown 格式
- 语气专业诚恳，完全站在为用户省钱的角度"""

        # 不用 async with，直接创建 client
        client = MultiServerMCPClient(
            connections=self.mcp_config.get("mcpServers", {}),
            tool_interceptors=[UserIdInjector()]  # 复用安全拦截器
        )

        all_tools = await client.get_tools()

        # FinOps 需要两个工具
        # query_user_instances：找不到实例时先查列表
        # analyze_instance_usage：查监控数据
        target_tools = ["query_user_instances", "analyze_instance_usage"]
        tools = [t for t in all_tools if t.name in target_tools]

        print(f"[FinOpsAgent] 可用工具：{[t.name for t in tools]}")

        inner_agent = create_react_agent(
            model=self.llm,
            tools=tools,
            prompt=system_prompt,
        )

        # 注入 user_id
        config = {"configurable": {"user_id": user_id}}

        result = await inner_agent.ainvoke(
            {"messages": state["messages"]},
            config=config
        )

        final_message = result["messages"][-1]
        print(f"[FinOpsAgent] 回复：{final_message.content[:50]}...")

        # 流程结束，清空 next_agent
        return {
            "messages": [final_message],
            "next_agent": ""
        }


# 全局实例
finops_agent_node = FinOpsAgentNode()


async def finops_node(state: AgentState) -> Dict[str, Any]:
    return await finops_agent_node(state)