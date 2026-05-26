
# 作用：知识图谱查询工具
# 用于查询产品关系、实例规格、地域可用区等结构化数据
# 使用 GraphCypherQAChain 自动把自然语言转成 Cypher 查询

import os
import re
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool

# 加载环境变量
dotenv_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'
)
load_dotenv(dotenv_path)

# 全局单例，避免每次调用重复连接数据库
_graph_chain_instance = None
_graph_instance = None


def _get_graph_chain():
    """获取 GraphCypherQAChain 单例"""
    global _graph_chain_instance, _graph_instance
    if _graph_chain_instance is not None:
        return _graph_chain_instance

    print("🔌 [GraphTool] 正在连接 Neo4j 数据库...")

    graph = Neo4jGraph(
        url=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        username=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "cloudmind123"),
        database=os.getenv("NEO4J_DATABASE", "neo4j"),
    )
    _graph_instance = graph
    graph.refresh_schema()

    llm = ChatOpenAI(
        api_key=os.getenv("SILICONFLOW_API_KEY"),
        base_url=os.getenv("SILICONFLOW_BASE_URL"),
        model=os.getenv("MODEL", "deepseek-ai/DeepSeek-V3"),
        temperature=0,
    )

    # Cypher 生成提示词
    CYPHER_GENERATION_TEMPLATE = """Task: Generate Cypher statement to query a graph database.
Instructions:
Use only the provided relationship types and properties in the schema.
Do not use any other relationship types or properties that are not provided.

Schema:
{schema}

Important Rules:
1. 节点标签: Region, Zone, InstanceTypeFamily, InstanceType, Storage, BillingRule 等
2. 注意属性访问: 必须给节点赋予变量名才能访问属性
   错误: MATCH (:InstanceType {{id: "g8a"}}) RETURN vcpu
   正确: MATCH (n {{id: "ecs.g8a.xlarge"}}) RETURN n.`Max ENI Quantity`
3. 注意实体层级:
   g8a, c7 这种属于 InstanceTypeFamily（规格族）
   ecs.g8a.xlarge 这种具体型号才属于 InstanceType（实例规格）
4. 属性名可能包含空格，必须用反引号包裹，例如：
   n.`Max ENI Quantity`  （弹性网卡数量）
   n.`Memory`           （内存）
   n.`CPU`              （CPU数量）
5. 查询实例属性时，直接 MATCH (n {{id: "实例ID"}}) RETURN properties(n) 获取所有属性
6. 返回格式: 尽可能详细，返回节点时用 RETURN node 而不是只返回 ID

The question is:
{question}"""

    cypher_prompt = PromptTemplate(
        template=CYPHER_GENERATION_TEMPLATE,
        input_variables=["schema", "question"]
    )

    _graph_chain_instance = GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        cypher_prompt=cypher_prompt,
        verbose=False,
        return_intermediate_steps=False,
        allow_dangerous_requests=True,
    )

    print("✅ [GraphTool] Neo4j 连接成功")
    return _graph_chain_instance


def _extract_keywords(query: str) -> list[str]:
    """从查询中提取关键词，用于兜底搜索"""
    lower_query = query.lower()
    tokens = re.findall(r"[a-z0-9._-]+", lower_query)
    cn_tokens = re.findall(r"[\u4e00-\u9fff]{2,}", query)
    keywords = []
    for token in tokens + cn_tokens:
        if len(token.strip()) >= 2 and token not in keywords:
            keywords.append(token.strip())
    if not keywords:
        keywords.append(lower_query[:20] if lower_query else "ecs")
    return keywords[:8]


def _fallback_graph_keyword_search(query: str) -> str:
    """
    关键词兜底搜索。
    GraphCypherQAChain 失败时，直接用关键词搜索节点和关系。
    防止完全查不到数据。
    """
    global _graph_instance
    if _graph_instance is None:
        _get_graph_chain()

    graph = _graph_instance
    if graph is None:
        return "图谱关键词检索不可用，请稍后重试。"

    keywords = _extract_keywords(query)

    node_cypher = """
    MATCH (n)
    WHERE any(k IN $keywords WHERE
        toLower(coalesce(n.id, '')) CONTAINS k OR
        toLower(coalesce(n.name, '')) CONTAINS k OR
        toLower(coalesce(n.description, '')) CONTAINS k
    )
    RETURN labels(n) AS labels, coalesce(n.id, n.name, '') AS node_key, properties(n) AS props
    LIMIT 8
    """

    rel_cypher = """
    MATCH (a)-[r]->(b)
    WHERE any(k IN $keywords WHERE
        toLower(coalesce(a.id, '')) CONTAINS k OR
        toLower(coalesce(a.name, '')) CONTAINS k OR
        toLower(coalesce(b.id, '')) CONTAINS k OR
        toLower(coalesce(b.name, '')) CONTAINS k
    )
    RETURN labels(a) AS from_labels, coalesce(a.id, a.name, '') AS from_node,
           type(r) AS rel, labels(b) AS to_labels, coalesce(b.id, b.name, '') AS to_node
    LIMIT 8
    """

    try:
        nodes = graph.query(node_cypher, params={"keywords": keywords})
        relations = graph.query(rel_cypher, params={"keywords": keywords})
    except Exception as exc:
        return f"图谱关键词检索失败: {str(exc)}"

    if not nodes and not relations:
        return "未查询到相关图谱信息。"

    parts = ["图谱关键词检索结果："]
    if nodes:
        parts.append("命中节点：")
        for row in nodes:
            labels = ",".join(row.get("labels", []))
            node_key = row.get("node_key", "")
            props = row.get("props", {})
            parts.append(f"- [{labels}] {node_key} {props}")
    if relations:
        parts.append("命中关系：")
        for row in relations:
            from_labels = ",".join(row.get("from_labels", []))
            to_labels = ",".join(row.get("to_labels", []))
            parts.append(
                f"- [{from_labels}] {row.get('from_node', '')} "
                f"-[{row.get('rel', '')}]-> "
                f"[{to_labels}] {row.get('to_node', '')}"
            )
    return "\n".join(parts)


@tool
def query_knowledge_graph(query: str) -> str:
    """
    查询云产品知识图谱。
    当用户询问云产品的架构、包含关系、配置限制时使用此工具。
    例如：
    - ecs.g8a.xlarge 能挂载几块网卡？
    - 北京可用区有哪些实例？
    - 退款有什么限制？
    - 某个实例支持哪些存储类型？

    Args:
        query: 明确的自然语言查询句子
    """
    try:
        chain = _get_graph_chain()
        result = chain.invoke({"query": query})
        answer = result.get('result', "")
        
        # 如果主链没找到或返回不确定的答案，用 fallback 补充
        uncertain_phrases = ["没有找到", "无法", "不确定", "建议您查阅", "暂时没有", "没有具体"]
        if not answer or any(p in answer for p in uncertain_phrases):
            fallback = _fallback_graph_keyword_search(query)
            if fallback and "失败" not in fallback:
                return fallback
        
        return answer if answer else "未找到相关图谱信息。"

    except Exception as e:
        fallback_result = _fallback_graph_keyword_search(query)
        if fallback_result and "失败" not in fallback_result:
            return fallback_result
        return f"查询图谱时发生错误: {str(e)}"
