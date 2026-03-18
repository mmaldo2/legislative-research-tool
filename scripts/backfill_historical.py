"""Backfill historical federal bills from Congress 110-118.

Runs the GovInfo ingester for each historical congress, one at a time.
Each congress gets its own IngestionRun for tracking and resumability.

Usage:
    python -m scripts.backfill_historical
    python -m scripts.backfill_historical --start 114 --end 118
    python -m scripts.backfill_historical --enrich-only --start 110 --end 118
    python -m scripts.backfill_historical --no-enrich --start 118 --end 118
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


async def backfill(start: int, end: int, enrich: bool, enrich_only: bool) -> None:
    """Run GovInfo ingestion for each congress in the range."""
    for congress in range(start, end + 1):
        logger.info("=" * 60)
        progress = congress - start + 1
        total = end - start + 1
        logger.info(
            "Starting %s for Congress %d (%d of %d)",
            "enrichment" if enrich_only else "backfill",
            congress,
            progress,
            total,
        )
        logger.info("=" * 60)

        try:
            async with async_session_factory() as session:
                ingester = GovInfoIngester(session, congress=congress)
                try:
                    if enrich_only:
                        await ingester._ensure_jurisdiction()
                        await ingester._ensure_session()
                        await ingester.enrich_bills()
                    else:
                        await ingester.ingest(enrich=enrich)
                finally:
                    await ingester.close()
            logger.info("Completed Congress %d successfully", congress)
        except Exception:
            logger.exception("Failed Congress %d", congress)
            logger.info(
                "Resume with: python -m scripts.backfill_historical --start %d", congress
            )
            raise

    logger.info("Complete: Congress %d-%d", start, end)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill historical federal bills")
    parser.add_argument(
        "--start", type=int, default=110, help="First congress (default: 110)"
    )
    parser.add_argument(
        "--end", type=int, default=118, help="Last congress (default: 118)"
    )
    parser.add_argument(
        "--enrich-only",
        action="store_true",
        help="Only run detail enrichment (skip list fetch)",
    )
    parser.add_argument(
        "--no-enrich",
        action="store_true",
        help="Skip detail enrichment (list fetch only)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Override CONGRESS_API_KEY (for parallel runs with separate keys)",
    )
    args = parser.parse_args()

    if args.api_key:
        import os

        os.environ["CONGRESS_API_KEY"] = args.api_key

    if args.start > args.end:
        print(
            f"Error: --start ({args.start}) must be <= --end ({args.end})",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.enrich_only and args.no_enrich:
        print("Error: --enrich-only and --no-enrich are mutually exclusive", file=sys.stderr)
        sys.exit(1)

    asyncio.run(
        backfill(args.start, args.end, enrich=not args.no_enrich, enrich_only=args.enrich_only)
    )


if __name__ == "__main__":
    main()
