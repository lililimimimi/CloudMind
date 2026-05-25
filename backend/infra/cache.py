
# 作用：语义缓存
# 把问过的问题和答案存在 Milvus 里
# 下次有相似问题直接返回缓存，不走 Agent 工作流
# 节省时间和 token

from __future__ import annotations
from typing import Any
from app_config.settings import settings

COLLECTION_NAME = "qa_semantic_cache"
EMBEDDING_DIM = 1024
L1_SEMANTIC_DISTANCE_THRESHOLD = 0.08


class SemanticCache:
    """
    语义缓存。
    支持两种命中：
    - L1_EXACT：完全匹配（问题规范化后完全一样）
    - L1_SEMANTIC：语义匹配（向量相似度超过阈值）

    支持两种范围：
    - public：所有用户共享（适合通用问题）
    - user：用户专属（适合个人数据查询）
    """

    def __init__(self) -> None:
        self._client: Any = None
        self._embeddings: Any = None
        self._available: bool = False

    async def initialize(self) -> None:
        """初始化 Milvus 连接，失败不抛异常"""
        try:
            from pymilvus import MilvusClient
            from langchain_openai import OpenAIEmbeddings

            connect_kwargs: dict[str, Any] = {
                "uri": f"http://{settings.milvus_host}:{settings.milvus_port}"
            }
            if settings.milvus_api_key:
                connect_kwargs["token"] = settings.milvus_api_key

            self._client = MilvusClient(**connect_kwargs)

            # 用硅基流动的 embedding API
            self._embeddings = OpenAIEmbeddings(
                model="BAAI/bge-m3",
                api_key=settings.siliconflow_api_key or settings.dashscope_api_key,
                base_url="https://api.siliconflow.cn/v1"
            )

            # 确保 collection 存在
            self._ensure_collection()
            self._available = True
            print("[SemanticCache] 初始化成功")

        except Exception as exc:
            print(f"[SemanticCache] 初始化失败，语义缓存已禁用：{exc}")
            self._available = False

    async def get_cache(
        self,
        query: str,
        user_id: str
    ) -> dict[str, Any] | None:
        """
        查询语义缓存。
        先查精确匹配，再查语义匹配。
        未命中返回 None。
        """
        if not self._available:
            return None

        normalized = self._normalize(query)
        safe_norm = normalized.replace('"', '\\"')
        safe_user = user_id.replace('"', '\\"')

        # 1. 精确匹配：用户专属
        user_filter = (
            f'enabled == 1 and question_norm == "{safe_norm}" '
            f'and scope == "user" and user_id == "{safe_user}"'
        )
        user_exact = self._query_one(user_filter)
        if user_exact:
            return {
                "answer": user_exact["answer"],
                "matched_question": user_exact["question"],
                "level": "L1_EXACT",
                "distance": 0.0,
            }

        # 2. 精确匹配：公共缓存
        public_filter = (
            f'enabled == 1 and question_norm == "{safe_norm}" '
            f'and scope == "public"'
        )
        public_exact = self._query_one(public_filter)
        if public_exact:
            return {
                "answer": public_exact["answer"],
                "matched_question": public_exact["question"],
                "level": "L1_EXACT",
                "distance": 0.0,
            }

        # 3. 语义匹配
        try:
            query_embedding = await self._embeddings.aembed_query(normalized)
            scoped_filter = (
                f'enabled == 1 and '
                f'(scope == "public" or (scope == "user" and user_id == "{safe_user}"))'
            )
            results = self._client.search(
                collection_name=COLLECTION_NAME,
                data=[query_embedding],
                filter=scoped_filter,
                limit=1,
                output_fields=["question", "answer", "scope", "user_id"],
            )

            if not results or not results[0]:
                return None

            hit = results[0][0] if results[0] else None
            if not hit:
                return None

            distance = float(hit.get("distance", 1.0))

            # COSINE 距离：越小越相似，超过阈值说明不相似
            if distance > L1_SEMANTIC_DISTANCE_THRESHOLD:
                return None

            entity = hit.get("entity", {})
            return {
                "answer": entity.get("answer", ""),
                "matched_question": entity.get("question", ""),
                "level": "L1_SEMANTIC",
                "distance": distance,
            }

        except Exception as exc:
            print(f"[SemanticCache] 语义查询失败：{exc}")
            return None

    async def set_cache(
        self,
        query: str,
        response: str,
        user_id: str | None = None,
        scope: str = "public",
    ) -> None:
        """
        把问题和答案存入缓存。
        有个人数据时用 scope="user"，通用问题用 scope="public"。
        """
        if not self._available:
            return

        normalized = self._normalize(query)
        owner = user_id or ""
        cache_scope = "user" if owner else scope

        try:
            embedding = await self._embeddings.aembed_query(normalized)

            # 先删旧的，避免重复
            safe_norm = normalized.replace('"', '\\"')
            safe_scope = cache_scope.replace('"', '\\"')
            safe_owner = owner.replace('"', '\\"')
            delete_filter = (
                f'question_norm == "{safe_norm}" '
                f'and scope == "{safe_scope}" '
                f'and user_id == "{safe_owner}"'
            )
            self._client.delete(
                collection_name=COLLECTION_NAME,
                filter=delete_filter
            )

            # 存入新的
            self._client.insert(
                collection_name=COLLECTION_NAME,
                data=[{
                    "question": query.strip(),
                    "question_norm": normalized,
                    "answer": response,
                    "scope": cache_scope,
                    "user_id": owner,
                    "enabled": 1,
                    "embedding": embedding,
                }]
            )

            print(f"[SemanticCache] 已缓存：{query[:30]}...")

        except Exception as exc:
            print(f"[SemanticCache] 存入失败：{exc}")

    @property
    def available(self) -> bool:
        return self._available

    @staticmethod
    def _normalize(text: str) -> str:
        """规范化查询词，去掉多余空格和大小写差异"""
        return " ".join(text.strip().lower().split())

    def _query_one(self, filter_expr: str) -> dict[str, Any] | None:
        """精确查询一条记录"""
        try:
            rows = self._client.query(
                collection_name=COLLECTION_NAME,
                filter=filter_expr,
                output_fields=["question", "answer", "scope", "user_id"],
                limit=1,
            )
            return rows[0] if rows else None
        except Exception:
            return None

    def _ensure_collection(self) -> None:
        """确保 collection 存在，不存在则创建"""
        from pymilvus import DataType

        if self._client.has_collection(COLLECTION_NAME):
            return

        schema = self._client.create_schema()
        schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field("question", DataType.VARCHAR, max_length=2048)
        schema.add_field("question_norm", DataType.VARCHAR, max_length=2048)
        schema.add_field("answer", DataType.VARCHAR, max_length=8192)
        schema.add_field("scope", DataType.VARCHAR, max_length=16)
        schema.add_field("user_id", DataType.VARCHAR, max_length=128)
        schema.add_field("enabled", DataType.INT8)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)

        index_params = self._client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 256},
        )

        self._client.create_collection(
            collection_name=COLLECTION_NAME,
            schema=schema,
            index_params=index_params,
        )
        print(f"[SemanticCache] 创建 collection：{COLLECTION_NAME}")


# 全局实例
semantic_cache = SemanticCache()