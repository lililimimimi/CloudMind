
# 作用：接收前端请求，调用 Agent 图，流式返回结果
# 完整记忆系统：语义缓存 + 短期记忆 + 长期记忆

import os
import sys
import json
import asyncio
from typing import AsyncGenerator

# 把 agent 目录加入 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../agent'))

from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from infra.cache import semantic_cache
from app_config.settings import settings


class ChatService:
    """
    聊天服务类。
    流程：
    1. 查语义缓存，命中直接返回
    2. 未命中，读取记忆上下文（短期+长期）
    3. 调用 Agent 图处理
    4. 结果存入语义缓存
    5. 保存对话到短期记忆
    6. 后台提取长期偏好
    7. 分块流式返回结果
    """

    def __init__(self):
        # 初始化 Agent 图
        from core.workflow.graph_manager import AgentGraphManager
        manager = AgentGraphManager()
        self.agent_graph = manager.build_graph()

        # 初始化记忆管理器
        from core.memory.memory_manager import MemoryManager
        self.memory = MemoryManager(
            redis_url=settings.redis_url,
            redis_ttl=settings.redis_ttl,
            milvus_host=settings.milvus_host,
            milvus_port=settings.milvus_port,
            milvus_api_key=settings.milvus_api_key or None,
            embedding_api_key=settings.siliconflow_api_key,
        )

        # 初始化 LLM，用于偏好提取
        self.llm = ChatOpenAI(
            api_key=settings.siliconflow_api_key,
            base_url=settings.siliconflow_base_url,
            model=settings.model,
            temperature=0,
        )

        print("[ChatService] 初始化完成")

    async def initialize(self):
        """异步初始化"""
        await self.memory.initialize()
        await semantic_cache.initialize()
        print(f"[ChatService] 短期记忆可用：{self.memory.short_term.available}")
        print(f"[ChatService] 长期记忆可用：{self.memory.long_term.available}")

    async def stream_chat(
        self,
        query: str,
        user_id: str,
        session_id: str,
    ) -> AsyncGenerator[str, None]:
        """处理用户问题，分块流式返回结果"""

        try:
            history = await self.memory.get_recent_messages(user_id, session_id)
            has_history = bool(history)

            # -------------------------------------------------------
            # 1. 读取记忆上下文
            # -------------------------------------------------------
            memory_context = await self.memory.get_memory_context(
                user_id, session_id, query
            )
            has_memory_context = bool(memory_context.strip())

            # -------------------------------------------------------
            # 2. 查语义缓存
            # -------------------------------------------------------
            # 有对话历史或长期记忆时，必须进入 Agent 工作流，避免缓存答案绕过个性化上下文。
            cache_hit = await semantic_cache.get_cache(query, user_id)
            if cache_hit:
                answer = cache_hit["answer"]
                print(
                    f"⚡ [ChatService] 语义缓存命中！"
                    f"level={cache_hit['level']} "
                    f"distance={cache_hit['distance']:.4f}"
                )
                async for chunk in self._stream_text(answer):
                    yield chunk
                return

            # -------------------------------------------------------
            # 3. 调用 Agent 工作流
            # -------------------------------------------------------
            print("🏃 [ChatService] 缓存未命中，进入 Agent 工作流...")

            history_messages = []
            for msg in history:
                if msg["role"] == "human":
                    history_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "ai":
                    history_messages.append(AIMessage(content=msg["content"]))

            # 只保留最近2条
            recent_history = history_messages[-2:] if len(history_messages) > 2 else history_messages
            current_message = HumanMessage(content=query)
            all_messages = recent_history + [current_message]

            print(f"[ChatService] 历史消息数：{len(recent_history)}，当前问题：{query}")

            state = {
                "messages": all_messages,
                "user_id": user_id,
                "session_id": session_id,
                "next_agent": "",
                "response": "",
                "metadata": {},
                "memory_context": memory_context,
            }

            result = await self.agent_graph.ainvoke(state)
            final_message = result["messages"][-1]
            answer = final_message.content

            print(f"[ChatService] 最终回复：{answer[:50]}...")

            # -------------------------------------------------------
            # 4. 存入语义缓存
            # -------------------------------------------------------
            personal_keywords = ["账单", "订单", "实例", "我的", "查询"]
            is_personal = any(kw in query for kw in personal_keywords)

            if not has_history:
                await semantic_cache.set_cache(
                    query=query,
                    response=answer,
                    user_id=user_id if is_personal else None,
                    scope="user" if is_personal else "public",
                )

            # -------------------------------------------------------
            # 5. 保存对话到短期记忆
            # -------------------------------------------------------
            await self.memory.save_conversation(
                user_id, session_id,
                [
                    {"role": "human", "content": query},
                    {"role": "ai", "content": answer},
                ]
            )

            # -------------------------------------------------------
            # 6. 后台提取长期偏好（不阻塞返回）
            # -------------------------------------------------------
            asyncio.create_task(
                self.memory.background_extract(user_id, session_id, self.llm)
            )

            # -------------------------------------------------------
            # 7. 分块流式返回
            # -------------------------------------------------------
            async for chunk in self._stream_text(answer):
                yield chunk

        except Exception as e:
            print(f"[ChatService] 错误：{e}")
            yield f"data: {json.dumps({'content': '系统出现错误，请稍后再试'})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

    async def _stream_text(self, text: str) -> AsyncGenerator[str, None]:
        """分块流式返回文本"""
        chunk_size = 5
        for i in range(0, len(text), chunk_size):
            chunk = text[i:i+chunk_size]
            yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.02)
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
