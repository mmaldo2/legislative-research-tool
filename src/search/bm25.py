"""BM25 keyword search over bill titles and texts.

Uses bm25s for pure-Python BM25 scoring without external services.
Streams bills from the database in batches to bound memory usage.
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.bill import Bill
from src.models.bill_text import BillText

logger = logging.getLogger(__name__)


class BM25Index:
    """In-memory BM25 index built from bill titles and texts."""

    def __init__(self) -> None:
        self._corpus: list[str] = []
        self._bill_ids: list[str] = []
        self._retriever: object | None = None

    @property
    def is_built(self) -> bool:
        return self._retriever is not None

    def invalidate(self) -> None:
        """Mark the index as stale so it will be rebuilt on next search."""
        self._retriever = None
        self._corpus = []
        self._bill_ids = []

    async def build(self, session: AsyncSession) -> None:
        """Build the BM25 index by streaming bills in batches.

        Uses yield_per() to avoid loading all bills into memory at once.
        Respects bm25_max_corpus setting to bound total index size.
        """
        import bm25s

        max_corpus = settings.bm25_max_corpus
        batch_size = settings.bm25_stream_batch

        # Pre-fetch text snippets (one per bill, first text only)
        texts_result = await session.execute(
            select(BillText.bill_id, BillText.content_text).limit(max_corpus)
        )
        texts_by_bill: dict[str, str] = {}
        for row in texts_result.all():
            if row.content_text and row.bill_id not in texts_by_bill:
                texts_by_bill[row.bill_id] = row.content_text[:5000]

        # Stream bills in batches using yield_per
        bill_count = (
            await session.execute(select(func.count(Bill.id)))
        ).scalar_one()

        self._corpus = []
        self._bill_ids = []

        stmt = (
            select(Bill.id, Bill.title)
            .order_by(Bill.updated_at.desc())
            .limit(max_corpus)
            .execution_options(yield_per=batch_size)
        )
        result = await session.execute(stmt)

        for partition in result.partitions():
            for bill_id, title in partition:
                doc = title
                if bill_id in texts_by_bill:
                    doc = f"{title} {texts_by_bill[bill_id]}"
                self._corpus.append(doc)
                self._bill_ids.append(bill_id)

        # Free text snippets after building corpus
        del texts_by_bill

        if not self._corpus:
            logger.warning("No bills found — BM25 index is empty")
            return

        corpus_tokens = bm25s.tokenize(self._corpus)
        retriever = bm25s.BM25()
        retriever.index(corpus_tokens)
        self._retriever = retriever
        logger.info(
            "BM25 index built with %d documents (total bills: %d, max: %d)",
            len(self._corpus),
            bill_count,
            max_corpus,
        )

    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        """Search the index. Returns list of (bill_id, score)."""
        if not self._retriever:
            return []

        import bm25s

        query_tokens = bm25s.tokenize([query])
        results, scores = self._retriever.retrieve(query_tokens, k=min(top_k, len(self._corpus)))

        hits: list[tuple[str, float]] = []
        for idx, score in zip(results[0], scores[0]):
            if score > 0:
                hits.append((self._bill_ids[idx], float(score)))
        return hits
