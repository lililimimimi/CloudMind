
# 作用：选型推荐专员 Agent
# 负责根据用户的业务场景，推荐合适的云产品实例型号
# 比如：Java + MySQL 需要什么配置、高并发场景推荐什么实例

import os
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent

from core.workflow.state import AgentState

# 加载环境变量
load_dotenv()


class RecommendationAgentNode:
    """
    选型推荐专员 Agent。
    负责根据用户的业务需求，推荐具体的云产品实例型号和配置。
    
    和 ProductAgent 的区别：
    - ProductAgent  → 介绍产品是什么、怎么用
    - RecommendationAgent → 根据业务场景推荐具体型号和配置
    """

    def __init__(self):
        # 初始化 LangChain 客户端
        self.llm = ChatOpenAI(
            api_key=os.getenv("SILICONFLOW_API_KEY"),
            base_url=os.getenv("SILICONFLOW_BASE_URL"),
            model=os.getenv("MODEL", "deepseek-ai/DeepSeek-V3"),
            temperature=0.1,  # 选型建议要准确，随机性低
        )

        # 暂时没有工具，后面接入产品目录查询工具
        self.tools = []

        # 选型专员的系统提示词
        self.system_prompt = """你是 CloudMind 云平台的选型推荐专员。
你的任务是根据用户描述的业务场景，推荐最合适的云产品实例型号和配置。

推荐维度：
- 根据业务类型（Web应用、数据库、大数据、AI训练等）推荐实例族
- 根据并发量、数据量估算所需 CPU 和内存
- 给出具体的实例型号（如 ecs.c7.2xlarge）
- 说明推荐理由和预估费用范围
- 如果预算有限，给出性价比最高的方案

回答要求：
- 用纯中文回答
- 给出至少两个方案供用户选择（入门版和推荐版）
- 说明每个方案的适用场景
- 不要用 markdown 格式
- 数据要合理，不要编造不存在的实例型号"""

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        """
        LangGraph 节点调用入口。
        """

        print("💡 [RecommendationAgent] 开始处理选型推荐请求...")

        # 用 create_react_agent 创建内部执行器
        inner_agent = create_react_agent(
            model=self.llm,
            tools=self.tools,   # 后面加入产品目录查询工具
            prompt=self.system_prompt,
        )

        # 把对话历史传给内部 agent
        result = await inner_agent.ainvoke({
            "messages": state["messages"]
        })

        # 取出最后一条 AI 回复
        final_message = result["messages"][-1]

        print(f"[RecommendationAgent] 回复：{final_message.content[:50]}...")

        return {"messages": [final_message]}


# 全局实例，只初始化一次
recommendation_agent_node = RecommendationAgentNode()


# LangGraph 节点函数
async def recommendation_node(state: AgentState) -> Dict[str, Any]:
    return await recommendation_agent_node(state)