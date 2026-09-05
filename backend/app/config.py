from pathlib import Path

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

    # 图片识别视觉模型（与主 LLM 分离，托管于 openai-next）
    LLM_VISION_ENDPOINT: str = "https://api.openai-next.com/v1"
    LLM_VISION_API_KEY: str = ""
    LLM_VISION_MODEL: str = "deepseek-v4-flash-vision-exp"

    # ASR/TTS
    ASR_ENDPOINT: str = "http://localhost:8200"
    TTS_ENDPOINT: str = "http://localhost:8300"
    ASR_TIMEOUT: float = 30.0
    TTS_TIMEOUT: float = 30.0
    TTS_DEFAULT_SPEED: float = 0.85

    # 语音运行时目录与默认音色
    VOICE_RUNTIME_DIR: str = ""
    DEFAULT_VOICE_REF: str = ""
    DEFAULT_VOICE_REF_TEXT: str = ""

    # Web Push (VAPID)
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_CONTACT: str = "admin@example.com"

    # Server
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    @property
    def voice_runtime_dir(self) -> Path:
        """返回 voice-runtime 绝对路径（仓库根）"""
        from pathlib import Path
        if self.VOICE_RUNTIME_DIR:
            return Path(self.VOICE_RUNTIME_DIR).resolve()
        return Path(__file__).resolve().parent.parent.parent / "voice-runtime"

    @property
    def default_voice_ref(self) -> Path:
        """默认音色参考音频路径"""
        if self.DEFAULT_VOICE_REF:
            return Path(self.DEFAULT_VOICE_REF)
        return self.voice_runtime_dir / "refs" / "default.wav"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()