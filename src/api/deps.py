"""FastAPI dependency injection."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.database import async_session_factory
from src.llm.harness import LLMHarness


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def get_llm_harness(
    session: AsyncSession,
) -> LLMHarness:
    return LLMHarness(db_session=session)
