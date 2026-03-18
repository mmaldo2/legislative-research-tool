"""Backfill historical federal bills from Congress 110-118.

Runs the GovInfo ingester for each historical congress, one at a time.
Each congress gets its own IngestionRun for tracking and resumability.

Usage:
    python -m scripts.backfill_historical
    python -m scripts.backfill_historical --start 114 --end 118
    python -m scripts.backfill_historical --start 110 --end 110
"""

import argparse
import asyncio
import logging
import sys

from src.database import async_session_factory
from src.ingestion.govinfo import GovInfoIngester

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def backfill(start: int, end: int) -> None:
    """Run GovInfo ingestion for each congress in the range."""
    for congress in range(start, end + 1):
        logger.info("=" * 60)
        progress = congress - start + 1
        total = end - start + 1
        logger.info("Starting backfill for Congress %d (%d of %d)", congress, progress, total)
        logger.info("=" * 60)

        try:
            async with async_session_factory() as session:
                ingester = GovInfoIngester(session, congress=congress)
                try:
                    await ingester.ingest()
                finally:
                    await ingester.close()
            logger.info("Completed Congress %d successfully", congress)
        except Exception:
            logger.exception("Failed to backfill Congress %d", congress)
            logger.info("Resume with: python -m scripts.backfill_historical --start %d", congress)
            raise

    logger.info("Historical backfill complete: Congress %d-%d", start, end)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill historical federal bills")
    parser.add_argument(
        "--start", type=int, default=110, help="First congress to backfill (default: 110)"
    )
    parser.add_argument(
        "--end", type=int, default=118, help="Last congress to backfill (default: 118)"
    )
    args = parser.parse_args()

    if args.start > args.end:
        print(f"Error: --start ({args.start}) must be <= --end ({args.end})", file=sys.stderr)
        sys.exit(1)

    asyncio.run(backfill(args.start, args.end))


if __name__ == "__main__":
    main()
