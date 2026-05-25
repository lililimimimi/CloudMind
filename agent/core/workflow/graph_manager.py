
# 作用：用 LangGraph 把所有 Agent 组装成一张有序的工作流图
# 封装成 class，统一管理所有 Agent 的初始化和流转逻辑

import asyncio
from langgraph.graph import StateGraph, START, END
from core.workflow.state import AgentState

# 导入所有 Agent
from agents.orchestrator import OrchestratorAgent
from agents.product_agent import ProductAgentNode
from agents.billing_agent import BillingAgentNode
from agents.promotion_agent import PromotionAgentNode
from agents.recommendation_agent import RecommendationAgentNode
from agents.finops_agent import FinOpsAgentNode


class AgentGraphManager:
    """
    负责组装 LangGraph 多 Agent 编排。
    统一管理所有 Agent 的初始化。
    支持 FinOps 工作流的跨 Agent 协同。
    """

    def __init__(self):
        # 统一初始化所有 Agent，只初始化一次
        self.orchestrator = OrchestratorAgent()
        self.product_node = ProductAgentNode()
        self.billing_node = BillingAgentNode()
        self.promotion_node = PromotionAgentNode()
        self.recommendation_node = RecommendationAgentNode()
        self.finops_node = FinOpsAgentNode()

    def _route_condition(self, state: AgentState) -> str:
        """
        orchestrator 完成后的路由函数。
        读取 next_agent，决定去哪个专业 Agent。
        """
        next_agent = state.get("next_agent", "product_agent")
        print(f"[Router] 路由到：{next_agent}")
        return next_agent

    def _billing_post_condition(self, state: AgentState) -> str:
        """
        billing_agent 完成后的路由函数。
        判断是普通账单查询还是 FinOps 工作流。
        FinOps 工作流：继续去 finops_agent 分析成本。
        普通查询：直接结束。
        """
        is_finops = state.get("metadata", {}).get("is_finops_workflow", False)

        if is_finops:
            print("[Router] FinOps 工作流，转交 finops_agent")
            return "finops_agent"

        print("[Router] 普通账单查询，流程结束")
        return END

    def build_graph(self):
        """
        构建 LangGraph 状态图。
        返回编译好的可执行图对象。
        """
        builder = StateGraph(AgentState)

        # -------------------------------------------------------
        # 1. 添加所有节点
        # -------------------------------------------------------
        builder.add_node("orchestrator", self.orchestrator.route)
        builder.add_node("product_agent", self.product_node)
        builder.add_node("billing_agent", self.billing_node)
        builder.add_node("promotion_agent", self.promotion_node)
        builder.add_node("recommendation_agent", self.recommendation_node)
        builder.add_node("finops_agent", self.finops_node)

        # -------------------------------------------------------
        # 2. 设置入口
        # -------------------------------------------------------
        builder.add_edge(START, "orchestrator")

        # -------------------------------------------------------
        # 3. orchestrator 完成后，条件路由到对应专业 Agent
        # -------------------------------------------------------
        builder.add_conditional_edges(
            "orchestrator",
            self._route_condition,
            {
                "product_agent":        "product_agent",
                "billing_agent":        "billing_agent",
                "promotion_agent":      "promotion_agent",
                "recommendation_agent": "recommendation_agent",
            }
        )

        # -------------------------------------------------------
        # 4. billing_agent 完成后，判断是否进入 finops_agent
        # -------------------------------------------------------
        builder.add_conditional_edges(
            "billing_agent",
            self._billing_post_condition,
            {
                "finops_agent": "finops_agent",
                END: END,
            }
        )

        # -------------------------------------------------------
        # 5. 其他 Agent 完成后直接结束
        # -------------------------------------------------------
        builder.add_edge("product_agent", END)
        builder.add_edge("promotion_agent", END)
        builder.add_edge("recommendation_agent", END)
        builder.add_edge("finops_agent", END)

        return builder.compile()


# -------------------------------------------------------
# 测试函数，不启动服务直接测试 Agent 流程
# -------------------------------------------------------
async def test_graph():
    manager = AgentGraphManager()
    graph = manager.build_graph()

    print("🚀 启动 CloudMind Multi-Agent 系统...")
    print("=" * 60)

    # 第一轮：产品问题
    state: AgentState = {
        "messages": [("user", "什么是VPC？")],
        "user_id": "user_1001",
        "session_id": "test_session_1",
        "next_agent": "",
        "response": "",
        "metadata": {}
    }

    print(f"👤 用户：{state['messages'][0][1]}")
    result = await graph.ainvoke(state)
    print(f"🤖 AI：{result['messages'][-1].content}\n")

    # 第二轮：账单问题
    state["messages"] = result["messages"]
    state["messages"].append(("user", "帮我查一下我最近的订单"))

    print(f"👤 用户：{state['messages'][-1][1]}")
    result = await graph.ainvoke(state)
    print(f"🤖 AI：{result['messages'][-1].content}\n")


# -------------------------------------------------------
# 全局图实例，只初始化一次，供 chat_service 调用
# -------------------------------------------------------
graph_manager = AgentGraphManager()
agent_graph = graph_manager.build_graph()


if __name__ == "__main__":
    asyncio.run(test_graph())