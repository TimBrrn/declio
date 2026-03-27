"""Auth middleware — validates Bearer token against Better Stack API token."""

import logging

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.src.infrastructure.config.settings import settings

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """Validate the Bearer token and return the user identity.

    For the PoC, we validate against the configured Better Stack API token.
    Returns a simple dict with the token owner info.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization token")

    token = credentials.credentials

    if not settings.betterstack_api_token:
        logger.warning("BETTERSTACK_API_TOKEN not configured — rejecting all requests")
        raise HTTPException(status_code=401, detail="Auth not configured on server")

    if token != settings.betterstack_api_token:
        raise HTTPException(status_code=401, detail="Invalid authorization token")

    return {"authenticated": True, "token_type": "betterstack"}
