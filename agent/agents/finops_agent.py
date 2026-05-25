
# 作用：成本优化专员 Agent
# 负责分析用户的云资源使用情况，给出降本建议
# 在 FinOps 工作流中，billing_agent 先查到实例数据
# 再交给这里做成本分析

import os
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent

from core.workflow.state import AgentState

# 加载环境变量
load_dotenv()


class FinOpsAgentNode:
    """
    成本优化专员 Agent。

    工作流程：
    1. billing_agent 先查出用户真实实例数据
    2. 把实例数据存入 state["metadata"]["instance_data"]
    3. finops_agent 读取实例数据，结合监控指标分析
    4. 给出具体的降本建议
    """

    def __init__(self):
        # 初始化 LangChain 客户端
        self.llm = ChatOpenAI(
            api_key=os.getenv("SILICONFLOW_API_KEY"),
            base_url=os.getenv("SILICONFLOW_BASE_URL"),
            model=os.getenv("MODEL", "deepseek-ai/DeepSeek-V3"),
            temperature=0.3,
        )

        # 暂时没有工具，后面接入监控数据查询工具
        self.tools = []

        # 成本优化专员的系统提示词
        self.system_prompt = """你是 CloudMind 云平台的成本优化专员（FinOps）。
你的任务是根据用户的实例数据，分析云资源使用情况，给出降本建议。

分析维度：
- 实例规格是否过大（CPU、内存利用率低）
- 是否有长期停止但仍在计费的实例
- 是否可以用包年包月替代按量付费
- 是否可以用低规格实例替代高规格实例

回答要求：
- 用纯中文回答
- 给出具体可执行的建议
- 预估节省金额或比例
- 不要用 markdown 格式
- 如果实例数据不足，如实告知"""

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        """
        LangGraph 节点调用入口。
        读取 billing_agent 查到的实例数据，进行成本分析。
        """

        print("💡 [FinOpsAgent] 开始进行成本优化分析...")

        # 从 metadata 里取出 billing_agent 查到的实例数据
        metadata = state.get("metadata", {})
        instance_data = metadata.get("instance_data", "暂无实例数据")
        
        # 如果没有真实实例数据，给通用降本建议
        if not instance_data or len(instance_data) < 10:
            full_prompt = f"""{self.system_prompt}
            
当前没有获取到真实实例数据。
请给用户提供通用的云资源降本建议，包括：
包年包月优惠、合理规格选择、闲置资源清理等方向。
回答控制在150字以内，不要用列表格式。"""
        else:
            full_prompt = f"""{self.system_prompt}



当前用户实例数据：
{instance_data}

请根据以上实例数据给出具体的成本优化建议，控制在150字以内。"""

        print(f"[FinOpsAgent] 实例数据：{instance_data[:50]}...")

        # 用 create_react_agent 创建内部执行器
        inner_agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=full_prompt,
        )

        # 直接传对话历史
        result = await inner_agent.ainvoke({
            "messages": state["messages"]
        })

        # 取出最后一条 AI 回复
        final_message = result["messages"][-1]

        print(f"[FinOpsAgent] 回复：{final_message.content[:50]}...")

        # next_agent 清空，代表流程结束
        return {"messages": [final_message], "next_agent": ""}


# 全局实例，只初始化一次
finops_agent_node = FinOpsAgentNode()


# LangGraph 节点函数
async def finops_node(state: AgentState) -> Dict[str, Any]:
    return await finops_agent_node(state)