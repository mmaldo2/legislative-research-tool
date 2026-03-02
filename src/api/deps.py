"""FastAPI dependency injection."""

from collections.abc import AsyncGenerator

import anthropic
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import async_session_factory
from src.llm.harness import LLMHarness

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

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
) -> str:
    """Validate API key. If API_KEY is not configured, allow all requests (dev mode)."""
    if not settings.api_key:
        return "dev-no-auth"
    if not api_key or api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key


async def get_llm_harness(
    session: AsyncSession = Depends(get_session),
) -> LLMHarness:
    return LLMHarness(db_session=session, client=get_anthropic_client())


def escape_like(value: str) -> str:
    """Escape special characters in LIKE/ILIKE patterns."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
