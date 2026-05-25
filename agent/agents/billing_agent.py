
# 作用：账单查询专员 Agent
# 负责查询用户的订单、账单、实例状态等真实数据


import os
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent

from core.workflow.state import AgentState

# 加载环境变量
load_dotenv()


class BillingAgentNode:
    """
    账单查询专员 Agent。
    负责查询用户真实的订单、账单、实例状态。
    
    特殊逻辑：
    - 普通账单查询 → 直接返回结果给用户
    - FinOps 工作流 → 查完实例数据，传给 finops_agent 继续分析
    """

    def __init__(self):
        # 初始化 LangChain 客户端
        self.llm = ChatOpenAI(
            api_key=os.getenv("SILICONFLOW_API_KEY"),
            base_url=os.getenv("SILICONFLOW_BASE_URL"),
            model=os.getenv("MODEL", "deepseek-ai/DeepSeek-V3"),
            temperature=0,    # 账单数据要求准确，随机性设为 0
        )

        # 暂时没有工具，后面接入 MCP 查真实数据库
        self.tools = []

        # 普通账单查询的系统提示词
        self.system_prompt = """你是 CloudMind 云平台的账单查询专员。
你负责查询用户的订单记录、账单明细、实例状态等信息。

重要规则：
- 只能查询当前登录用户自己的数据，不能查询其他用户
- 数据必须来自工具返回的真实结果，不能编造
- 如果工具没有返回数据，如实告知用户

回答要求：
- 用纯中文回答
- 简洁清晰
- 不要用 markdown 格式"""

        # FinOps 工作流的系统提示词
        # 这个场景下需要把实例数据整理好，传给 finops_agent
        self.finops_system_prompt = """你是 CloudMind 云平台的账单查询专员。
你现在的任务是查询用户当前所有运行中的实例信息。
请列出每个实例的：实例ID、实例类型、运行状态、所在地域。
数据必须来自工具返回的真实结果，不能编造。
输出格式要清晰，方便后续成本分析使用。"""

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        """
        LangGraph 节点调用入口。
        根据 is_finops_workflow 决定用哪个提示词。
        """

        # 判断是否是 FinOps 工作流
        metadata = state.get("metadata", {})
        is_finops = metadata.get("is_finops_workflow", False)

        if is_finops:
            print("💡 [BillingAgent] FinOps 工作流，查询用户实例数据...")
            prompt = self.finops_system_prompt
        else:
            print("💡 [BillingAgent] 普通账单查询...")
            prompt = self.system_prompt

        # 用 create_react_agent 创建内部执行器
        inner_agent = create_react_agent(
            model=self.llm,
            tools=self.tools,   # 后面加入 MCP 工具查真实数据
            prompt=prompt,
        )

        # 把对话历史传给内部 agent
        result = await inner_agent.ainvoke({
            "messages": state["messages"]
        })

        # 取出最后一条 AI 回复
        final_message = result["messages"][-1]

        print(f"[BillingAgent] 回复：{final_message.content[:50]}...")

        # FinOps 工作流：把实例数据存入 metadata，传给 finops_agent
        if is_finops:
            metadata["instance_data"] = final_message.content
            return {
                "messages": [final_message],
                "metadata": metadata,
            }

        # 普通账单查询：直接返回结果
        return {"messages": [final_message]}


# 全局实例，只初始化一次
billing_agent_node = BillingAgentNode()


# LangGraph 节点函数
async def billing_node(state: AgentState) -> Dict[str, Any]:
    return await billing_agent_node(state)