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

    where_clause = ""
    if jurisdiction:
        where_clause = "AND b.jurisdiction_id = :jurisdiction"
        params["jurisdiction"] = jurisdiction

    sql = text(f"""
        SELECT be.bill_id, 1 - (be.embedding <=> :embedding::vector) AS similarity
        FROM bill_embeddings be
        JOIN bills b ON b.id = be.bill_id
        WHERE be.embedding IS NOT NULL
        {where_clause}
        ORDER BY be.embedding <=> :embedding::vector
        LIMIT :limit
    """)

    try:
        result = await session.execute(sql, params)
        return [(row.bill_id, float(row.similarity)) for row in result.all()]
    except Exception as e:
        logger.warning("Vector search failed (embeddings may not exist yet): %s", e)
        return []
