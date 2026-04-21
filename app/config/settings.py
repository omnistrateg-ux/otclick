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

    # Deliverability
    auto_pause_min_sample_size: int = Field(default=50)  # Min emails before auto-pause
    bounce_rate_warning: float = Field(default=0.05)  # 5%
    bounce_rate_critical: float = Field(default=0.10)  # 10%
    complaint_rate_warning: float = Field(default=0.001)  # 0.1%
    complaint_rate_critical: float = Field(default=0.005)  # 0.5%

    # Warm-up
    warmup_enabled: bool = Field(default=True)
    warmup_initial_daily_limit: int = Field(default=10)  # Start with 10/day
    warmup_max_daily_limit: int = Field(default=200)  # Ramp up to 200/day
    warmup_increment_percent: int = Field(default=20)  # Increase by 20% daily
    warmup_days_to_full: int = Field(default=14)  # 14 days to reach max

    # A/B Testing
    ab_holdout_percent: float = Field(default=0.10)  # 10% holdout by default
    ab_winner_metric: str = Field(default="qualified_rate")  # reply_rate, qualified_rate, handoff_rate

    # Account-Based Outreach
    abo_max_contacts_per_account: int = Field(default=3)  # Max contacts to reach per company
    abo_days_between_contacts: int = Field(default=3)  # Days to wait before next contact
    abo_max_touches_per_contact: int = Field(default=4)  # Max emails per contact
    abo_stop_on_any_reply: bool = Field(default=True)  # Stop all contacts on any reply
    abo_stop_on_bounce_count: int = Field(default=2)  # Stop after N bounces per account

    # Lead Freshness
    lead_stale_days: int = Field(default=30)  # Days before lead is considered stale
    lead_reenrichment_days: int = Field(default=14)  # Days between re-enrichment
    contact_stale_days: int = Field(default=60)  # Days before contact is stale

    # Source Quality
    default_source_quality: float = Field(default=0.7)  # Default quality for unknown sources

    # Feedback Loop
    feedback_score_adjustment_max: float = Field(default=0.15)  # Max score adjustment from feedback

    # Revenue Loop
    default_deal_value: float = Field(default=50000.0)  # Default deal value in RUB
    deal_expiry_days: int = Field(default=90)  # Days before stalled deal expires

    # Handoff SLA (hours)
    handoff_sla_accept_hours: int = Field(default=4)  # Hours to accept handoff
    handoff_sla_resolve_hours: int = Field(default=72)  # Hours to resolve handoff

    # Forecasting
    forecast_min_samples: int = Field(default=30)  # Min samples for forecasting
    forecast_lookback_days: int = Field(default=60)  # Days to look back

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

    # Webhook security
    webhook_secret: SecretStr | None = Field(default=None)
    webhook_signature_required: bool = Field(default=True)

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

    def validate_security(self) -> list[str]:
        """Validate security-critical configuration.

        Returns:
            List of warning/error messages
        """
        issues = []

        # Check secret_key
        if self.secret_key.get_secret_value() == "change-me":
            msg = "CRITICAL: secret_key is set to default 'change-me'. Set OTCLICK_SECRET_KEY"
            issues.append(msg)

        # Check CORS configuration
        if self.cors_origins == "*" and self.cors_allow_credentials:
            msg = (
                "CRITICAL: CORS allows all origins (*) with credentials=True. "
                "This is a security vulnerability. Set specific origins or disable credentials"
            )
            issues.append(msg)

        # Check API authentication
        if not self.api_key_required and not self.api_keys:
            msg = (
                "WARNING: API authentication is disabled (api_key_required=False). "
                "Set OTCLICK_API_KEY_REQUIRED=true and OTCLICK_API_KEYS for production"
            )
            issues.append(msg)

        # Check database URL
        if "localhost" in self.database_url and self.is_production:
            msg = "CRITICAL: Database URL points to localhost in production"
            issues.append(msg)

        # Check Redis URL
        if "localhost" in self.redis_url and self.is_production:
            msg = "CRITICAL: Redis URL points to localhost in production"
            issues.append(msg)

        # Check LLM providers
        if not any([
            self.openai_api_key,
            self.anthropic_api_key,
            self.qwen_api_key,
            self.yandexgpt_api_key,
        ]):
            msg = "WARNING: No LLM provider API keys configured. LLM features will not work"
            issues.append(msg)

        return issues

    def validate_or_raise(self) -> None:
        """Validate configuration and raise if critical issues in production.

        Raises:
            ValueError: If critical security issues exist in production
        """
        import logging

        logger = logging.getLogger(__name__)
        issues = self.validate_security()

        if not issues:
            return

        critical_issues = [i for i in issues if i.startswith("CRITICAL")]
        warning_issues = [i for i in issues if i.startswith("WARNING")]

        for issue in warning_issues:
            logger.warning(issue)

        for issue in critical_issues:
            logger.error(issue)

        if critical_issues and self.is_production:
            raise ValueError(
                f"Critical security configuration issues in production: "
                f"{'; '.join(critical_issues)}"
            )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
