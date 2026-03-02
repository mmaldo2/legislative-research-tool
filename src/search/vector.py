"""pgvector similarity search for bill embeddings."""

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SimilarBillMatch:
    """A single bill-to-bill similarity result."""

    bill_id: str
    score: float


async def find_similar_bill_ids(
    session: AsyncSession,
    bill_id: str,
    *,
    exclude_jurisdiction: str | None = None,
    min_score: float = 0.0,
    top_k: int = 10,
) -> list[SimilarBillMatch]:
    """Find bills similar to the given bill, with pgvector fallback to bill_similarities.

    Tries cosine similarity on bill_embeddings first, then falls back to the
    pre-computed bill_similarities table.

    Args:
        session: Async database session.
        bill_id: Source bill ID.
        exclude_jurisdiction: If set, exclude bills from this jurisdiction.
        min_score: Minimum similarity score (0.0-1.0).
        top_k: Maximum number of results.

    Returns:
        List of SimilarBillMatch sorted by descending score.
    """
    params: dict = {"bill_id": bill_id, "top_k": top_k}

    jurisdiction_clause = ""
    if exclude_jurisdiction:
        jurisdiction_clause = "AND b.jurisdiction_id != :exclude_jurisdiction"
        params["exclude_jurisdiction"] = exclude_jurisdiction

    min_score_clause = ""
    if min_score > 0.0:
        min_score_clause = "AND 1 - (be1.embedding <=> be2.embedding) > :min_score"
        params["min_score"] = min_score

    # Try pgvector cosine similarity first
    embedding_query = text(f"""
        SELECT be2.bill_id,
               1 - (be1.embedding <=> be2.embedding) AS score
        FROM bill_embeddings be1
        JOIN bill_embeddings be2 ON be1.bill_id != be2.bill_id
        JOIN bills b ON b.id = be2.bill_id
        WHERE be1.bill_id = :bill_id
          {min_score_clause}
          {jurisdiction_clause}
        ORDER BY be1.embedding <=> be2.embedding
        LIMIT :top_k
    """)

    try:
        rows = (await session.execute(embedding_query, params)).fetchall()
    except Exception as e:
        logger.warning("Embedding similarity failed: %s", e)
        rows = []

    # Fallback to pre-computed bill_similarities table
    if not rows:
        logger.info(
            "No embedding match for bill %s, falling back to bill_similarities",
            bill_id,
        )
        fallback_min = ""
        if min_score > 0.0:
            fallback_min = "AND bs.similarity_score > :min_score"

        fallback_query = text(f"""
            SELECT
                CASE WHEN bill_id_a = :bill_id THEN bill_id_b
                     ELSE bill_id_a END AS bill_id,
                similarity_score AS score
            FROM bill_similarities bs
            JOIN bills b ON b.id = (
                CASE WHEN bs.bill_id_a = :bill_id THEN bs.bill_id_b
                     ELSE bs.bill_id_a END
            )
            WHERE (bs.bill_id_a = :bill_id OR bs.bill_id_b = :bill_id)
              {fallback_min}
              {jurisdiction_clause}
            ORDER BY bs.similarity_score DESC
            LIMIT :top_k
        """)
        rows = (await session.execute(fallback_query, params)).fetchall()

    return [SimilarBillMatch(bill_id=r.bill_id, score=float(r.score)) for r in rows]


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
