"""Ingestion scheduler using APScheduler.

Runs background jobs for periodic data refresh:
- Daily: federal bills from GovInfo
- Daily: Federal Register regulatory documents (6:00 AM UTC)
- Weekly: state bills from Open States (all 50 states)
- Weekly: congress legislators update
- Weekly: LegiScan dataset cross-reference (Saturdays 5:00 AM UTC)
- Weekly: committee hearings (Wednesdays 5:00 AM UTC)
- Weekly: CRS reports (Thursdays 5:00 AM UTC)
"""

import logging
from collections.abc import Callable
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.database import async_session_factory
from src.ingestion.base import BaseIngester

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _run_ingestion(
    label: str,
    factory: Callable[..., BaseIngester],
    **kwargs: Any,
) -> None:
    """Generic scheduled ingestion runner."""
    logger.info("Scheduled: starting %s ingestion", label)
    async with async_session_factory() as session:
        ingester = factory(session, **kwargs)
        try:
            await ingester.ingest()
            logger.info("Scheduled: %s ingestion completed", label)
        except Exception as e:
            logger.error("Scheduled: %s ingestion failed: %s", label, e)
        finally:
            await ingester.close()


async def _run_federal_ingestion() -> None:
    """Scheduled job: ingest federal bills."""
    from src.ingestion.govinfo import GovInfoIngester

    await _run_ingestion("federal", GovInfoIngester, congress=119)


async def _run_state_ingestion() -> None:
    """Scheduled job: ingest all 50 states."""
    from src.ingestion.openstates import STATE_JURISDICTIONS, OpenStatesIngester

    states = list(STATE_JURISDICTIONS.keys())
    await _run_ingestion("state", OpenStatesIngester, states=states)


async def _run_legislators_ingestion() -> None:
    """Scheduled job: update congress legislators."""
    from src.ingestion.congress_legislators import CongressLegislatorsIngester

    await _run_ingestion("legislators", CongressLegislatorsIngester)


async def _run_legiscan_ingestion() -> None:
    """Scheduled job: ingest LegiScan weekly datasets."""
    from src.ingestion.legiscan import LegiScanIngester

    await _run_ingestion("legiscan", LegiScanIngester)


async def _run_federal_register_ingestion() -> None:
    """Scheduled job: ingest Federal Register regulatory documents."""
    from src.ingestion.federal_register import FederalRegisterIngester

    await _run_ingestion("federal_register", FederalRegisterIngester, lookback_days=7)


async def _run_hearings_ingestion() -> None:
    """Scheduled job: ingest committee hearings from Congress.gov."""
    from src.ingestion.committee_hearings import CommitteeHearingIngester

    await _run_ingestion("hearings", CommitteeHearingIngester, congress=119)


async def _run_crs_reports_ingestion() -> None:
    """Scheduled job: ingest CRS reports from EveryCRSReport.com."""
    from src.ingestion.crs_reports import CrsReportIngester

    await _run_ingestion("crs_reports", CrsReportIngester, months_back=1, max_reports=200)


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

    # Weekly LegiScan cross-reference — Saturdays at 5:00 AM UTC
    scheduler.add_job(
        _run_legiscan_ingestion,
        "cron",
        day_of_week="sat",
        hour=5,
        minute=0,
        id="legiscan_ingestion",
        replace_existing=True,
    )

    # Daily Federal Register regulatory documents — 6:00 AM UTC
    scheduler.add_job(
        _run_federal_register_ingestion,
        "cron",
        hour=6,
        minute=0,
        id="federal_register_ingestion",
        replace_existing=True,
    )

    # Weekly committee hearings — Wednesdays at 5:00 AM UTC
    scheduler.add_job(
        _run_hearings_ingestion,
        "cron",
        day_of_week="wed",
        hour=5,
        minute=0,
        id="hearings_ingestion",
        replace_existing=True,
    )

    # Weekly CRS reports — Thursdays at 5:00 AM UTC
    scheduler.add_job(
        _run_crs_reports_ingestion,
        "cron",
        day_of_week="thu",
        hour=5,
        minute=0,
        id="crs_reports_ingestion",
        replace_existing=True,
    )

    logger.info("Ingestion scheduler configured with 7 jobs")
    return scheduler
