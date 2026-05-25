# agent/tools/vector_tool.py
import os
import json
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_milvus import Milvus
from pymilvus import connections
from langchain_core.tools import tool

# 修复 pymilvus 2.6.x 与 langchain-milvus 0.3.x 兼容性问题
original_fetch = connections._fetch_handler
def patched_fetch(alias):
    try:
        return original_fetch(alias)
    except Exception:
        from pymilvus.client.connection_manager import ConnectionManager
        mgr = ConnectionManager.get_instance()
        for mc in mgr._registry.values():
            if f"cm-{id(mc.handler)}" == alias:
                return mc.handler
        for mc in mgr._dedicated.values():
            if f"cm-{id(mc.handler)}" == alias:
                return mc.handler
        raise
connections._fetch_handler = patched_fetch

dotenv_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'
)
load_dotenv(dotenv_path)

# 全局单例
_milvus_instance = None


def _get_milvus_store():
    """获取 Milvus 向量库单例"""
    global _milvus_instance
    if _milvus_instance is not None:
        return _milvus_instance

    api_key = os.getenv("SILICONFLOW_API_KEY")
    milvus_host = os.getenv("MILVUS_HOST", "localhost")
    milvus_port = os.getenv("MILVUS_PORT", "19530")
    milvus_uri = f"http://{milvus_host}:{milvus_port}"

    print(f"🔌 [VectorTool] 正在连接 Milvus: {milvus_uri}")

    # 用硅基流动的 embedding API，不需要本地下载模型
    embeddings = OpenAIEmbeddings(
        model="BAAI/bge-m3",
        api_key=api_key,
        base_url="https://api.siliconflow.cn/v1"
    )

    _milvus_instance = Milvus(
        embedding_function=embeddings,
        connection_args={"uri": milvus_uri},
        collection_name="cloud_product_docs",
        auto_id=True,
        drop_old=False
    )

    print("✅ [VectorTool] Milvus 连接成功")
    return _milvus_instance


@tool
def query_vector_db(query: str) -> str:
    """
    通过语义搜索查询云产品说明文档（RAG）。
    当用户询问概念解释、操作步骤、详细规则时使用。
    例如：
    - 退款规则有哪些限制？
    - 什么是专有网络VPC？
    - 包年包月和按量付费怎么选？
    - 安全组怎么配置？

    Args:
        query: 用户的自然语言问题
    """
    try:
        store = _get_milvus_store()
        results = store.similarity_search_with_score(query, k=5)

        if not results:
            return "未在文档中检索到相关信息。"

        formatted_results = []
        for doc, score in results:
            source = os.path.basename(doc.metadata.get('source', '未知来源'))
            content = doc.page_content.strip()
            formatted_results.append(f"【来源: {source}】\n{content}")

        return "\n\n".join(formatted_results)

    except Exception as e:
        return f"向量检索失败: {str(e)}"