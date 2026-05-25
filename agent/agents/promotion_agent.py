# agent/agents/promotion_agent.py
# 作用：推广活动专员 Agent
# 通过 MCP 工具获取推广物料、生成推广链接、生成 AI 海报

import os
import json
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from core.workflow.state import AgentState
from agents.billing_agent import UserIdInjector

load_dotenv()


class PromotionAgentNode:
    """
    推广活动专员 Agent。
    负责处理推广返佣、活动物料、AI 海报生成等营销类需求。
    """

    def __init__(self):
        self.llm = ChatOpenAI(
            api_key=os.getenv("SILICONFLOW_API_KEY"),
            base_url=os.getenv("SILICONFLOW_BASE_URL"),
            model="Qwen/Qwen2.5-32B-Instruct",
            temperature=0.3,
        )

        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config', 'mcp_servers.json'
        )
        with open(config_path, 'r', encoding='utf-8') as f:
            self.mcp_config = json.load(f)

    async def __call__(self, state: AgentState) -> Dict[str, Any]:

        config = {"configurable": {"user_id": state.get("user_id", "unknown")}}

        client = MultiServerMCPClient(
            connections=self.mcp_config.get("mcpServers", {}),
            tool_interceptors=[UserIdInjector()]
        )
        all_tools = await client.get_tools()
        target_tools = [
            "get_promotable_products",
            "search_product_catalog",
            "get_promotion_materials",
            "generate_ai_poster"
        ]
        tools = [t for t in all_tools if t.name in target_tools]

        system_prompt = """你是一个热情的云服务平台推广营销专员。
你的主要任务是帮助想要分享或推广云产品的用户，提供对应的产品亮点、专属推广链接，并使用 AI 为其生成专属推广海报。

工作流程：

1. 意图：随便看看或列出商品
   当用户说"我想推广商品"、"有哪些商品可以推广"时：
   必须先调用 get_promotable_products 工具，获取所有可推广产品列表展示给用户。
   给商品编上序号，引导用户选择。
   此时不要调用生成物料的工具，等待用户回复。

2. 意图：用户明确了具体产品
   当用户一开始就明确说要推广某款产品（如"云服务器ECS"、"GPU实例"）时：
   直接调用 search_product_catalog 搜索，不需要先列清单。
   搜到结果后直接继续步骤3和4，不要等待用户确认。

3. 处理未找到的情况
   如果 search_product_catalog 返回 not_found，不要捏造产品。
   使用工具返回的通用活动继续执行步骤4。

4. 获取物料与生成海报（必须完成，不能跳过）
   拿到 product_id 后：
   必须调用 get_promotion_materials 获取专属链接和卖点。
   必须调用 generate_ai_poster 生成海报，自己构思一段英文 prompt，
   例如："A futuristic cloud server room, glowing blue neon lights, high tech"
   海报生成需要约30秒，调用前告知用户稍等。

注意：
- 调用 get_promotion_materials 时 user_id 传 "auto"
- 最终回答必须包含：
  1. 热情开场白 + 返佣比例
  2. 产品核心卖点
  3. 专属推广链接：[点击这里查看活动详情](链接URL)
  4. 海报图片：![产品名称推广海报](图片URL)
- 文字内容必须在图片前面
- 用纯中文回答"""

        inner_agent = create_react_agent(
            model=self.llm,
            tools=tools,
            prompt=system_prompt
        )

        print("📢 [PromotionAgent] 正在生成营销与推广物料...")

        result = await inner_agent.ainvoke(
            {"messages": state["messages"]},
            config=config
        )

        final_message = result["messages"][-1]
        return {"messages": [final_message]}


# 全局实例
promotion_agent_node = PromotionAgentNode()


async def promotion_node(state: AgentState) -> Dict[str, Any]:
    return await promotion_agent_node(state)