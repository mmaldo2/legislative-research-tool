"""Voyage-law-2 embedding pipeline for bill texts.

Generates embeddings for bill texts and stores them in pgvector.
Falls back to a no-op if VOYAGE_API_KEY is not set.
"""

import logging

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.normalizer import content_hash
from src.models.bill import Bill
from src.models.bill_embedding import BillEmbedding
from src.models.bill_text import BillText

logger = logging.getLogger(__name__)

VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_MODEL = "voyage-law-2"
EMBEDDING_DIM = 1024
BATCH_SIZE = 8  # Voyage recommends small batches for long documents

# Module-level shared client — created lazily, closed explicitly
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    """Return a shared httpx client, creating it on first use."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=120.0)
    return _http_client


async def close_http_client() -> None:
    """Close the shared httpx client. Call during app shutdown."""
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Call Voyage AI API to embed a batch of texts."""
    if not settings.voyage_api_key:
        raise RuntimeError("VOYAGE_API_KEY not set")

    client = _get_http_client()
    resp = await client.post(
        VOYAGE_API_URL,
        json={"model": VOYAGE_MODEL, "input": texts, "input_type": "document"},
        headers={"Authorization": f"Bearer {settings.voyage_api_key}"},
    )
    resp.raise_for_status()
    data = resp.json()
    return [item["embedding"] for item in data["data"]]


async def embed_query(query: str) -> list[float]:
    """Embed a single search query."""
    if not settings.voyage_api_key:
        raise RuntimeError("VOYAGE_API_KEY not set")

    client = _get_http_client()
    resp = await client.post(
        VOYAGE_API_URL,
        json={"model": VOYAGE_MODEL, "input": [query], "input_type": "query"},
        headers={"Authorization": f"Bearer {settings.voyage_api_key}"},
    )
    resp.raise_for_status()
    data = resp.json()
    return data["data"][0]["embedding"]


async def embed_all_bills(session: AsyncSession) -> int:
    """Embed all bills that don't have embeddings yet. Returns count embedded."""
    if not settings.voyage_api_key:
        logger.warning("VOYAGE_API_KEY not set — skipping embedding")
        return 0

    # Find bills without embeddings
    existing = select(BillEmbedding.bill_id)
    stmt = (
        select(Bill.id, Bill.title, BillText.content_text)
        .outerjoin(BillText, Bill.id == BillText.bill_id)
        .where(Bill.id.notin_(existing))
    )
    result = await session.execute(stmt)
    rows = result.all()

    if not rows:
        logger.info("All bills already embedded")
        return 0

    # Deduplicate by bill_id (may have multiple text versions)
    bills_to_embed: dict[str, str] = {}
    for bill_id, title, content_text in rows:
        if bill_id not in bills_to_embed:
            doc = content_text[:5000] if content_text else title
            bills_to_embed[bill_id] = f"{title}\n\n{doc}"

    bill_ids = list(bills_to_embed.keys())
    texts = list(bills_to_embed.values())
    embedded_count = 0

    for i in range(0, len(texts), BATCH_SIZE):
        batch_texts = texts[i : i + BATCH_SIZE]
        batch_ids = bill_ids[i : i + BATCH_SIZE]

        try:
            embeddings = await embed_texts(batch_texts)
        except Exception as e:
            logger.error("Embedding batch %d failed: %s", i, e)
            continue

        # Batch insert embedding rows
        new_embeddings = []
        for bill_id, embedding in zip(batch_ids, embeddings):
            c_hash = content_hash(bills_to_embed[bill_id])
            emb = BillEmbedding(
                bill_id=bill_id,
                model_version=VOYAGE_MODEL,
                content_hash=c_hash,
            )
            session.add(emb)
            new_embeddings.append((emb, embedding))

        # Flush once per batch to get IDs for all rows
        await session.flush()

        # Batch update vectors via raw SQL
        for emb, embedding in new_embeddings:
            await session.execute(
                text(
                    "UPDATE bill_embeddings SET embedding = :vec::vector "
                    "WHERE id = :id"
                ),
                {"vec": str(embedding), "id": emb.id},
            )
            embedded_count += 1

        await session.commit()
        logger.info(
            "Embedded batch %d-%d (%d bills)", i, i + len(batch_texts), embedded_count
        )

    logger.info("Embedding complete: %d bills embedded", embedded_count)
    return embedded_count
