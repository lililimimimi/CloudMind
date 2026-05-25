
# 作用：推广活动专员 Agent
# 负责处理推广返佣、活动链接、海报生成等营销类需求
# 目前先用 AI 模拟返回，后面接入 MCP 工具生成真实海报

import os
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent

from core.workflow.state import AgentState

# 加载环境变量
load_dotenv()


class PromotionAgentNode:
    """
    推广活动专员 Agent。
    负责处理：
    - 推广返佣链接生成
    - 活动物料获取
    - AI 海报生成
    - 推广商品查询
    """

    def __init__(self):
        # 初始化 LangChain 客户端
        self.llm = ChatOpenAI(
            api_key=os.getenv("SILICONFLOW_API_KEY"),
            base_url=os.getenv("SILICONFLOW_BASE_URL"),
            model=os.getenv("MODEL", "deepseek-ai/DeepSeek-V3"),
            temperature=0.7,  # 推广文案可以适当有创意
        )

        # 暂时没有工具，后面接入 MCP 生成真实海报和链接
        self.tools = []

        # 推广专员的系统提示词
        self.system_prompt = """你是 CloudMind 云平台的推广活动专员。
你负责处理以下类型的需求：
- 推广返佣链接的生成和说明
- 云产品活动物料的获取
- AI 推广海报的生成
- 当前可推广商品的查询

回答要求：
- 用纯中文回答
- 语气友好积极
- 简洁清晰，不超过300字
- 不要用 markdown 格式
- 目前工具还未接入，请告知用户功能即将上线，
  并描述该功能的大致效果"""

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        """
        LangGraph 节点调用入口。
        """

        print("💡 [PromotionAgent] 开始处理推广活动请求...")

        # 用 create_react_agent 创建内部执行器
        inner_agent = create_react_agent(
            model=self.llm,
            tools=self.tools,   # 后面加入 MCP 工具
            prompt=self.system_prompt,
        )

        # 把对话历史传给内部 agent
        result = await inner_agent.ainvoke({
            "messages": state["messages"]
        })

        # 取出最后一条 AI 回复
        final_message = result["messages"][-1]

        print(f"[PromotionAgent] 回复：{final_message.content[:50]}...")

        return {"messages": [final_message]}


# 全局实例，只初始化一次
promotion_agent_node = PromotionAgentNode()


# LangGraph 节点函数
async def promotion_node(state: AgentState) -> Dict[str, Any]:
    return await promotion_agent_node(state)