
# 作用：把 mock_data/ecs_product_info.json 导入 Neo4j 知识图谱
# 运行一次即可，数据会持久化在 Neo4j 里

import os
import json
from dotenv import load_dotenv
from neo4j import GraphDatabase

# 加载环境变量
dotenv_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'
)
load_dotenv(dotenv_path)


def build_knowledge_graph():
    """
    把 ecs_product_info.json 里的节点和关系导入 Neo4j。
    节点：Region、Zone、InstanceType、Storage 等
    关系：CONTAINS、HAS_SPEC、HAS_NETWORK 等
    """

    # 读取数据文件
    data_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'mock_data', 'ecs_product_info.json'
    )

    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    nodes = data.get('nodes', [])
    edges = data.get('edges', [])

    print(f"📊 节点数量：{len(nodes)}")
    print(f"🔗 关系数量：{len(edges)}")

    # 连接 Neo4j
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(
            os.getenv("NEO4J_USER", "neo4j"),
            os.getenv("NEO4J_PASSWORD", "cloudmind123")
        )
    )

    with driver.session() as session:

        # 清空旧数据
        print("🗑️  清空旧数据...")
        session.run("MATCH (n) DETACH DELETE n")

        # 导入节点
        print("📥 导入节点...")
        for node in nodes:
            node_id = node['id']
            label = node['label']
            properties = {p['key']: p['value'] for p in node.get('properties', [])}
            properties['id'] = node_id

            # 动态创建不同 label 的节点
            cypher = f"MERGE (n:{label} {{id: $id}}) SET n += $props"
            session.run(cypher, id=node_id, props=properties)

        print(f"✅ 导入了 {len(nodes)} 个节点")

        # 导入关系
        print("📥 导入关系...")
        for edge in edges:
            source = edge['source']
            target = edge['target']
            rel_type = edge['type']

            cypher = f"""
            MATCH (a {{id: $source}})
            MATCH (b {{id: $target}})
            MERGE (a)-[:{rel_type}]->(b)
            """
            session.run(cypher, source=source, target=target)

        print(f"✅ 导入了 {len(edges)} 条关系")

    driver.close()
    print("🎉 知识图谱构建完成！")


if __name__ == "__main__":
    build_knowledge_graph()