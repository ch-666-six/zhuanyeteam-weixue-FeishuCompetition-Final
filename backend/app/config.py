from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_secret_key: str = Field(
        default="development-only-secret-change-me",
        min_length=32,
    )
    database_url: str = "postgresql+psycopg://weixue:weixue@localhost:5432/weixue"
    frontend_origin: str = "http://localhost:5173"
    access_token_expire_minutes: int = 480
    # Production interactions must always use a real model provider.
    ai_provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    ai_worker_enabled: bool = True
    ai_worker_poll_seconds: float = Field(default=1.0, ge=0.1, le=60)
    ai_job_lease_seconds: int = Field(default=90, ge=10, le=600)
    ai_job_max_attempts: int = Field(default=3, ge=1, le=10)


@lru_cache
def get_settings() -> Settings:
    return Settings()
