"""API Key authentication.

Аутентификация по API ключу в заголовке запроса.
"""

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timezone

UTC = timezone.utc
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from app.config import settings

logger = logging.getLogger(__name__)

# API Key header
api_key_header = APIKeyHeader(
    name=settings.api_key_header,
    auto_error=False,
)


class APIKeyAuth:
    """API Key authentication handler.

    Validates API keys from request headers.
    Supports multiple valid keys for key rotation.
    """

    def __init__(self) -> None:
        """Initialize API key auth."""
        self._valid_keys = set(settings.api_keys_list)
        self._key_hashes: dict[str, str] = {}

        # Pre-compute hashes for comparison
        for key in self._valid_keys:
            self._key_hashes[self._hash_key(key)] = key

    def _hash_key(self, key: str) -> str:
        """Hash API key for secure comparison.

        Args:
            key: API key

        Returns:
            Hashed key
        """
        return hashlib.sha256(key.encode()).hexdigest()

    def validate_key(self, api_key: str | None) -> bool:
        """Validate API key.

        Args:
            api_key: API key to validate

        Returns:
            True if valid
        """
        if not api_key:
            return False

        # Use constant-time comparison
        key_hash = self._hash_key(api_key)
        return key_hash in self._key_hashes

    def get_key_info(self, api_key: str) -> dict[str, str] | None:
        """Get information about an API key.

        Args:
            api_key: API key

        Returns:
            Key info or None
        """
        if not self.validate_key(api_key):
            return None

        return {
            "key_prefix": api_key[:8] + "...",
            "valid": True,
        }

    @staticmethod
    def generate_key() -> str:
        """Generate a new API key.

        Returns:
            New API key
        """
        return secrets.token_urlsafe(32)


# Global auth instance
_auth = APIKeyAuth()


async def get_api_key(
    request: Request,
    api_key: str | None = Security(api_key_header),
) -> str | None:
    """Get API key from request.

    Args:
        request: HTTP request
        api_key: API key from header

    Returns:
        API key or None
    """
    return api_key


async def require_api_key(
    request: Request,
    api_key: str | None = Security(api_key_header),
) -> str:
    """Require valid API key.

    Args:
        request: HTTP request
        api_key: API key from header

    Returns:
        Validated API key

    Raises:
        HTTPException: If key is missing or invalid
    """
    # Skip auth if not required
    if not settings.api_key_required:
        return api_key or "anonymous"

    if not api_key:
        logger.warning(
            f"Missing API key for {request.method} {request.url.path}",
            extra={"client_ip": request.client.host if request.client else "unknown"},
        )
        raise HTTPException(
            status_code=401,
            detail="API key required",
            headers={"WWW-Authenticate": f"ApiKey realm='{settings.api_key_header}'"},
        )

    if not _auth.validate_key(api_key):
        logger.warning(
            f"Invalid API key for {request.method} {request.url.path}",
            extra={
                "key_prefix": api_key[:8] + "...",
                "client_ip": request.client.host if request.client else "unknown",
            },
        )
        raise HTTPException(
            status_code=403,
            detail="Invalid API key",
        )

    # Store key info in request state
    request.state.api_key = api_key[:8] + "..."
    request.state.authenticated = True

    return api_key


async def optional_api_key(
    request: Request,
    api_key: str | None = Security(api_key_header),
) -> str | None:
    """Optional API key validation.

    Args:
        request: HTTP request
        api_key: API key from header

    Returns:
        Validated API key or None
    """
    if not api_key:
        request.state.authenticated = False
        return None

    if _auth.validate_key(api_key):
        request.state.api_key = api_key[:8] + "..."
        request.state.authenticated = True
        return api_key

    request.state.authenticated = False
    return None


# Type aliases for dependency injection
RequiredAPIKey = Annotated[str, Depends(require_api_key)]
OptionalAPIKey = Annotated[str | None, Depends(optional_api_key)]
