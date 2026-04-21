"""Configuration and Secrets Validation Service.

Validates all required configuration and secrets at startup.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class ConfigStatus(str, Enum):
    """Configuration status."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    MISSING = "missing"


class ConfigCategory(str, Enum):
    """Configuration categories."""

    DATABASE = "database"
    REDIS = "redis"
    API_KEYS = "api_keys"
    EMAIL = "email"
    SECURITY = "security"
    MONITORING = "monitoring"
    FEATURE_FLAGS = "feature_flags"


@dataclass
class ConfigCheck:
    """Result of a configuration check."""

    name: str
    category: ConfigCategory
    status: ConfigStatus
    message: str
    value_preview: str | None = None  # Masked preview
    required: bool = True
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category.value,
            "status": self.status.value,
            "message": self.message,
            "value_preview": self.value_preview,
            "required": self.required,
            "details": self.details,
        }


@dataclass
class ConfigValidationResult:
    """Result of full configuration validation."""

    valid: bool
    checked_at: datetime
    total_checks: int
    passed: int
    warnings: int
    errors: int
    checks: list[ConfigCheck]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "checked_at": self.checked_at.isoformat(),
            "total_checks": self.total_checks,
            "passed": self.passed,
            "warnings": self.warnings,
            "errors": self.errors,
            "checks": [c.to_dict() for c in self.checks],
        }


# Required configuration definitions
REQUIRED_CONFIGS = [
    # Database
    {
        "name": "OTCLICK_DATABASE_URL",
        "category": ConfigCategory.DATABASE,
        "required": True,
        "description": "PostgreSQL connection URL",
        "pattern": r"^postgresql://",
    },
    # Redis
    {
        "name": "OTCLICK_REDIS_URL",
        "category": ConfigCategory.REDIS,
        "required": True,
        "description": "Redis connection URL",
        "pattern": r"^redis://",
    },
    # API Keys
    {
        "name": "OTCLICK_API_KEY",
        "category": ConfigCategory.API_KEYS,
        "required": True,
        "description": "Main API key for authentication",
        "min_length": 32,
    },
    {
        "name": "OTCLICK_OPENAI_API_KEY",
        "category": ConfigCategory.API_KEYS,
        "required": False,
        "description": "OpenAI API key for LLM features",
        "pattern": r"^sk-",
    },
    {
        "name": "OTCLICK_ANTHROPIC_API_KEY",
        "category": ConfigCategory.API_KEYS,
        "required": False,
        "description": "Anthropic API key for LLM features",
        "pattern": r"^sk-ant-",
    },
    # Email
    {
        "name": "OTCLICK_SMTP_HOST",
        "category": ConfigCategory.EMAIL,
        "required": False,
        "description": "SMTP server host",
    },
    {
        "name": "OTCLICK_SMTP_USER",
        "category": ConfigCategory.EMAIL,
        "required": False,
        "description": "SMTP username",
    },
    {
        "name": "OTCLICK_SMTP_PASSWORD",
        "category": ConfigCategory.EMAIL,
        "required": False,
        "description": "SMTP password",
        "sensitive": True,
    },
    {
        "name": "OTCLICK_FROM_EMAIL",
        "category": ConfigCategory.EMAIL,
        "required": False,
        "description": "Default from email address",
        "pattern": r"^[^@]+@[^@]+\.[^@]+$",
    },
    # Security
    {
        "name": "OTCLICK_SECRET_KEY",
        "category": ConfigCategory.SECURITY,
        "required": True,
        "description": "Application secret key",
        "min_length": 32,
        "sensitive": True,
    },
    {
        "name": "OTCLICK_JWT_SECRET",
        "category": ConfigCategory.SECURITY,
        "required": False,
        "description": "JWT signing secret",
        "min_length": 32,
        "sensitive": True,
    },
    # Monitoring
    {
        "name": "OTCLICK_SENTRY_DSN",
        "category": ConfigCategory.MONITORING,
        "required": False,
        "description": "Sentry DSN for error tracking",
        "pattern": r"^https://.*@.*sentry",
    },
]


class ConfigValidationService:
    """Service for validating configuration and secrets.

    Features:
    - Startup validation
    - Secret presence checks
    - Format validation
    - Health checks
    """

    def __init__(self) -> None:
        """Initialize service."""
        pass

    def validate_all(self) -> ConfigValidationResult:
        """Validate all configuration.

        Returns:
            ConfigValidationResult
        """
        import re

        checks = []
        now = datetime.now(UTC)

        for config in REQUIRED_CONFIGS:
            name = config["name"]
            category = config["category"]
            required = config.get("required", True)
            description = config.get("description", "")
            pattern = config.get("pattern")
            min_length = config.get("min_length")
            sensitive = config.get("sensitive", False)

            value = os.environ.get(name)

            if not value:
                if required:
                    status = ConfigStatus.MISSING
                    message = f"Required: {description}"
                else:
                    status = ConfigStatus.WARNING
                    message = f"Optional but missing: {description}"

                checks.append(ConfigCheck(
                    name=name,
                    category=category,
                    status=status,
                    message=message,
                    required=required,
                ))
                continue

            # Value exists, validate it
            errors = []

            if pattern and not re.match(pattern, value):
                errors.append(f"Value does not match expected pattern")

            if min_length and len(value) < min_length:
                errors.append(f"Value too short (min {min_length} chars)")

            if errors:
                status = ConfigStatus.ERROR
                message = "; ".join(errors)
            else:
                status = ConfigStatus.OK
                message = description

            # Create masked preview
            if sensitive:
                preview = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "****"
            else:
                preview = f"{value[:20]}..." if len(value) > 20 else value

            checks.append(ConfigCheck(
                name=name,
                category=category,
                status=status,
                message=message,
                value_preview=preview,
                required=required,
            ))

        # Calculate summary
        passed = sum(1 for c in checks if c.status == ConfigStatus.OK)
        warnings = sum(1 for c in checks if c.status == ConfigStatus.WARNING)
        errors = sum(1 for c in checks if c.status in (ConfigStatus.ERROR, ConfigStatus.MISSING) and c.required)

        return ConfigValidationResult(
            valid=errors == 0,
            checked_at=now,
            total_checks=len(checks),
            passed=passed,
            warnings=warnings,
            errors=errors,
            checks=checks,
        )

    def validate_category(self, category: ConfigCategory) -> ConfigValidationResult:
        """Validate configuration for a category.

        Args:
            category: Category to validate

        Returns:
            ConfigValidationResult
        """
        full_result = self.validate_all()

        filtered_checks = [c for c in full_result.checks if c.category == category]

        passed = sum(1 for c in filtered_checks if c.status == ConfigStatus.OK)
        warnings = sum(1 for c in filtered_checks if c.status == ConfigStatus.WARNING)
        errors = sum(1 for c in filtered_checks if c.status in (ConfigStatus.ERROR, ConfigStatus.MISSING) and c.required)

        return ConfigValidationResult(
            valid=errors == 0,
            checked_at=full_result.checked_at,
            total_checks=len(filtered_checks),
            passed=passed,
            warnings=warnings,
            errors=errors,
            checks=filtered_checks,
        )

    def check_database_connection(self) -> ConfigCheck:
        """Check database connection.

        Returns:
            ConfigCheck
        """
        try:
            # Just check if URL is configured
            db_url = os.environ.get("OTCLICK_DATABASE_URL")
            if not db_url:
                return ConfigCheck(
                    name="database_connection",
                    category=ConfigCategory.DATABASE,
                    status=ConfigStatus.MISSING,
                    message="Database URL not configured",
                    required=True,
                )

            return ConfigCheck(
                name="database_connection",
                category=ConfigCategory.DATABASE,
                status=ConfigStatus.OK,
                message="Database URL configured",
                required=True,
            )
        except Exception as e:
            return ConfigCheck(
                name="database_connection",
                category=ConfigCategory.DATABASE,
                status=ConfigStatus.ERROR,
                message=f"Database check failed: {str(e)}",
                required=True,
            )

    async def check_redis_connection(self) -> ConfigCheck:
        """Check Redis connection.

        Returns:
            ConfigCheck
        """
        try:
            from app.storage.redis import get_redis

            redis = await get_redis()
            await redis.ping()

            return ConfigCheck(
                name="redis_connection",
                category=ConfigCategory.REDIS,
                status=ConfigStatus.OK,
                message="Redis connection successful",
                required=True,
            )
        except Exception as e:
            return ConfigCheck(
                name="redis_connection",
                category=ConfigCategory.REDIS,
                status=ConfigStatus.ERROR,
                message=f"Redis connection failed: {str(e)}",
                required=True,
            )

    def get_config_summary(self) -> dict[str, Any]:
        """Get configuration summary by category.

        Returns:
            Summary dict
        """
        result = self.validate_all()

        by_category = {}
        for check in result.checks:
            cat = check.category.value
            if cat not in by_category:
                by_category[cat] = {"ok": 0, "warning": 0, "error": 0, "missing": 0}

            by_category[cat][check.status.value] = by_category[cat].get(check.status.value, 0) + 1

        return {
            "valid": result.valid,
            "total_checks": result.total_checks,
            "passed": result.passed,
            "warnings": result.warnings,
            "errors": result.errors,
            "by_category": by_category,
        }

    def log_validation_result(self, result: ConfigValidationResult) -> None:
        """Log validation result.

        Args:
            result: Validation result
        """
        if result.valid:
            logger.info(
                f"[Config] Validation passed | "
                f"checks={result.total_checks} | passed={result.passed} | warnings={result.warnings}"
            )
        else:
            logger.error(
                f"[Config] Validation FAILED | "
                f"checks={result.total_checks} | errors={result.errors} | warnings={result.warnings}"
            )

            for check in result.checks:
                if check.status in (ConfigStatus.ERROR, ConfigStatus.MISSING):
                    logger.error(f"[Config] {check.name}: {check.message}")


# Singleton
config_validator = ConfigValidationService()
