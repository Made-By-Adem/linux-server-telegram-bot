"""API key authentication dependency for FastAPI."""

from __future__ import annotations

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from linux_server_bot.config import config

_api_key_header = APIKeyHeader(name="X-API-Key")


async def verify_api_key(key: str = Security(_api_key_header)) -> str:
    """FastAPI dependency that validates the API key from the X-API-Key header."""
    if not config.api.enabled:
        raise HTTPException(status_code=503, detail="API disabled")
    if not config.api.api_key:
        raise HTTPException(status_code=503, detail="API key not configured")
    if key != config.api.api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return key
