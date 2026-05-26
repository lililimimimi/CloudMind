
# 作用：把 mock_data/ 下的 .md 文档导入 Milvus 向量库
# 运行一次即可，数据会持久化在 Milvus 里

import os
import glob
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_milvus import Milvus
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pymilvus import connections

# 修复兼容性问题
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


def build_vector_db():
    """
    把 mock_data/ 下所有 .md 文件导入 Milvus 向量库。
    使用 RecursiveCharacterTextSplitter 把长文档切成小块。
    每块约500字，块间重叠50字，保证上下文连贯。
    """

    # 找到所有 .md 文件
    mock_data_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'mock_data'
    )
    md_files = glob.glob(os.path.join(mock_data_path, '*.md'))

    if not md_files:
        print("❌ 没有找到 .md 文件，请检查 mock_data/ 目录")
        return

    print(f"📄 找到 {len(md_files)} 个文档：")
    for f in md_files:
        print(f"  - {os.path.basename(f)}")

    # 加载所有文档
    all_docs = []
    for file_path in md_files:
        loader = TextLoader(file_path, encoding='utf-8')
        docs = loader.load()
        # 给每个文档加上来源标记
        for doc in docs:
            doc.metadata['source'] = os.path.basename(file_path)
        all_docs.extend(docs)

    print(f"\n📚 共加载 {len(all_docs)} 个文档")

    # 切割文档
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=200,      
        chunk_overlap=50,     # 块间重叠50字，保证上下文连贯
        length_function=len,
    )
    chunks = splitter.split_documents(all_docs)
    print(f"✂️  切割成 {len(chunks)} 个文本块")

    # 初始化 embedding 模型
    api_key = os.getenv("SILICONFLOW_API_KEY")
    embeddings = OpenAIEmbeddings(
        model="BAAI/bge-m3",
        api_key=api_key,
        base_url="https://api.siliconflow.cn/v1"
    )

    # 连接 Milvus 并导入
    milvus_host = os.getenv("MILVUS_HOST", "localhost")
    milvus_port = os.getenv("MILVUS_PORT", "19530")
    milvus_uri = f"http://{milvus_host}:{milvus_port}"

    print(f"\n📥 正在导入到 Milvus ({milvus_uri})...")

    # drop_old=True 清空旧数据重新导入
    Milvus.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name="cloud_product_docs",
        connection_args={"uri": milvus_uri},
        drop_old=True,
    )

    print(f"🎉 向量库构建完成！共导入 {len(chunks)} 个文本块")


if __name__ == "__main__":
    build_vector_db()