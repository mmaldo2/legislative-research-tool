"""Backfill the federal bill-text corpus from GovInfo BILLS bulkdata.

Rebuilds the introduced text (HR + S) for a Congress into `bill_texts`. Deletes the
congress's existing rows first, then downloads the per-(session, type) USLM ZIPs --
deterministic and idempotent (a re-run reconstructs the same corpus). No API key needed
(bulkdata is public/static).

Usage:
    python -m scripts.backfill_bill_text --congress 119
    python -m scripts.backfill_bill_text --congress 119 --limit 50   # smoke run
"""

import argparse
import asyncio
import logging

from src.database import async_session_factory
from src.ingestion.govinfo import GovInfoIngester

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def backfill_bill_text(congress: int, limit: int | None) -> None:
    """Run the bill-text corpus backfill for a single Congress."""
    async with async_session_factory() as session:
        ingester = GovInfoIngester(session, congress=congress)
        try:
            report = await ingester.backfill_bill_texts(limit=limit)
            logger.info("Bill-text backfill done for Congress %d: %s", congress, report)
        finally:
            await ingester.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--congress", type=int, default=119, help="Congress number (default: 119)")
    parser.add_argument(
        "--limit", type=int, default=None, help="Cap total rows for a smoke run (default: all)"
    )
    args = parser.parse_args()
    asyncio.run(backfill_bill_text(args.congress, args.limit))


if __name__ == "__main__":
    main()
