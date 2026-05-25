
# 作用：统一管理短期记忆（Redis）和长期记忆（Milvus）
# 对外提供统一接口，chat_service 只需要调用这个类

import asyncio
import logging
from typing import Any
from unittest import result

from core.memory.short_term import ShortTermMemory
from core.memory.long_term import LongTermMemory
from core.memory.preference_extractor import PreferenceExtractor

logger = logging.getLogger(__name__)

_TOP_K_PREFERENCES = 3    # 每次检索的最大偏好数量
_MAX_HISTORY_TURNS = 20   # 用于提取偏好的最大对话轮数


class MemoryManager:
    """
    记忆系统管理器。
    统一管理短期记忆（Redis）和长期记忆（Milvus）。

    会话生命周期：
    1. 新会话首次查询 → load_preferences 从 Milvus 获取偏好
    2. 每个查询轮次  → save_conversation 保存到 Redis
    3. 会话结束      → finalize_session 提取偏好存 Milvus，清 Redis
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        redis_ttl: int = 1800,
        milvus_host: str = "localhost",
        milvus_port: int = 19530,
        milvus_api_key: str | None = None,
        embedding_api_key: str | None = None,
    ) -> None:
        self.short_term = ShortTermMemory(
            redis_url=redis_url,
            ttl=redis_ttl,
        )
        self.long_term = LongTermMemory(
            host=milvus_host,
            port=milvus_port,
            api_key=milvus_api_key,
            embedding_api_key=embedding_api_key,
        )

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """并发初始化短期和长期记忆"""
        await asyncio.gather(
            self.short_term.initialize(),
            self.long_term.initialize(),
            return_exceptions=True,
        )
        logger.info(
            "MemoryManager 初始化完成 – 短期记忆=%s, 长期记忆=%s",
            "✓" if self.short_term.available else "✗ (禁用)",
            "✓" if self.long_term.available else "✗ (禁用)",
        )

    async def close(self) -> None:
        """关闭所有连接"""
        await asyncio.gather(
            self.short_term.close(),
            self.long_term.close(),
            return_exceptions=True,
        )
        logger.info("MemoryManager 已关闭")

    # ------------------------------------------------------------------
    # 每轮对话操作
    # ------------------------------------------------------------------

    async def save_conversation(
        self,
        user_id: str,
        session_id: str,
        messages: list[dict[str, Any]],
    ) -> None:
        """
        保存一轮对话到 Redis 短期记忆。
        追加到已有历史，不覆盖。
        """
        non_system = [m for m in messages if m.get("role") != "system"]
        existing = await self.short_term.get_messages(user_id, session_id)
        combined = existing + non_system
        await self.short_term.save_messages(user_id, session_id, combined)
        logger.debug(
            "[MEMORY] 保存 %d 条消息（总计 %d）user=%s session=%s",
            len(non_system), len(combined), user_id, session_id,
        )

    async def get_recent_messages(
        self, user_id: str, session_id: str
    ) -> list[dict[str, Any]]:
        """从 Redis 读取近期对话消息"""
        return await self.short_term.get_messages(user_id, session_id)
    
    async def get_memory_context(
    self,
    user_id: str,
    session_id: str,
    query: str,
    ) -> str:
        """
        获取记忆上下文，注入到 Agent prompt。
        包含：近期对话历史 + 相关长期记忆。
        """
        context_parts = []

        # 1. 近期对话历史（短期记忆）
        if self.short_term.available:
            history = await self.short_term.get_messages(user_id, session_id)
            print(f"[MemoryManager] 短期记忆：{len(history)} 条")
            if history:
                recent = history[-10:] if len(history) > 10 else history
                context_parts.append("【近期对话历史】:")
                for msg in recent:
                    role = "User" if msg["role"] == "human" else "Assistant"
                    context_parts.append(f"{role}: {msg['content'][:200]}")

        # 2. 相关长期记忆
        if self.long_term.available:
            memories = await self.long_term.retrieve_relevant(user_id, query)
            print(f"[MemoryManager] 长期记忆：{memories}")
            if memories:
                context_parts.append("\n【用户长期偏好/背景】:")
                for memory in memories:
                    context_parts.append(f"- {memory}")
                    
        result = "\n".join(context_parts)
        print(f"[MemoryManager] 记忆上下文长度：{len(result)}")
        return "\n".join(context_parts)

    # ------------------------------------------------------------------
    # 长期偏好操作
    # ------------------------------------------------------------------

    async def load_preferences(
        self,
        user_id: str,
        query: str = "用户偏好习惯个性特点",
        top_k: int = _TOP_K_PREFERENCES,
    ) -> list[str]:
        """
        从 Milvus 检索用户相关偏好。
        建议每次新会话调用一次，结果缓存起来。

        Args:
            user_id: 用户ID
            query: 语义搜索查询词
            top_k: 最多返回几条偏好

        Returns:
            偏好字符串列表
        """
        if not self.long_term.available:
            return []
        try:
            result = await self.long_term.retrieve_relevant(
                user_id=user_id,
                query=query,
                top_k=top_k,
            )
            logger.debug(
                "[MEMORY] load_preferences user='%s' → %d 条: %s",
                user_id, len(result), result,
            )
            return result
        except Exception as exc:
            logger.warning("load_preferences 失败 user=%s: %s", user_id, exc)
            return []

    async def save_preference(
        self, user_id: str, preference_type: str, value: str
    ) -> None:
        """手动保存一条用户偏好"""
        await self.long_term.save_preference(user_id, preference_type, value)

    async def background_extract(
        self, user_id: str, session_id: str, llm: Any
    ) -> list[str]:
        """
        后台提取偏好，不清除 Redis。
        适合在对话进行中定期调用。
        """
        if not self.long_term.available:
            return []

        messages = await self.short_term.get_messages(user_id, session_id)
        if len(messages) < 4:
            return []

        recent = messages[-_MAX_HISTORY_TURNS:]
        conversation_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in recent
        )

        try:
            extractor = PreferenceExtractor(llm=llm)
            existing = await self.load_preferences(user_id)
            new_items = await extractor.extract(
                conversation_text=conversation_text,
                existing=existing,
            )
            for item in new_items:
                await self.long_term.save_memory(
                    user_id=user_id,
                    content=item,
                    memory_type="preference",
                )
            if new_items:
                logger.info(
                    "[MEMORY] 后台提取：user='%s' 保存 %d 条新偏好: %s",
                    user_id, len(new_items), new_items,
                )
            return new_items
        except Exception as exc:
            logger.warning("[MEMORY] 后台提取失败 user=%s: %s", user_id, exc)
            return []

    # ------------------------------------------------------------------
    # 会话结束
    # ------------------------------------------------------------------

    async def finalize_session(
        self, user_id: str, session_id: str, llm: Any
    ) -> None:
        """
        会话结束时：提取偏好 → 存 Milvus → 清 Redis。

        流程：
        1. 从 Redis 读取对话历史
        2. 用 LLM 提取新偏好
        3. 与已有偏好去重
        4. 保存新偏好到 Milvus
        5. 清除 Redis 短期记忆
        """
        if not user_id or not session_id:
            return

        messages = await self.short_term.get_messages(user_id, session_id)
        if len(messages) < 2:
            await self.short_term.clear(user_id, session_id)
            return

        logger.info(
            "[MEMORY] 结束会话 %s:%s – %d 条消息",
            user_id, session_id, len(messages),
        )

        # 提取偏好
        if self.long_term.available:
            recent = messages[-_MAX_HISTORY_TURNS:]
            conversation_text = "\n".join(
                f"{m['role']}: {m['content']}" for m in recent
            )

            extractor = PreferenceExtractor(llm=llm)
            existing = await self.load_preferences(user_id)
            new_items = await extractor.extract(
                conversation_text=conversation_text,
                existing=existing,
            )

            for item in new_items:
                await self.long_term.save_memory(
                    user_id=user_id,
                    content=item,
                    memory_type="preference",
                )

            if new_items:
                logger.info(
                    "[MEMORY] 保存 %d 条新偏好 user='%s': %s",
                    len(new_items), user_id, new_items,
                )

        # 清除 Redis
        await self.short_term.clear(user_id, session_id)
        logger.info("[MEMORY] 清除短期记忆 %s:%s", user_id, session_id)