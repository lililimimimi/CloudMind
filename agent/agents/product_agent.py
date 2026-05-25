# agent/agents/product_agent.py
# 作用：产品咨询专员 Agent
# 使用知识图谱工具查询产品结构化数据
# 后面还会接入 RAG 向量检索工具

import os
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from core.workflow.state import AgentState
from tools.graph_tool import query_knowledge_graph

load_dotenv()


class ProductAgentNode:
    """
    产品咨询专员 Agent。
    负责回答云产品相关问题：功能介绍、规格说明、概念解释、操作指南。
    使用知识图谱查询结构化数据，后面接入 RAG 查询文档知识。
    """

    def __init__(self):
        self.llm = ChatOpenAI(
            api_key=os.getenv("SILICONFLOW_API_KEY"),
            base_url=os.getenv("SILICONFLOW_BASE_URL"),
            model=os.getenv("MODEL", "deepseek-ai/DeepSeek-V3"),
            temperature=0.1,
        )

        # 配备知识图谱工具
        # 后面加入 RAG 工具后这里再加
        self.tools = [query_knowledge_graph]

        self.system_prompt = """你是 CloudMind 云平台的产品咨询专员。
你可以通过工具查询云产品的详细信息。

工具使用规则：
- 用户询问实例规格、CPU、内存、网络等参数 → 调用 query_knowledge_graph
- 用户询问地域、可用区、支持哪些实例 → 调用 query_knowledge_graph
- 用户询问存储类型、计费规则 → 调用 query_knowledge_graph
- 一般性产品介绍可以直接回答，不需要调用工具

回答要求：
- 用纯中文回答
- 简洁专业
- 数据必须来自工具返回结果，不能编造参数
- 不要用 markdown 格式"""

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        """
        LangGraph 节点调用入口。
        """
        print("💡 [ProductAgent] 开始处理产品咨询请求...")

        inner_agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=self.system_prompt,
        )

        result = await inner_agent.ainvoke({
            "messages": state["messages"]
        })

        final_message = result["messages"][-1]
        print(f"[ProductAgent] 回复：{final_message.content[:50]}...")

        return {"messages": [final_message]}


# 全局实例
product_agent_node = ProductAgentNode()


async def product_node(state: AgentState) -> Dict[str, Any]:
    return await product_agent_node(state)