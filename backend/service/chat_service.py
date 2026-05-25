# backend/service/chat_service.py
# 作用：接收前端请求，调用 Agent 图，流式返回结果
# 加入语义缓存：先查缓存，命中直接返回，不走 Agent
# 加入短期记忆：每次请求前读取历史，请求后保存历史

import os
import sys
import json
import asyncio
from typing import AsyncGenerator

# 把 agent 目录加入 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../agent'))

from langchain_core.messages import HumanMessage, AIMessage
from infra.cache import semantic_cache


class ChatService:
    """
    聊天服务类。
    流程：
    1. 查语义缓存，命中直接返回
    2. 未命中，读取 Redis 历史记录
    3. 调用 Agent 图处理
    4. 结果存入语义缓存
    5. 保存本轮对话到 Redis
    6. 分块流式返回结果
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
        """异步初始化，连接 Redis 和语义缓存"""
        await self.memory.initialize()
        await semantic_cache.initialize()

    async def stream_chat(
        self,
        query: str,
        user_id: str,
        session_id: str,
    ) -> AsyncGenerator[str, None]:
        """
        处理用户问题，分块流式返回结果。
        """

        try:
            # -------------------------------------------------------
            # 1. 查语义缓存
            # -------------------------------------------------------
            cache_hit = await semantic_cache.get_cache(query, user_id)
            if cache_hit:
                answer = cache_hit["answer"]
                print(
                    f"⚡ [ChatService] 语义缓存命中！"
                    f"level={cache_hit['level']} "
                    f"distance={cache_hit['distance']:.4f} "
                    f"matched='{cache_hit['matched_question'][:30]}'"
                )
                # 分块流式返回缓存答案
                chunk_size = 5
                for i in range(0, len(answer), chunk_size):
                    chunk = answer[i:i+chunk_size]
                    yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.02)
                yield f"data: {json.dumps({'done': True})}\n\n"
                return

            # -------------------------------------------------------
            # 2. 未命中，读取历史记录
            # -------------------------------------------------------
            print("🏃 [ChatService] 缓存未命中，进入 Agent 工作流...")
            history = await self.memory.get_messages(user_id, session_id)

            history_messages = []
            for msg in history:
                if msg["role"] == "human":
                    history_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "ai":
                    history_messages.append(AIMessage(content=msg["content"]))

            # 只保留最近2条历史，避免 AI 复用旧答案
            recent_history = history_messages[-2:] if len(history_messages) > 2 else history_messages
            current_message = HumanMessage(content=query)
            all_messages = recent_history + [current_message]

            print(f"[ChatService] 历史消息数：{len(recent_history)}，当前问题：{query}")

            # -------------------------------------------------------
            # 3. 调用 Agent 图
            # -------------------------------------------------------
            state = {
                "messages": all_messages,
                "user_id": user_id,
                "session_id": session_id,
                "next_agent": "",
                "response": "",
                "metadata": {},
            }

            result = await self.agent_graph.ainvoke(state)
            final_message = result["messages"][-1]
            answer = final_message.content

            print(f"[ChatService] 最终回复：{answer[:50]}...")

            # -------------------------------------------------------
            # 4. 存入语义缓存
            # 个人数据用 user scope，通用问题用 public scope
            # -------------------------------------------------------
            personal_keywords = ["账单", "订单", "实例", "我的", "查询"]
            is_personal = any(kw in query for kw in personal_keywords)

            await semantic_cache.set_cache(
                query=query,
                response=answer,
                user_id=user_id if is_personal else None,
                scope="user" if is_personal else "public",
            )

            # -------------------------------------------------------
            # 5. 保存到 Redis 短期记忆
            # -------------------------------------------------------
            await self.memory.append_message(user_id, session_id, "human", query)
            await self.memory.append_message(user_id, session_id, "ai", answer)

            # -------------------------------------------------------
            # 6. 分块流式返回
            # -------------------------------------------------------
            chunk_size = 5
            for i in range(0, len(answer), chunk_size):
                chunk = answer[i:i+chunk_size]
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.02)

            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            print(f"[ChatService] 错误：{e}")
            yield f"data: {json.dumps({'content': '系统出现错误，请稍后再试'})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"


# 全局实例
chat_service = ChatService()


async def stream_chat(
    query: str,
    user_id: str,
    session_id: str,
) -> AsyncGenerator[str, None]:
    async for chunk in chat_service.stream_chat(query, user_id, session_id):
        yield chunk