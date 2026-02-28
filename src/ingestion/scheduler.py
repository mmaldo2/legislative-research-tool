"""Ingestion scheduler using APScheduler.

Runs background jobs for periodic data refresh:
- Daily: federal bills from GovInfo
- Weekly: state bills from Open States (all 50 states)
- Weekly: congress legislators update
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.database import async_session_factory

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _run_federal_ingestion() -> None:
    """Scheduled job: ingest federal bills."""
    from src.ingestion.govinfo import GovInfoIngester

    logger.info("Scheduled: starting federal ingestion")
    async with async_session_factory() as session:
        ingester = GovInfoIngester(session, congress=119)
        try:
            await ingester.ingest()
            logger.info("Scheduled: federal ingestion completed")
        except Exception as e:
            logger.error("Scheduled: federal ingestion failed: %s", e)
        finally:
            await ingester.close()


async def _run_state_ingestion() -> None:
    """Scheduled job: ingest all 50 states."""
    from src.ingestion.openstates import STATE_JURISDICTIONS, OpenStatesIngester

    states = list(STATE_JURISDICTIONS.keys())
    logger.info("Scheduled: starting state ingestion for %d states", len(states))
    async with async_session_factory() as session:
        ingester = OpenStatesIngester(session, states=states)
        try:
            await ingester.ingest()
            logger.info("Scheduled: state ingestion completed")
        except Exception as e:
            logger.error("Scheduled: state ingestion failed: %s", e)
        finally:
            await ingester.close()


async def _run_legislators_ingestion() -> None:
    """Scheduled job: update congress legislators."""
    from src.ingestion.congress_legislators import CongressLegislatorsIngester

    logger.info("Scheduled: starting legislators ingestion")
    async with async_session_factory() as session:
        ingester = CongressLegislatorsIngester(session)
        try:
            await ingester.ingest()
            logger.info("Scheduled: legislators ingestion completed")
        except Exception as e:
            logger.error("Scheduled: legislators ingestion failed: %s", e)
        finally:
            await ingester.close()


def configure_scheduler() -> AsyncIOScheduler:
    """Configure and return the scheduler with all ingestion jobs."""
    # Daily federal check at 2:00 AM UTC
    scheduler.add_job(
        _run_federal_ingestion,
        "cron",
        hour=2,
        minute=0,
        id="federal_ingestion",
        replace_existing=True,
    )

    # Weekly state refresh — Sundays at 3:00 AM UTC
    scheduler.add_job(
        _run_state_ingestion,
        "cron",
        day_of_week="sun",
        hour=3,
        minute=0,
        id="state_ingestion",
        replace_existing=True,
    )

    # Weekly legislators update — Mondays at 4:00 AM UTC
    scheduler.add_job(
        _run_legislators_ingestion,
        "cron",
        day_of_week="mon",
        hour=4,
        minute=0,
        id="legislators_ingestion",
        replace_existing=True,
    )

    logger.info("Ingestion scheduler configured with 3 jobs")
    return scheduler
