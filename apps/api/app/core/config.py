from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas.common import AIQualityMode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "TextPulse AI"
    environment: str = "development"
    api_prefix: str = "/api"
    web_origin: str = "http://localhost:3000"
    database_url: str = "sqlite+pysqlite:///./textpulse.db"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me-textpulse-development-secret-at-least-32"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12
    encryption_key: str = Field(
        default="2U0YB6cP45bo_1MCVMhlM8TaE_oM4zHVFmb-RzwJvK8=",
        description="Base64 urlsafe 32-byte AES key.",
    )
    uploads_dir: Path = Path("./uploads")
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_endpoint_url: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    anthropic_api_key: str | None = None
    anthropic_model: str | None = None
    anthropic_default_mode: AIQualityMode = AIQualityMode.BALANCED
    anthropic_model_haiku: str = "claude-haiku-4-5"
    anthropic_model_sonnet: str = "claude-sonnet-4-6"
    anthropic_model_opus: str = "claude-opus-4-6"
    anthropic_allow_opus: bool = False
    anthropic_bulk_request_budget_usd: float = 0.15
    anthropic_live_request_budget_usd: float = 0.35
    anthropic_profile_request_budget_usd: float = 0.9
    use_demo_seed: bool = True
    imports_use_celery: bool = False
    max_upload_size_mb: int = 150
    import_preview_ttl_hours: int = 24
    ocr_enabled: bool = True
    inactivity_timeout_minutes: int = 30
    rate_limit_default: str = "100/minute"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    return settings
