"""Hybrid search engine with Reciprocal Rank Fusion (RRF).

Combines BM25 keyword search with pgvector semantic search.
Falls back gracefully when embeddings or BM25 index are unavailable.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.bill import Bill
from src.search.bm25 import BM25Index
from src.search.vector import vector_search

logger = logging.getLogger(__name__)

# Singleton BM25 index — rebuilt on first search or manually
_bm25_index = BM25Index()

RRF_K = 60  # Standard RRF constant


def rrf_fuse(
    ranked_lists: list[list[tuple[str, float]]],
    top_k: int = 20,
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion across multiple result lists.

    Each input list is [(bill_id, score)] sorted by descending score.
    Returns [(bill_id, rrf_score)] sorted by descending RRF score.
    """
    scores: dict[str, float] = {}
    for ranked_list in ranked_lists:
        for rank, (bill_id, _score) in enumerate(ranked_list):
            scores[bill_id] = scores.get(bill_id, 0.0) + 1.0 / (RRF_K + rank + 1)

    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return fused[:top_k]


async def hybrid_search(
    session: AsyncSession,
    query: str,
    mode: str = "hybrid",
    jurisdiction: str | None = None,
    top_k: int = 20,
) -> list[tuple[str, float]]:
    """Run hybrid search combining BM25 and vector search.

    Args:
        session: Database session.
        query: Search query string.
        mode: "keyword", "semantic", or "hybrid".
        jurisdiction: Optional jurisdiction filter.
        top_k: Number of results to return.

    Returns:
        List of (bill_id, score) tuples.
    """
    ranked_lists: list[list[tuple[str, float]]] = []

    # BM25 keyword search
    if mode in ("keyword", "hybrid"):
        if not _bm25_index.is_built:
            await _bm25_index.build(session)

        bm25_results = _bm25_index.search(query, top_k=top_k * 2)

        # Apply jurisdiction filter if set
        if jurisdiction and bm25_results:
            bill_ids = [r[0] for r in bm25_results]
            result = await session.execute(
                select(Bill.id).where(
                    Bill.id.in_(bill_ids),
                    Bill.jurisdiction_id == jurisdiction,
                )
            )
            valid_ids = {row[0] for row in result.all()}
            bm25_results = [(bid, s) for bid, s in bm25_results if bid in valid_ids]

        if bm25_results:
            ranked_lists.append(bm25_results)

    # Vector semantic search
    if mode in ("semantic", "hybrid"):
        try:
            from src.search.embedder import embed_query

            query_embedding = await embed_query(query)
            vec_results = await vector_search(
                session, query_embedding, top_k=top_k * 2, jurisdiction=jurisdiction
            )
            if vec_results:
                ranked_lists.append(vec_results)
        except Exception as e:
            logger.warning("Semantic search unavailable: %s", e)

    if not ranked_lists:
        return []

    # If only one source, return directly
    if len(ranked_lists) == 1:
        return ranked_lists[0][:top_k]

    # Fuse with RRF
    return rrf_fuse(ranked_lists, top_k=top_k)


async def rebuild_bm25_index(session: AsyncSession) -> None:
    """Force rebuild of the BM25 index."""
    await _bm25_index.build(session)
