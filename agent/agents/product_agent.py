
# 作用：产品咨询专员 Agent

import os
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent

from core.workflow.state import AgentState

# 加载环境变量
load_dotenv()


class ProductAgentNode:
    """
    产品咨询专员 Agent。
    负责回答云产品相关问题：功能介绍、规格说明、概念解释、操作指南。
    封装成 class 的好处：llm 只初始化一次，节省资源。
    """

    def __init__(self):
        # 初始化 LangChain 客户端，只初始化一次
        self.llm = ChatOpenAI(
            api_key=os.getenv("SILICONFLOW_API_KEY"),
            base_url=os.getenv("SILICONFLOW_BASE_URL"),
            model=os.getenv("MODEL", "deepseek-ai/DeepSeek-V3"),
            temperature=0.1,  # 低随机性，让产品信息更准确
        )

        # 暂时没有工具，后面加入 RAG 和知识图谱
        self.tools = []

        # 产品专员的系统提示词
        self.system_prompt = """你是 CloudMind 云平台的产品咨询专员。
你只负责回答云产品相关的问题，包括：
- 云服务器 ECS 的配置、规格、功能介绍
- 各类云产品的使用说明和操作指南
- 产品概念解释

回答要求：
- 用纯中文回答
- 简洁专业，不超过300字
- 不要用 markdown 格式
- 不要用编号列表
- 如果不确定请如实告知，不要编造信息"""

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        """
        LangGraph 节点调用入口。
        使用 create_react_agent 让 Agent 自主决策。
        后面加了工具之后，Agent 会自己决定用哪个工具。
        """

        print("💡 [ProductAgent] 开始处理产品咨询请求...")

        # 用 create_react_agent 创建内部执行器
        # 目前 tools 为空，后面加入 RAG 工具
        inner_agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=self.system_prompt,
        )

        # 把对话历史传给内部 agent
        result = await inner_agent.ainvoke({
            "messages": state["messages"]
        })

        # 取出最后一条 AI 回复
        final_message = result["messages"][-1]

        print(f"[ProductAgent] 回复：{final_message.content[:50]}...")

        # 返回消息，LangGraph 会自动追加到 state["messages"]
        return {"messages": [final_message]}


# 全局实例，只初始化一次
product_agent_node = ProductAgentNode()


# LangGraph 节点函数，graph_manager 里 add_node 用这个
async def product_node(state: AgentState) -> Dict[str, Any]:
    return await product_agent_node(state)