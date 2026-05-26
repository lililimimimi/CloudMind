
# 作用：MCP 工具服务，提供查询真实数据库的工具
# billing_agent 和 finops_agent 通过这些工具查询真实数据

import os
import pymysql
import json
import requests
import sys
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# 加载 agent/.env 环境变量
dotenv_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'
)
load_dotenv(dotenv_path)
print(f"[MCP] DASHSCOPE_API_KEY={'已配置' if os.getenv('DASHSCOPE_API_KEY') else '未配置'}", file=sys.stderr)

# 初始化 MCP 服务
mcp = FastMCP("CloudPlatformMCPServer")

FALLBACK_POSTER_URL = "/posters/cloudmind-ecs-poster.svg"


# -------------------------------------------------------
# 数据库连接
# -------------------------------------------------------
def get_db_connection():
    """获取 MySQL 连接，查完记得关闭"""
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "cloud_platform"),
        cursorclass=pymysql.cursors.DictCursor,  # 返回字典格式
        charset="utf8mb4",
    )


# -------------------------------------------------------
# 产品目录（静态数据，后面可以接数据库）
# -------------------------------------------------------
PRODUCT_CATALOG = {
    "P_ECS_G8A_XLARGE": {
        "name": "第八代企业级通用型实例 ecs.g8a.xlarge",
        "keywords": ["ecs", "云服务器", "通用型", "g8a", "4核16g", "amd"],
        "price": 299.0,
    },
    "P_ECS_C7_8XLARGE": {
        "name": "第七代企业级计算型实例 ecs.c7.8xlarge",
        "keywords": ["ecs", "云服务器", "计算型", "c7", "32核64g", "高并发"],
        "price": 1299.0,
    },
    "P_GPU_GN7I": {
        "name": "GPU 计算型实例 ecs.gn7i-c8g1.2xlarge",
        "keywords": ["gpu", "算力", "大模型", "a10", "深度学习", "推理"],
        "price": 3500.0,
    },
    "P_RDS_MYSQL_HA": {
        "name": "云数据库 RDS MySQL 高可用版",
        "keywords": ["rds", "mysql", "数据库", "高可用", "主备"],
        "price": 599.0,
    },
}


# -------------------------------------------------------
# 工具1：查询用户订单
# -------------------------------------------------------
@mcp.tool()
def query_user_orders(user_id: str, limit: int = 5) -> str:
    """
    查询用户的云服务订单和账单记录。

    Args:
        user_id: 用户ID，由系统自动注入，不允许模型伪造
        limit: 返回的最大记录数，默认5条
    """
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = """
                SELECT order_id, product_name, billing_mode,
                       amount, status,
                       DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at
                FROM cloud_orders
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """
            cursor.execute(sql, (user_id, limit))
            results = cursor.fetchall()

            if not results:
                return json.dumps({
                    "status": "success",
                    "message": "该用户暂无订单记录"
                }, ensure_ascii=False)

            # Decimal 转 float，避免 JSON 序列化报错
            for row in results:
                if row.get('amount') is not None:
                    row['amount'] = float(row['amount'])

            return json.dumps({
                "status": "success",
                "data": results
            }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"查询订单失败: {str(e)}"
        }, ensure_ascii=False)
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()


# -------------------------------------------------------
# 工具2：查询用户实例
# -------------------------------------------------------
@mcp.tool()
def query_user_instances(user_id: str, limit: int = 5) -> str:
    """
    查询用户的云资源实例列表。
    返回实例ID、规格、地域、状态、公网IP。

    Args:
        user_id: 用户ID，由系统自动注入
        limit: 返回的最大记录数，默认5条
    """
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = """
                SELECT instance_id, instance_type, region_id,
                       zone_id, public_ip, status
                FROM cloud_instances
                WHERE user_id = %s
                ORDER BY instance_id DESC
                LIMIT %s
            """
            cursor.execute(sql, (user_id, limit))
            results = cursor.fetchall()

            if not results:
                return json.dumps({
                    "status": "success",
                    "message": "未查询到您的实例数据"
                }, ensure_ascii=False)

            return json.dumps({
                "status": "success",
                "data": results
            }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"查询实例失败: {str(e)}"
        }, ensure_ascii=False)
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()


# -------------------------------------------------------
# 工具3：分析实例监控数据
# -------------------------------------------------------
@mcp.tool()
def analyze_instance_usage(instance_id: str, user_id: str = "") -> str:
    """
    查询实例近7天的监控数据，判断资源是否闲置。
    用于 FinOps 成本优化分析场景。

    Args:
        instance_id: 实例ID，需先通过 query_user_instances 查出
        user_id: 用户ID，由系统自动注入，用于安全鉴权
    """
    if not instance_id:
        return json.dumps({
            "status": "error",
            "message": "必须提供实例ID"
        }, ensure_ascii=False)

    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:

            # 先验证实例归属，防止越权查询
            cursor.execute("""
                SELECT instance_id FROM cloud_instances
                WHERE instance_id = %s AND user_id = %s LIMIT 1
            """, (instance_id, user_id))

            if not cursor.fetchone():
                return json.dumps({
                    "status": "error",
                    "message": "未找到该实例，或您无权查看该实例监控数据"
                }, ensure_ascii=False)

            # 查询近7天监控数据
            cursor.execute("""
                SELECT
                    ROUND(AVG(avg_cpu_usage_percent), 2) AS cpu_usage_percent,
                    ROUND(AVG(avg_memory_usage_percent), 2) AS memory_usage_percent,
                    ROUND(MAX(max_network_out_mbps), 2) AS network_out_bandwidth_mbps,
                    COUNT(*) AS days_count
                FROM instance_metrics_daily
                WHERE instance_id = %s AND user_id = %s
                  AND metric_date >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
            """, (instance_id, user_id))

            agg = cursor.fetchone()

            if not agg or not agg.get("days_count"):
                return json.dumps({
                    "status": "error",
                    "message": "未查询到近7天监控数据"
                }, ensure_ascii=False)

            cpu = float(agg["cpu_usage_percent"] or 0)
            memory = float(agg["memory_usage_percent"] or 0)
            bandwidth = float(agg["network_out_bandwidth_mbps"] or 0)

            # 自动诊断资源状态
            if cpu < 10 and memory < 30:
                diagnosis = "RESOURCES_IDLE"    # 资源闲置，建议降配
            elif cpu > 70 or memory > 80:
                diagnosis = "RESOURCES_TIGHT"   # 资源紧张，建议升配
            else:
                diagnosis = "RESOURCES_NORMAL"  # 资源正常

            return json.dumps({
                "status": "success",
                "data": {
                    "instance_id": instance_id,
                    "owner_id": user_id,
                    "metrics_7d_avg": {
                        "cpu_usage_percent": cpu,
                        "memory_usage_percent": memory,
                        "network_out_bandwidth_mbps": bandwidth,
                    },
                    "diagnosis": diagnosis,
                }
            }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"查询监控数据失败: {str(e)}"
        }, ensure_ascii=False)
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()


# -------------------------------------------------------
# 工具4：搜索产品目录
# -------------------------------------------------------
@mcp.tool()
def search_product_catalog(keyword: str) -> str:
    print(f"[search_product_catalog] keyword={keyword}", file=sys.stderr)
    """
    根据关键词搜索云产品目录，，模糊搜索并返回符合条件的产品信息及【产品ID】

    Args:
        keyword: 产品关键词，如 "云服务器"、"GPU"、"数据库"
    """
    results = []
    kw_lower = keyword.lower()

    for pid, pinfo in PRODUCT_CATALOG.items():
        name_lower = pinfo["name"].lower()
        keywords = pinfo["keywords"]
        
        # 双向匹配：关键词包含产品名 或 产品名包含关键词
        # 或者关键词包含任意一个 keyword 标签
        matched = (
            kw_lower in name_lower or
            name_lower in kw_lower or
            any(k in kw_lower for k in keywords) or  # 改成反向：keyword 在搜索词里
            any(kw_lower in k for k in keywords)
        )
        
        if matched:
            results.append({
                "product_id": pid,
                "product_name": pinfo["name"],
                "price": pinfo["price"]
            })


    print(f"[search_product_catalog] results={results}", file=sys.stderr)
    if not results:
        return json.dumps({
            "status": "not_found",
            "message": f"未找到匹配 '{keyword}' 的产品",
            "recommendation": {
                "product_id": "P_ALL_000",
                "product_name": "全场通用云产品活动"
            }
        }, ensure_ascii=False)

    return json.dumps({
        "status": "success",
        "data": results
    }, ensure_ascii=False)


# -------------------------------------------------------
# 工具5：获取推广物料
# -------------------------------------------------------
@mcp.tool()
def get_promotion_materials(product_name: str, user_id: str = "") -> str:
    """
    根据产品名称获取推广链接、海报和返佣信息。
    必须先调用 search_product_catalog 获得精确的 product_id 后再调用此工具。

    Args:
        product_name: 产品名称，如 "ECS"、"GPU"、"RDS"
        user_id: 用户ID，由系统注入，用于生成专属推广链接
    """
    promotions = {
        "ecs": {
            "title": "云服务器 ECS 新人特惠",
            "desc": "标准型 2核4G 实例，首年仅需 99 元",
            "base_link": "https://promotion.cloud.com/ecs-new-user",
            "poster": FALLBACK_POSTER_URL,
            "commission_rate": "15%"
        },
        "gpu": {
            "title": "GPU 算力特惠季",
            "desc": "A10/V100 多款 GPU 实例，首单立减 500 元",
            "base_link": "https://promotion.cloud.com/gpu-ai-special",
            "poster": FALLBACK_POSTER_URL,
            "commission_rate": "20%"
        },
        "default": {
            "title": "云上全家桶满减活动",
            "desc": "全场云产品满 1000 减 100",
            "base_link": "https://promotion.cloud.com/all-in-one",
            "poster": FALLBACK_POSTER_URL,
            "commission_rate": "10%"
        }
    }

    product_lower = product_name.lower()
    key = "default"
    if "ecs" in product_lower or "服务器" in product_lower:
        key = "ecs"
    elif "gpu" in product_lower or "算力" in product_lower:
        key = "gpu"

    promo = promotions[key]

    # 用 user_id 生成专属推广链接
    exclusive_link = f"{promo['base_link']}?inviter={user_id}" \
        if user_id else promo['base_link']

    return json.dumps({
        "status": "success",
        "data": {
            "activity_title": promo["title"],
            "selling_points": promo["desc"],
            "exclusive_link": exclusive_link,
            "poster_url": promo["poster"],
            "commission_rate": promo["commission_rate"]
        }
    }, ensure_ascii=False)


# -------------------------------------------------------
# 工具6：生成 AI 海报
# -------------------------------------------------------
@mcp.tool()
def generate_ai_poster(prompt: str) -> str:
    """
    根据描述生成 AI 推广海报。
    使用阿里云百炼通义万相模型生成图片。

    Args:
        prompt: 海报描述，如 "生成一张云服务器推广海报，蓝色科技风"
    """
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        return json.dumps({
            "status": "success",
            "data": {
                "poster_url": FALLBACK_POSTER_URL,
                "message": "未配置 DASHSCOPE_API_KEY，已使用本地兜底海报",
                "fallback": True,
                "prompt": prompt
            }
        }, ensure_ascii=False)

    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable"   # 开启异步模式
    }

    # 构建海报 prompt
    enhanced_prompt = f"云计算平台推广海报，{prompt}，无任何文字，纯视觉背景，4k高清，蓝色科技风，突出云服务器和GPU算力的特点，适合社交媒体分享"

    payload = {
        "model": "wanx2.1-t2i-plus",  # 通义万相最新模型，速度快质量好
        "input": {
            "prompt": enhanced_prompt,
            "negative_prompt": "低质量，模糊，水印，变形"
        },
        "parameters": {
            "size": "1024*1024",
            "n": 1,               # 生成1张
        }
    }

    try:
        sys.stderr.write(f"[AI-POSTER] 提交生成任务，prompt: {prompt}\n")

        # 第一步：提交任务
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30
        )
        data = response.json()

        if response.status_code != 200:
            error_msg = data.get("message", f"HTTP {response.status_code}")
            return json.dumps({
                "status": "error",
                "message": f"提交任务失败: {error_msg}"
            }, ensure_ascii=False)

        # 取出任务 ID
        task_id = data.get("output", {}).get("task_id")
        if not task_id:
            return json.dumps({
                "status": "error",
                "message": "未获取到任务ID"
            }, ensure_ascii=False)

        sys.stderr.write(f"[AI-POSTER] 任务已提交，task_id: {task_id}\n")

        # 第二步：轮询任务结果
        poll_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
        poll_headers = {"Authorization": f"Bearer {api_key}"}

        for attempt in range(30):  # 最多等30次，每次2秒
            import time
            time.sleep(2)

            poll_response = requests.get(poll_url, headers=poll_headers, timeout=10)
            poll_data = poll_response.json()

            task_status = poll_data.get("output", {}).get("task_status")
            sys.stderr.write(f"[AI-POSTER] 轮询第{attempt+1}次，状态: {task_status}\n")

            if task_status == "SUCCEEDED":
                # 取出图片 URL
                results = poll_data.get("output", {}).get("results", [])
                if results:
                    image_url = results[0].get("url", "")
                    sys.stderr.write(f"[AI-POSTER] 生成成功: {image_url}\n")
                    return json.dumps({
                        "status": "success",
                        "data": {
                            "poster_url": image_url,
                            "message": "海报生成成功",
                            "prompt": prompt
                        }
                    }, ensure_ascii=False)

            elif task_status == "FAILED":
                error_msg = poll_data.get("output", {}).get("message", "生成失败")
                return json.dumps({
                    "status": "error",
                    "message": f"海报生成失败: {error_msg}"
                }, ensure_ascii=False)

        # 超时
        return json.dumps({
            "status": "success",
            "data": {
                "poster_url": FALLBACK_POSTER_URL,
                "message": "海报生成超时，已使用本地兜底海报",
                "fallback": True,
                "prompt": prompt
            }
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "status": "success",
            "data": {
                "poster_url": FALLBACK_POSTER_URL,
                "message": f"海报生成出错，已使用本地兜底海报: {str(e)}",
                "fallback": True,
                "prompt": prompt
            }
        }, ensure_ascii=False)


# -------------------------------------------------------
# 启动入口
# -------------------------------------------------------
if __name__ == "__main__":
    sys.stderr.write("🚀 CloudMind MCP Server 启动 (stdio 模式)...\n")
    mcp.run()
