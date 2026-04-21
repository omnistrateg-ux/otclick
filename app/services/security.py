"""Security Hardening Service.

Input validation, security checks, and threat detection.
"""

import hashlib
import hmac
import logging
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class ThreatLevel(str, Enum):
    """Threat severity levels."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityEventType(str, Enum):
    """Types of security events."""

    INVALID_INPUT = "invalid_input"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    AUTHENTICATION_FAILED = "authentication_failed"
    AUTHORIZATION_FAILED = "authorization_failed"
    SUSPICIOUS_PATTERN = "suspicious_pattern"
    INJECTION_ATTEMPT = "injection_attempt"
    BRUTE_FORCE = "brute_force"
    IP_BLOCKED = "ip_blocked"


@dataclass
class SecurityEvent:
    """A security event."""

    id: str
    event_type: SecurityEventType
    threat_level: ThreatLevel
    timestamp: datetime
    source_ip: str | None
    user_id: str | None
    description: str
    details: dict[str, Any] = field(default_factory=dict)
    blocked: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "threat_level": self.threat_level.value,
            "timestamp": self.timestamp.isoformat(),
            "source_ip": self.source_ip,
            "user_id": self.user_id,
            "description": self.description,
            "details": self.details,
            "blocked": self.blocked,
        }


@dataclass
class ValidationResult:
    """Result of input validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    sanitized_value: Any = None
    threat_detected: bool = False


# Patterns for threat detection
INJECTION_PATTERNS = [
    r"<script[^>]*>",
    r"javascript:",
    r"on\w+\s*=",
    r"eval\s*\(",
    r"exec\s*\(",
    r"__import__",
    r"subprocess",
    r"os\.system",
    r";\s*drop\s+table",
    r";\s*delete\s+from",
    r"union\s+select",
    r"'\s*or\s+'1'\s*=\s*'1",
]

# Compiled patterns
COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


class SecurityService:
    """Security hardening service.

    Features:
    - Input validation and sanitization
    - Threat detection
    - Security event logging
    - IP blocking
    - Rate limit tracking
    """

    def __init__(self) -> None:
        """Initialize service."""
        pass

    # ========================================================================
    # Input Validation
    # ========================================================================

    def validate_email(self, email: str) -> ValidationResult:
        """Validate email address.

        Args:
            email: Email to validate

        Returns:
            ValidationResult
        """
        errors = []

        if not email:
            return ValidationResult(valid=False, errors=["Email is required"])

        # Basic email pattern
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, email):
            errors.append("Invalid email format")

        # Check for injection
        threat = self._check_injection(email)
        if threat:
            errors.append("Potentially malicious content detected")
            return ValidationResult(
                valid=False,
                errors=errors,
                threat_detected=True,
            )

        # Sanitize
        sanitized = email.lower().strip()

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            sanitized_value=sanitized,
        )

    def validate_phone(self, phone: str) -> ValidationResult:
        """Validate phone number.

        Args:
            phone: Phone to validate

        Returns:
            ValidationResult
        """
        errors = []

        if not phone:
            return ValidationResult(valid=False, errors=["Phone is required"])

        # Remove common separators
        cleaned = re.sub(r"[\s\-\.\(\)]", "", phone)

        # Check for valid characters
        if not re.match(r"^\+?[0-9]{7,15}$", cleaned):
            errors.append("Invalid phone format")

        # Check for injection
        threat = self._check_injection(phone)
        if threat:
            errors.append("Potentially malicious content detected")
            return ValidationResult(
                valid=False,
                errors=errors,
                threat_detected=True,
            )

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            sanitized_value=cleaned,
        )

    def validate_url(self, url: str) -> ValidationResult:
        """Validate URL.

        Args:
            url: URL to validate

        Returns:
            ValidationResult
        """
        errors = []

        if not url:
            return ValidationResult(valid=False, errors=["URL is required"])

        # Basic URL pattern
        pattern = r"^https?://[a-zA-Z0-9][-a-zA-Z0-9@:%._\+~#=]{0,255}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_\+.~#?&//=]*)$"
        if not re.match(pattern, url, re.IGNORECASE):
            errors.append("Invalid URL format")

        # Check for javascript: URLs
        if url.lower().startswith("javascript:"):
            errors.append("JavaScript URLs not allowed")
            return ValidationResult(
                valid=False,
                errors=errors,
                threat_detected=True,
            )

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            sanitized_value=url.strip(),
        )

    def validate_text(
        self,
        text: str,
        max_length: int = 10000,
        allow_html: bool = False,
    ) -> ValidationResult:
        """Validate text input.

        Args:
            text: Text to validate
            max_length: Maximum allowed length
            allow_html: Whether to allow HTML

        Returns:
            ValidationResult
        """
        errors = []

        if not text:
            return ValidationResult(valid=True, sanitized_value="")

        if len(text) > max_length:
            errors.append(f"Text exceeds maximum length of {max_length}")

        # Check for injection
        threat = self._check_injection(text)
        if threat:
            errors.append("Potentially malicious content detected")
            return ValidationResult(
                valid=False,
                errors=errors,
                threat_detected=True,
            )

        # Sanitize HTML if not allowed
        sanitized = text
        if not allow_html:
            sanitized = re.sub(r"<[^>]+>", "", text)

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            sanitized_value=sanitized.strip(),
        )

    def _check_injection(self, value: str) -> bool:
        """Check for injection patterns.

        Args:
            value: Value to check

        Returns:
            True if threat detected
        """
        for pattern in COMPILED_PATTERNS:
            if pattern.search(value):
                return True
        return False

    # ========================================================================
    # Security Events
    # ========================================================================

    async def log_security_event(
        self,
        event_type: SecurityEventType,
        threat_level: ThreatLevel,
        description: str,
        source_ip: str | None = None,
        user_id: str | None = None,
        details: dict[str, Any] | None = None,
        blocked: bool = False,
    ) -> SecurityEvent:
        """Log a security event.

        Args:
            event_type: Type of event
            threat_level: Threat severity
            description: Event description
            source_ip: Source IP
            user_id: User ID if known
            details: Additional details
            blocked: Whether action was blocked

        Returns:
            SecurityEvent
        """
        from app.storage.redis import get_redis
        from uuid import uuid4
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        event = SecurityEvent(
            id=str(uuid4()),
            event_type=event_type,
            threat_level=threat_level,
            timestamp=now,
            source_ip=source_ip,
            user_id=user_id,
            description=description,
            details=details or {},
            blocked=blocked,
        )

        # Store event
        key = f"security:event:{event.id}"
        await redis.set(key, json.dumps(event.to_dict()), ex=86400 * 90)

        # Add to timeline
        await redis.zadd("security:timeline", {event.id: now.timestamp()})
        await redis.expire("security:timeline", 86400 * 90)

        # Track by IP if available
        if source_ip:
            await redis.lpush(f"security:ip:{source_ip}", event.id)
            await redis.ltrim(f"security:ip:{source_ip}", 0, 999)
            await redis.expire(f"security:ip:{source_ip}", 86400 * 30)

        # Increment counters
        day = now.strftime("%Y-%m-%d")
        await redis.incr(f"security:stats:{day}:{event_type.value}")
        await redis.expire(f"security:stats:{day}:{event_type.value}", 86400 * 90)

        # Log
        log_level = logging.WARNING if threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL) else logging.INFO
        logger.log(
            log_level,
            f"[Security] {event_type.value} | threat={threat_level.value} | "
            f"ip={source_ip} | user={user_id} | {description}"
        )

        return event

    async def get_security_events(
        self,
        hours: int = 24,
        event_type: SecurityEventType | None = None,
        min_threat_level: ThreatLevel | None = None,
        limit: int = 100,
    ) -> list[SecurityEvent]:
        """Get recent security events.

        Args:
            hours: Hours to look back
            event_type: Filter by type
            min_threat_level: Minimum threat level
            limit: Max events

        Returns:
            List of security events
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)
        start_time = (now - timedelta(hours=hours)).timestamp()

        event_ids = await redis.zrangebyscore(
            "security:timeline",
            start_time,
            now.timestamp(),
            start=0,
            num=limit * 2,
        )

        threat_order = [ThreatLevel.NONE, ThreatLevel.LOW, ThreatLevel.MEDIUM, ThreatLevel.HIGH, ThreatLevel.CRITICAL]

        events = []
        for event_id in reversed(event_ids):
            if len(events) >= limit:
                break

            data = await redis.get(f"security:event:{event_id}")
            if not data:
                continue

            d = json.loads(data)
            event = SecurityEvent(
                id=d["id"],
                event_type=SecurityEventType(d["event_type"]),
                threat_level=ThreatLevel(d["threat_level"]),
                timestamp=datetime.fromisoformat(d["timestamp"]),
                source_ip=d.get("source_ip"),
                user_id=d.get("user_id"),
                description=d["description"],
                details=d.get("details", {}),
                blocked=d.get("blocked", False),
            )

            # Apply filters
            if event_type and event.event_type != event_type:
                continue

            if min_threat_level:
                if threat_order.index(event.threat_level) < threat_order.index(min_threat_level):
                    continue

            events.append(event)

        return events

    # ========================================================================
    # IP Blocking
    # ========================================================================

    async def block_ip(
        self,
        ip: str,
        reason: str,
        duration_hours: int = 24,
        actor: str = "system",
    ) -> None:
        """Block an IP address.

        Args:
            ip: IP to block
            reason: Reason for blocking
            duration_hours: Block duration
            actor: Who initiated the block
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        block_data = {
            "ip": ip,
            "reason": reason,
            "blocked_at": now.isoformat(),
            "blocked_by": actor,
            "expires_at": (now + timedelta(hours=duration_hours)).isoformat(),
        }

        await redis.set(
            f"security:blocked_ip:{ip}",
            json.dumps(block_data),
            ex=duration_hours * 3600,
        )

        await self.log_security_event(
            event_type=SecurityEventType.IP_BLOCKED,
            threat_level=ThreatLevel.HIGH,
            description=f"IP blocked: {reason}",
            source_ip=ip,
            details={"duration_hours": duration_hours, "actor": actor},
            blocked=True,
        )

    async def is_ip_blocked(self, ip: str) -> bool:
        """Check if IP is blocked.

        Args:
            ip: IP to check

        Returns:
            True if blocked
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        return await redis.exists(f"security:blocked_ip:{ip}") > 0

    async def unblock_ip(self, ip: str, actor: str = "system") -> None:
        """Unblock an IP address.

        Args:
            ip: IP to unblock
            actor: Who unblocked
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        await redis.delete(f"security:blocked_ip:{ip}")

        logger.info(f"[Security] IP unblocked | ip={ip} | actor={actor}")

    # ========================================================================
    # Rate Limiting
    # ========================================================================

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int = 60,
    ) -> tuple[bool, int]:
        """Check rate limit.

        Args:
            key: Rate limit key
            limit: Max requests
            window_seconds: Time window

        Returns:
            (allowed, remaining)
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        window_key = f"ratelimit:{key}:{int(now.timestamp()) // window_seconds}"

        current = await redis.incr(window_key)
        if current == 1:
            await redis.expire(window_key, window_seconds)

        remaining = max(0, limit - current)
        allowed = current <= limit

        return allowed, remaining

    # ========================================================================
    # Token Generation
    # ========================================================================

    def generate_secure_token(self, length: int = 32) -> str:
        """Generate a secure random token.

        Args:
            length: Token length in bytes

        Returns:
            Hex-encoded token
        """
        return secrets.token_hex(length)

    def hash_sensitive_data(self, data: str, salt: str | None = None) -> str:
        """Hash sensitive data.

        Args:
            data: Data to hash
            salt: Optional salt

        Returns:
            Hashed value
        """
        if salt:
            data = salt + data
        return hashlib.sha256(data.encode()).hexdigest()

    def verify_signature(
        self,
        payload: str,
        signature: str,
        secret: str,
    ) -> bool:
        """Verify HMAC signature.

        Args:
            payload: Original payload
            signature: Signature to verify
            secret: Secret key

        Returns:
            True if valid
        """
        expected = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature, expected)


# Singleton
security_service = SecurityService()
