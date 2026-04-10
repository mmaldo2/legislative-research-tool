"""FastAPI dependency injection."""

import logging
import secrets
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import anthropic
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import async_session_factory
from src.llm.harness import LLMHarness
from src.services.auth_service import AuthContext, hash_api_key, verify_api_key

logger = logging.getLogger(__name__)


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

# Module-level singleton for the configured LLM client — connection pooling across requests
_llm_client: Any | None = None


def get_llm_client() -> Any:
    """Return the configured shared LLM client.

    This intentionally no longer auto-falls-back from one provider to another.
    The provider must be chosen explicitly via LLM_PROVIDER.
    """
    global _llm_client
    if _llm_client is not None:
        return _llm_client

    provider = settings.llm_provider.strip().lower()
    if provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError(
                "LLM_PROVIDER=openai but OPENAI_API_KEY is not configured."
            )
        from src.llm.openai_adapter import OpenAICompatClient

        logger.info("Using OpenAI as the primary LLM provider")
        _llm_client = OpenAICompatClient(api_key=settings.openai_api_key)
        return _llm_client

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not configured."
            )
        _llm_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        return _llm_client

    if provider == "claude-sdk":
        try:
            from src.llm.claude_sdk_adapter import ClaudeSDKClient
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "LLM_PROVIDER=claude-sdk but claude-agent-sdk is unavailable."
            ) from exc

        logger.info("Using Claude SDK as the explicit LLM provider")
        _llm_client = ClaudeSDKClient()
        return _llm_client

    raise RuntimeError(
        f"Unsupported LLM_PROVIDER={settings.llm_provider!r}. Use openai, anthropic, or claude-sdk."
    )


def get_agentic_client() -> Any:
    """Return a client suitable for the tool-using chat/workspace flows.

    Anthropic-compatible providers and the OpenAI compatibility adapter can both
    power the current app-managed research loop.
    """
    return get_llm_client()


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
    try:
        client = get_llm_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return LLMHarness(db_session=session, client=client)


def require_org(auth: AuthContext) -> uuid.UUID:
    """Extract org_id from auth context, raising 403 if missing (e.g. dev mode)."""
    if auth.org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    return auth.org_id


def escape_like(value: str) -> str:
    """Escape special characters in LIKE/ILIKE patterns."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
