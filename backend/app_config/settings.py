
# 作用：统一管理所有配置
# 使用 pydantic_settings 自动从 .env 读取并做类型校验

import os
from pydantic_settings import BaseSettings, SettingsConfigDict

# 读取 backend/.env
ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


class Settings(BaseSettings):
    # AI 模型
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    dashscope_api_key: str = ""
    model: str = "deepseek-ai/DeepSeek-V3"

    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_ttl: int = 1800

    # Milvus
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_api_key: str = ""

    # MySQL
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "cloud_platform"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "cloudmind123"
    neo4j_database: str = "neo4j"

    # API
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    cors_origin_regex: str = r"http://(localhost|127\.0\.0\.1):\d+"

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        extra='ignore'      # 忽略 .env 里多余的字段
    )


# 全局单例
settings = Settings()
