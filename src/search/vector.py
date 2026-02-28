"""pgvector similarity search for bill embeddings."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def vector_search(
    session: AsyncSession,
    query_embedding: list[float],
    top_k: int = 20,
    jurisdiction: str | None = None,
) -> list[tuple[str, float]]:
    """Search bill embeddings using cosine similarity.

    Returns list of (bill_id, similarity_score) sorted by descending similarity.
    Requires the bill_embeddings table to have a `embedding` vector column.
    """
    params: dict = {"embedding": str(query_embedding), "limit": top_k}

    # Build query with optional jurisdiction filter — all values are bound params
    base = (
        "SELECT be.bill_id, 1 - (be.embedding <=> :embedding::vector) AS similarity"
        " FROM bill_embeddings be"
        " JOIN bills b ON b.id = be.bill_id"
        " WHERE be.embedding IS NOT NULL"
    )
    if jurisdiction:
        base += " AND b.jurisdiction_id = :jurisdiction"
        params["jurisdiction"] = jurisdiction

    base += " ORDER BY be.embedding <=> :embedding::vector LIMIT :limit"

    try:
        result = await session.execute(text(base), params)
        return [(row.bill_id, float(row.similarity)) for row in result.all()]
    except Exception as e:
        logger.warning("Vector search failed (embeddings may not exist yet): %s", e)
        return []
