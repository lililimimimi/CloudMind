
# 作用：接收前端请求，调用 Agent 图，流式返回结果
# 加入短期记忆：每次请求前读取历史，请求后保存历史

import os
import sys
from typing import AsyncGenerator


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../agent'))

from langchain_core.messages import HumanMessage, AIMessage


class ChatService:
    """
    聊天服务类。
    负责：
    1. 读取 Redis 历史记录
    2. 调用 Agent 图处理问题
    3. 保存本轮对话到 Redis
    4. 流式返回结果给前端
    """

    def __init__(self):
        # 初始化 Agent 图
        from core.workflow.graph_manager import AgentGraphManager
        manager = AgentGraphManager()
        self.agent_graph = manager.build_graph()

        # 初始化短期记忆
        from core.memory.short_term import ShortTermMemory
        self.memory = ShortTermMemory(
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            ttl=int(os.getenv("REDIS_TTL", 1800)),
        )

        print("[ChatService] 初始化完成")

    async def initialize(self):
        """
        异步初始化，连接 Redis。
        在 FastAPI startup 事件里调用。
        """
        await self.memory.initialize()

    async def stream_chat(
        self,
        query: str,
        user_id: str,
        session_id: str,
    ) -> AsyncGenerator[str, None]:
        """
        调用 Agent 图处理用户问题，流式返回结果。

        流程：
        1. 从 Redis 读取历史对话
        2. 把历史 + 新问题一起传给 Agent 图
        3. 取出最终回复，逐字流式返回
        4. 把本轮对话保存到 Redis
        """

        try:
            # 1. 从 Redis 读取历史对话
            history = await self.memory.get_messages(user_id, session_id)

            # 2. 把历史消息转成 LangChain 格式
            history_messages = []
            for msg in history:
                if msg["role"] == "human":
                    history_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "ai":
                    history_messages.append(AIMessage(content=msg["content"]))

            # 3. 加入本次用户问题
            current_message = HumanMessage(content=query)
            all_messages = history_messages + [current_message]

            print(f"[ChatService] 历史消息数：{len(history_messages)}，当前问题：{query}")

            # 4. 封装成 AgentState
            state = {
                "messages": all_messages,
                "user_id": user_id,
                "session_id": session_id,
                "next_agent": "",
                "response": "",
                "metadata": {},
            }

            # 5. 调用 Agent 图
            result = await self.agent_graph.ainvoke(state)

            # 6. 取出最终回复
            final_message = result["messages"][-1]
            answer = final_message.content

            print(f"[ChatService] 最终回复：{answer[:50]}...")

            # 7. 保存本轮对话到 Redis
            await self.memory.append_message(user_id, session_id, "human", query)
            await self.memory.append_message(user_id, session_id, "ai", answer)

            # 8. 逐字流式返回给前端
            for char in answer:
                if char == '\n':
                    yield f"data: <br>\n\n"
                else:
                    yield f"data: {char}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            print(f"[ChatService] 错误：{e}")
            yield f"data: 系统出现错误，请稍后再试\n\n"
            yield "data: [DONE]\n\n"


# 全局实例，只初始化一次
chat_service = ChatService()


# 供 chat_router 调用的函数
async def stream_chat(
    query: str,
    user_id: str,
    session_id: str,
) -> AsyncGenerator[str, None]:
    async for chunk in chat_service.stream_chat(query, user_id, session_id):
        yield chunk