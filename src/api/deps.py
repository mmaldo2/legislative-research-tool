"""FastAPI dependency injection."""

import secrets
import uuid
from collections.abc import AsyncGenerator

import anthropic
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import async_session_factory
from src.llm.harness import LLMHarness
from src.services.auth_service import AuthContext, hash_api_key, verify_api_key


def _get_key_func():
    """Rate limit key function — use API key hash if present, else IP."""
    from starlette.requests import Request

    def key_func(request: Request) -> str:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return hash_api_key(api_key)[:16]
        return request.client.host if request.client else "unknown"

    return key_func


limiter = Limiter(key_func=_get_key_func(), default_limits=["200/minute"])

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Module-level singleton for Anthropic client — connection pooling across requests
_anthropic_client: anthropic.AsyncAnthropic | None = None


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    """Return a shared Anthropic client (created once, reused across requests)."""
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def require_api_key(
    api_key: str | None = Security(_api_key_header),
    db: AsyncSession = Depends(get_session),
) -> AuthContext:
    """Validate API key via DB lookup. Falls back to dev mode when no key is configured."""
    # Dev mode: no static key configured and no key provided
    if not settings.api_key and not api_key:
        return AuthContext(org_id=None, tier="dev")

    # Legacy static key mode (backward compatibility during migration)
    if settings.api_key and api_key and secrets.compare_digest(api_key, settings.api_key):
        return AuthContext(org_id=None, tier="dev")

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    auth = await verify_api_key(db, api_key)
    if not auth:
        raise HTTPException(status_code=401, detail="Invalid or expired API key")
    return auth


def require_tier(*allowed_tiers: str):
    """Dependency factory: require the request's org to be on an allowed tier.

    Usage: Depends(require_tier("pro", "enterprise"))
    Dev mode always passes.
    """

    async def _check(auth: AuthContext = Depends(require_api_key)) -> AuthContext:
        if auth.tier == "dev":
            return auth
        if auth.tier not in allowed_tiers:
            raise HTTPException(
                status_code=403,
                detail=f"This endpoint requires one of: {', '.join(allowed_tiers)}",
            )
        return auth

    return _check


async def get_llm_harness(
    session: AsyncSession = Depends(get_session),
) -> LLMHarness:
    return LLMHarness(db_session=session, client=get_anthropic_client())


def require_org(auth: AuthContext) -> uuid.UUID:
    """Extract org_id from auth context, raising 403 if missing (e.g. dev mode)."""
    if auth.org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    return auth.org_id


def escape_like(value: str) -> str:
    """Escape special characters in LIKE/ILIKE patterns."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
