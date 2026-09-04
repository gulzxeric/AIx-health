from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "RetinaEcho API"
    api_version: str = "0.1.0"
    database_url: str = (
        "postgresql+asyncpg://retinaecho:retinaecho_dev@localhost:5432/retinaecho"
    )
    redis_url: str = "redis://localhost:6379/0"
    jwt_signing_key: SecretStr = SecretStr(
        "development-only-signing-key-change-before-production"
    )
    data_encryption_key: SecretStr | None = None
    lookup_hash_key: SecretStr = SecretStr(
        "development-only-lookup-key-change-before-production"
    )
    otp_provider: Literal["test", "sms"] = "test"
    test_otp_code: SecretStr | None = None
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:5174"]
    )
    agnes_api_key: SecretStr | None = None
    agnes_base_url: str = "https://apihub.agnes-ai.com/v1"
    agnes_model: str = "agnes-2.5-flash"
    llm_provider: str = "agnes"

    @model_validator(mode="after")
    def reject_test_configuration_in_production(self) -> "Settings":
        if self.app_env == "production" and self.otp_provider == "test":
            raise ValueError("The test OTP provider is forbidden in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

