from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # PostgreSQL
    DATABASE_URL: str

    # MinIO
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET_MEMORIES: str = "memories"
    MINIO_BUCKET_VOICE: str = "voice"
    MINIO_BUCKET_AVATARS: str = "avatars"
    MINIO_BUCKET_ASSETS: str = "asset-packs"

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_DAYS: int = 30

    # LLM (OpenAI Next)
    LLM_ENDPOINT: str
    LLM_API_KEY: str
    LLM_MODEL: str
    LLM_PROVIDER: str

    # ASR/TTS
    ASR_ENDPOINT: str
    TTS_ENDPOINT: str

    # Web Push (VAPID)
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_CONTACT: str = "admin@example.com"

    # Server
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()