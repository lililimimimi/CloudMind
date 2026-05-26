
# 作用：账单查询专员 Agent
# 通过 MCP 工具查询用户真实的订单、实例数据

import os
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from core.workflow.state import AgentState
from config.mcp_runtime import get_cloud_platform_mcp_connections

load_dotenv()


# -------------------------------------------------------
# UserIdInjector 安全拦截器
# 暂时简化，等确认工具调用成功后再加回来
# -------------------------------------------------------
class UserIdInjector:
    """
    MCP 工具调用拦截器。
    强制把真实 user_id 注入到工具参数里。
    """
    async def __call__(self, request, handler):
        user_id = None
        if hasattr(request, 'runtime') and hasattr(request.runtime, 'config'):
            config = request.runtime.config
            user_id = config.get("configurable", {}).get("user_id")

        if user_id:
            new_args = dict(request.args)
            new_args["user_id"] = user_id
            print(f"🔒 [安全拦截] 注入 user_id={user_id} 到工具 {request.name}")
            new_request = request.override(args=new_args)
            return await handler(new_request)

        return await handler(request)


# -------------------------------------------------------
# BillingAgentNode
# -------------------------------------------------------
class BillingAgentNode:
    """
    账单查询专员 Agent。
    通过 MCP 工具查询用户真实数据。
    """

    def __init__(self):
        self.llm = ChatOpenAI(
            api_key=os.getenv("SILICONFLOW_API_KEY"),
            base_url=os.getenv("SILICONFLOW_BASE_URL"),
            model=os.getenv("MODEL", "Qwen/Qwen2.5-72B-Instruct"),
            temperature=0,
        )

        self.mcp_connections = get_cloud_platform_mcp_connections()

        # 普通账单查询提示词
        self.system_prompt = """你是 CloudMind 云平台的账单查询专员。

重要规则：
你必须调用工具查询真实数据，禁止编造任何数据。
没有调用工具就没有数据，不能凭空回答。

工具使用规则：
- 用户询问订单、账单 → 必须调用 query_user_orders 工具
- 用户询问实例、服务器 → 必须调用 query_user_instances 工具
- 调用工具时 user_id 参数传 "auto"

数据来源规则：
- 只能使用工具返回的真实数据回答
- 工具没有返回的数据一律不能出现在回答中
- 禁止编造订单号、金额、时间等任何数据

输出规则：
- 用纯中文回答
- 不要用 markdown 格式"""

        # FinOps 工作流提示词
        self.finops_system_prompt = """你是 CloudMind 云平台的账单查询专员。
你的任务是查询用户当前所有实例信息，为后续成本优化分析做准备。

你必须立即调用 query_user_instances 工具，不要说"我将查询"或"请稍等"。
直接调用工具，把结果完整返回。
调用工具时 user_id 参数传 "auto"。"""

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        metadata = state.get("metadata", {})
        is_finops = metadata.get("is_finops_workflow", False)
        user_id = state.get("user_id", "unknown")

        config = {"configurable": {"user_id": user_id}}

        if is_finops:
            print("💡 [BillingAgent] FinOps 工作流，查询用户实例数据...")
            prompt = self.finops_system_prompt
            target_tools = {"query_user_instances"}
        else:
            print("💡 [BillingAgent] 普通账单查询...")
            prompt = self.system_prompt
            target_tools = {"query_user_orders", "query_user_instances"}

        # 用 connections 参数，和原项目一样
        client = MultiServerMCPClient(
            connections=self.mcp_connections,
            tool_interceptors=[UserIdInjector()]
        )

        all_tools = await client.get_tools()
        tools = [t for t in all_tools if t.name in target_tools]

        print(f"[BillingAgent] 可用工具：{[t.name for t in tools]}")

        # prompt 直接传给 create_react_agent，不用 SystemMessage
        inner_agent = create_react_agent(
            model=self.llm,
            tools=tools,
            prompt=prompt,
        )

        result = await inner_agent.ainvoke(
            {"messages": state["messages"]},
            config=config
        )

        final_message = result["messages"][-1]
        print(f"[BillingAgent] 回复：{final_message.content[:50]}...")

        if is_finops:
            metadata["instance_data"] = final_message.content
            return {
                "messages": [final_message],
                "metadata": metadata,
            }

        return {"messages": [final_message]}


# 全局实例
billing_agent_node = BillingAgentNode()


async def billing_node(state: AgentState) -> Dict[str, Any]:
    return await billing_agent_node(state)
