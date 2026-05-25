
# 作用：长期记忆管理，用 Milvus 存储用户偏好和背景
# 跨会话保留，永久有效
# 用向量检索找到和当前问题最相关的记忆

import logging
from typing import Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

COLLECTION_NAME = "long_term_memory"
EMBEDDING_DIM = 1024  # BAAI/bge-m3 的维度


class LongTermMemory:
    """
    长期记忆管理类。
    用 Milvus 存储用户的偏好、背景、重要信息。

    存储内容举例：
    - "用户是 Java 开发者"
    - "用户主要做电商业务"
    - "用户偏好华北2地域"

    检索时根据当前问题，找到最相关的记忆注入到 prompt。

    用法：
        mem = LongTermMemory(embedding_api_key="sk-...")
        await mem.initialize()
        await mem.save_preference("user1", "language", "Java")
        results = await mem.retrieve_relevant("user1", "推荐实例")
        await mem.close()
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 19530,
        api_key: str | None = None,
        embedding_api_key: str | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._api_key = api_key
        self._embedding_api_key = embedding_api_key
        self._client: Any = None
        self._embeddings: Any = None
        self._available: bool = False

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """连接 Milvus，失败不抛异常"""
        try:
            from pymilvus import MilvusClient
            from langchain_openai import OpenAIEmbeddings

            uri = f"http://{self._host}:{self._port}"
            connect_kwargs: dict[str, Any] = {"uri": uri}
            if self._api_key:
                connect_kwargs["token"] = self._api_key

            self._client = MilvusClient(**connect_kwargs)
            self._embeddings = OpenAIEmbeddings(
                model="BAAI/bge-m3",
                api_key=self._embedding_api_key,
                base_url="https://api.siliconflow.cn/v1"
            )

            self._ensure_collection()
            self._available = True
            logger.info("LongTermMemory: Milvus 连接成功 %s:%s", self._host, self._port)

        except Exception as exc:
            logger.warning("LongTermMemory: 初始化失败 (%s)，长期记忆已禁用", exc)
            self._available = False

    async def close(self) -> None:
        """关闭 Milvus 连接"""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------

    async def save_memory(
        self,
        user_id: str,
        content: str,
        memory_type: str = "general",
    ) -> None:
        """
        保存一条长期记忆。

        Args:
            user_id: 用户ID
            content: 记忆内容，如"用户是Java开发者"
            memory_type: 记忆类型，preference/fact/behavior
        """
        if not self._available:
            return
        try:
            embedding = await self._embeddings.aembed_query(content)
            self._client.insert(
                collection_name=COLLECTION_NAME,
                data=[{
                    "user_id": user_id,
                    "content": content,
                    "memory_type": memory_type,
                    "embedding": embedding,
                }]
            )
            logger.debug(
                "LongTermMemory: 保存 %s 记忆 user=%s: %s",
                memory_type, user_id, content[:60]
            )
        except Exception as exc:
            logger.error("LongTermMemory.save_memory 失败: %s", exc)

    async def save_preference(
        self,
        user_id: str,
        preference_type: str,
        value: str
    ) -> None:
        """
        保存用户偏好的便捷方法。

        Args:
            user_id: 用户ID
            preference_type: 偏好类型，如 "language"、"region"
            value: 偏好值，如 "Java"、"华北2"

        例子：
            await memory.save_preference("user_1001", "开发语言", "Java")
            await memory.save_preference("user_1001", "偏好地域", "华北2")
        """
        content = f"用户偏好 - {preference_type}：{value}"
        await self.save_memory(user_id, content, memory_type="preference")

    async def retrieve_relevant(
        self,
        user_id: str,
        query: str,
        top_k: int = 5
    ) -> list[str]:
        """
        根据当前问题，检索最相关的长期记忆。

        Args:
            user_id: 用户ID
            query: 当前问题
            top_k: 返回最相关的几条记忆

        Returns:
            相关记忆内容列表
        """
        if not self._available:
            return []
        try:
            query_embedding = await self._embeddings.aembed_query(query)
            results = self._client.search(
                collection_name=COLLECTION_NAME,
                data=[query_embedding],
                filter=f'user_id == "{user_id}"',
                limit=top_k,
                output_fields=["content", "memory_type"],
            )

            memories: list[str] = []
            for hits in results:
                for hit in hits:
                    memories.append(hit["entity"]["content"])
            return memories

        except Exception as exc:
            logger.error("LongTermMemory.retrieve_relevant 失败: %s", exc)
            return []

    async def get_all(self, user_id: str) -> list[dict]:
        """获取用户所有长期记忆"""
        if not self._available:
            return []
        try:
            rows = self._client.query(
                collection_name=COLLECTION_NAME,
                filter=f'user_id == "{user_id}"',
                output_fields=["content", "memory_type"],
                limit=100,
            )
            return rows or []
        except Exception as exc:
            logger.warning("LongTermMemory.get_all 失败: %s", exc)
            return []

    async def clear(self, user_id: str) -> None:
        """清除用户所有长期记忆"""
        if not self._available:
            return
        try:
            self._client.delete(
                collection_name=COLLECTION_NAME,
                filter=f'user_id == "{user_id}"'
            )
        except Exception as exc:
            logger.error("LongTermMemory.clear 失败: %s", exc)

    @property
    def available(self) -> bool:
        return self._available

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    def _ensure_collection(self) -> None:
        """确保 collection 存在，不存在则创建"""
        from pymilvus import DataType

        if self._client.has_collection(COLLECTION_NAME):
            return

        schema = self._client.create_schema()
        schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field("user_id", DataType.VARCHAR, max_length=128)
        schema.add_field("content", DataType.VARCHAR, max_length=2048)
        schema.add_field("memory_type", DataType.VARCHAR, max_length=64)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)

        index_params = self._client.prepare_index_params()
        index_params.add_index(
            "embedding",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 128},
        )

        self._client.create_collection(
            collection_name=COLLECTION_NAME,
            schema=schema,
            index_params=index_params,
        )
        logger.info("LongTermMemory: 创建 collection '%s'", COLLECTION_NAME)