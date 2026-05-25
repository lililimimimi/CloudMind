# agent/core/memory/short_term.py
# 作用：基于 Redis 的短期对话记忆
# 按用户/会话存储，TTL 自动过期，超过阈值自动压缩

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# 超过这个数量自动压缩，只保留最近的消息
COMPRESSION_THRESHOLD = 10

# 默认过期时间 30 分钟
DEFAULT_TTL = 1800


class ShortTermMemory:
    """
    基于 Redis 的短期对话记忆。

    功能：
    - 按 user_id + session_id 隔离存储
    - TTL 自动过期（默认30分钟）
    - 超过阈值自动压缩，避免 token 过多
    - Redis 不可用时优雅降级，不影响主流程
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        ttl: int = DEFAULT_TTL
    ) -> None:
        self._redis_url = redis_url
        self._ttl = ttl
        self._client: Any = None

        # Redis 是否可用的标记
        # False 时所有操作变为空操作，不报错
        self._available: bool = False

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """
        连接 Redis。
        连接失败不抛异常，只标记 _available=False。
        """
        try:
            import redis.asyncio as aioredis

            self._client = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=2,    # 连接超时2秒
                socket_timeout=2,            # 操作超时2秒
                health_check_interval=30,    # 每30秒检查一次连接健康
                retry_on_timeout=True,       # 超时自动重试
            )
            await self._client.ping()
            self._available = True
            logger.info("ShortTermMemory: Redis 连接成功 %s", self._redis_url)
        except Exception as exc:
            logger.warning(
                "ShortTermMemory: Redis 不可用 (%s)，短期记忆已禁用", exc
            )
            self._available = False

    async def close(self) -> None:
        """关闭 Redis 连接"""
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------

    async def get_messages(
        self,
        user_id: str,
        session_id: str
    ) -> list[dict[str, Any]]:
        """
        读取指定用户/会话的对话历史。
        Redis 不可用或没有记录时返回空列表。
        """
        if not self._available:
            return []
        try:
            data = await self._client.get(self._key(user_id, session_id))
            return json.loads(data) if data else []
        except Exception as exc:
            logger.warning("ShortTermMemory.get_messages 失败: %s", exc)
            self._available = False
            return []

    async def save_messages(
        self,
        user_id: str,
        session_id: str,
        messages: list[dict[str, Any]]
    ) -> None:
        """
        保存对话历史到 Redis。
        超过 COMPRESSION_THRESHOLD 时自动压缩。
        """
        if not self._available:
            return
        try:
            # 超过阈值自动压缩
            if len(messages) > COMPRESSION_THRESHOLD:
                messages = self._trim(messages)

            await self._client.set(
                self._key(user_id, session_id),
                json.dumps(messages, ensure_ascii=False),
                ex=self._ttl,   # 设置过期时间
            )
            logger.debug(
                "ShortTermMemory: 保存 %d 条消息 %s:%s",
                len(messages), user_id, session_id
            )
        except Exception as exc:
            logger.warning("ShortTermMemory.save_messages 失败: %s", exc)
            self._available = False

    async def append_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str
    ) -> None:
        """
        追加一条消息并重新保存。
        role: "human" 或 "ai"
        """
        messages = await self.get_messages(user_id, session_id)
        messages.append({"role": role, "content": content})
        await self.save_messages(user_id, session_id, messages)

    async def clear(
        self,
        user_id: str,
        session_id: str
    ) -> None:
        """
        清除指定用户/会话的对话历史。
        用户点击新对话时调用。
        """
        if not self._available:
            return
        try:
            await self._client.delete(self._key(user_id, session_id))
        except Exception as exc:
            logger.error("ShortTermMemory.clear 失败: %s", exc)

    @property
    def available(self) -> bool:
        """Redis 是否可用"""
        return self._available

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    @staticmethod
    def _key(user_id: str, session_id: str) -> str:
        """
        生成 Redis key。
        格式：memory:short:{user_id}:{session_id}
        """
        return f"memory:short:{user_id}:{session_id}"

    @staticmethod
    def _trim(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        压缩消息列表。
        保留系统消息 + 最近6条非系统消息。
        避免对话太长导致 token 超限。
        """
        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs  = [m for m in messages if m.get("role") != "system"]
        return system_msgs + other_msgs[-6:]


# 全局实例，只初始化一次
short_term_memory = ShortTermMemory()