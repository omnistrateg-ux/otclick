"""Authentication module."""

from app.auth.api_key import (
    APIKeyAuth,
    get_api_key,
    require_api_key,
    optional_api_key,
)

__all__ = [
    "APIKeyAuth",
    "get_api_key",
    "require_api_key",
    "optional_api_key",
]
