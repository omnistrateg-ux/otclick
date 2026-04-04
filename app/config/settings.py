"""Application settings using Pydantic Settings."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="OTCLICK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = Field(default="otclick-employer-engine")
    app_version: str = Field(default="0.1.0")
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    secret_key: SecretStr = Field(default=SecretStr("change-me"))

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://otclick:otclick@localhost:5432/otclick_employer"
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Celery
    celery_broker_url: str = Field(default="redis://localhost:6379/1")

    # LLM Providers
    openai_api_key: SecretStr | None = Field(default=None)
    anthropic_api_key: SecretStr | None = Field(default=None)
    qwen_api_key: SecretStr | None = Field(default=None)
    yandexgpt_api_key: SecretStr | None = Field(default=None)
    yandexgpt_folder_id: str | None = Field(default=None)

    # Email
    smtp_host: str = Field(default="localhost")
    smtp_port: int = Field(default=1025)
    smtp_user: str | None = Field(default=None)
    smtp_password: SecretStr | None = Field(default=None)
    smtp_from_email: str = Field(default="outreach@otclick.ru")

    # Rate Limits
    max_emails_per_sender_per_day: int = Field(default=50)
    max_emails_per_domain_per_day: int = Field(default=5)

    # External APIs
    hh_api_token: SecretStr | None = Field(default=None)
    hunter_api_key: SecretStr | None = Field(default=None)

    # Monitoring - Sentry
    sentry_dsn: str | None = Field(default=None)
    sentry_traces_sample_rate: float = Field(default=0.1)
    sentry_profiles_sample_rate: float = Field(default=0.1)

    # Monitoring - Prometheus
    prometheus_enabled: bool = Field(default=True)
    prometheus_port: int = Field(default=9090)

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")  # json or text
    log_file: str | None = Field(default=None)

    # API Authentication
    api_key_header: str = Field(default="X-API-Key")
    api_keys: str = Field(default="")  # Comma-separated list of valid API keys
    api_key_required: bool = Field(default=False)

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests_per_minute: int = Field(default=60)
    rate_limit_requests_per_hour: int = Field(default=1000)

    # CORS
    cors_origins: str = Field(default="*")
    cors_allow_credentials: bool = Field(default=True)

    # Slack notifications
    slack_webhook_url: str | None = Field(default=None)
    slack_channel: str = Field(default="#leads")

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"

    @property
    def is_testing(self) -> bool:
        """Check if running in test mode."""
        return self.environment == "testing"

    @property
    def api_keys_list(self) -> list[str]:
        """Get list of valid API keys."""
        if not self.api_keys:
            return []
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        """Get list of CORS origins."""
        if self.cors_origins == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
