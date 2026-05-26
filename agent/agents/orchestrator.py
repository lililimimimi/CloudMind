
# 作用：总路由 Agent，判断用户问题属于哪个类型
# 根据意图决定分发给哪个专业 Agent 处理

import os
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from core.workflow.state import AgentState

# 加载环境变量
load_dotenv()

class OrchestratorAgent:
    """
    总路由 Agent。
    只做一件事：判断用户意图，决定交给哪个专业 Agent。
    不回答用户问题，只做分类决策。
    """

    def __init__(self):
        # 初始化 LangChain 的 ChatOpenAI 客户端
        # 兼容硅基流动的 OpenAI 接口
        self.llm = ChatOpenAI(
            api_key=os.getenv("SILICONFLOW_API_KEY"),
            base_url=os.getenv("SILICONFLOW_BASE_URL"),
            model=os.getenv("MODEL", "deepseek-ai/DeepSeek-V3"),
            temperature=0,   # 设为 0，让意图判断结果稳定
        )

        # 意图分类的系统提示词
        # 路由规则要尽量清晰，避免模型判断错误
        self.system_prompt = """你是一个智能客服系统的总路由。
你的任务是根据用户的提问，决定将问题分发给哪个专业 Agent 处理。

可用的 Agent：
1. product_agent      → 云产品介绍、功能说明、概念解释、操作指南
2. billing_agent      → 查询个人实例、订单记录、账单明细
3. promotion_agent    → 推广返佣、获取活动链接、生成海报
4. recommendation_agent → 业务场景选型、推荐具体实例型号
5. finops_agent_trigger → 降本增效、成本优化、资源闲置分析


路由细则：
- 用户问"退款规则/退款政策/退款限制/退款条件" → product_agent（这是知识类问题）
- 用户问"帮我查账单/查订单/查实例" → billing_agent（这是查数据）
- 用户问"账单太贵/帮我省钱" → finops_agent_trigger
- 用户问"ECS是什么/怎么用/有什么特性" → product_agent
- 用户问"推荐实例/选型" → recommendation_agent
- 用户问"推广/海报/返佣" → promotion_agent

只输出一个 Agent 名称，不要输出任何其他内容。
如果无法判断，默认输出 product_agent。"""

    @staticmethod
    def _message_content(message: Any) -> str:
        if hasattr(message, "content"):
            return str(message.content)
        return str(message)

    @staticmethod
    def _looks_like_promotion_selection(user_input: str, context: str) -> bool:
        promotion_context_markers = ["推广", "海报", "返佣", "活动", "专属链接"]
        selection_context_markers = ["选择", "哪一款", "序号", "请选择", "找到"]
        selection_markers = [
            "ecs.",
            "gpu",
            "第",
            "实例",
            "1",
            "2",
            "3",
            "一",
            "二",
            "三",
        ]

        has_promotion_context = any(k in context for k in promotion_context_markers)
        has_selection_context = any(k in context for k in selection_context_markers)
        has_selection_input = any(k in user_input.lower() for k in selection_markers)
        return has_promotion_context and has_selection_context and has_selection_input

    async def route(self, state: AgentState) -> Dict[str, Any]:
        """
        路由函数，LangGraph 会调用这个函数。
        读取最新的用户消息，判断意图，写回 state。
        """

        # 取出最新一条用户消息
        messages = state.get("messages", [])
        if not messages:
            return {"next_agent": "product_agent", "metadata": {}}

        # 获取最后一条消息的内容
        last_msg = messages[-1]
        user_input = self._message_content(last_msg)

        print(f"[Orchestrator] 收到问题：{user_input}")

        recent_context = "\n".join(self._message_content(msg) for msg in messages[-4:-1])
        metadata = state.get("metadata", {})

        if self._looks_like_promotion_selection(user_input, recent_context):
            metadata["is_finops_workflow"] = False
            print("[Orchestrator] 检测到推广流程中的产品选择，继续路由到 promotion_agent")
            return {
                "next_agent": "promotion_agent",
                "metadata": metadata,
            }

        # 调用 AI 判断意图
        response = await self.llm.ainvoke([
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_input),
        ])

        # 取出意图，清理空格换行
        decision = response.content.strip().lower()

        print(f"[Orchestrator] 判断结果：{decision}")

        # 根据意图决定下一个 Agent
        if "finops" in decision:
            # FinOps 流程：先让 billing_agent 查真实实例
            # 再交给 finops_agent 分析
            next_agent = "billing_agent"
            metadata["is_finops_workflow"] = True
            print("[Orchestrator] FinOps 工作流，先查实例数据")

        elif "billing" in decision:
            next_agent = "billing_agent"
            metadata["is_finops_workflow"] = False
            print("[Orchestrator] 路由到 billing_agent")

        elif "promotion" in decision:
            next_agent = "promotion_agent"
            print("[Orchestrator] 路由到 promotion_agent")

        elif "recommendation" in decision:
            next_agent = "recommendation_agent"
            print("[Orchestrator] 路由到 recommendation_agent")

        else:
            # 默认走产品咨询
            next_agent = "product_agent"
            print("[Orchestrator] 路由到 product_agent")

        return {
            "next_agent": next_agent,
            "metadata": metadata,
        }


# 实例化，供 graph_manager 使用
orchestrator = OrchestratorAgent()

# LangGraph 节点函数，graph_manager 里 add_node 用这个
async def orchestrator_node(state: AgentState) -> Dict[str, Any]:
    return await orchestrator.route(state)
