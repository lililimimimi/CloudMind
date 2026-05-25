# agent/agents/product_agent.py
import os
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from core.workflow.state import AgentState
from tools.vector_tool import query_vector_db
from tools.graph_tool import query_knowledge_graph

load_dotenv()


class ProductAgentNode:
    """
    产品咨询专员 Agent。
    配备两个工具：
    - query_vector_db：查询文档知识库，适合概念解释、规则政策
    - query_knowledge_graph：查询知识图谱，适合结构化参数查询
    """

    def __init__(self):
        self.llm = ChatOpenAI(
            api_key=os.getenv("SILICONFLOW_API_KEY"),
            base_url=os.getenv("SILICONFLOW_BASE_URL"),
            model=os.getenv("MODEL", "deepseek-ai/DeepSeek-V3"),
            temperature=0.1,
        )

        # 两个工具配合使用
        self.tools = [query_vector_db, query_knowledge_graph]

        self.system_prompt = """你是 CloudMind 云平台的产品咨询专员。
你有两个检索工具可以使用：

1. query_vector_db（向量检索）：
   适合：概念解释、操作步骤、规则政策、长文本说明
   例如：ECS是什么、退款规则、安全组怎么配置

2. query_knowledge_graph（知识图谱）：
   适合：结构化参数、产品关系、实例规格、地域可用区
   例如：ecs.g8a.xlarge有多少网卡、华北2有哪些可用区

工作要求：
- 根据问题类型选择合适的工具
- 结构化参数优先用知识图谱
- 概念解释优先用向量检索
- 复杂问题可以同时使用两个工具
- 数据必须来自工具返回结果，不能编造
- 如果工具没找到，诚实告知用户
- 用纯中文回答，不要用 markdown 格式"""

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        print("💡 [ProductAgent] 开始处理产品咨询请求...")
        
        # 读取记忆上下文
        memory_context = state.get("memory_context", "")

        # 把记忆注入到 system_prompt
        full_prompt = self.system_prompt
        if memory_context:
            full_prompt = f"""{self.system_prompt}

【用户背景信息】:
{memory_context}

请根据以上用户背景信息，提供更有针对性的推荐。"""

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