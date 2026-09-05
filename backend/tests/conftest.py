import os

# 在应用模块导入前设好环境变量默认值
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/t")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("LLM_ENDPOINT", "https://api.test/v1")
os.environ.setdefault("LLM_API_KEY", "sk-test")
os.environ.setdefault("LLM_MODEL", "test-model")
os.environ.setdefault("LLM_PROVIDER", "test")
