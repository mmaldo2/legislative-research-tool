"""CLI interface for the legislative research tool.

Commands:
  ingest federal    — Fetch federal bills from GovInfo/Congress.gov
  ingest states     — Fetch state bills from Open States
  analyze bill <id> — Generate AI analysis for a specific bill
  status            — Show ingestion and analysis status
"""

import asyncio
import logging
import sys

import click

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Legislative Research Tool CLI."""
    pass


@cli.group()
def ingest():
    """Data ingestion commands."""
    pass


@ingest.command("federal")
@click.option("--congress", default=119, help="Congress number (default: 119)")
def ingest_federal(congress: int):
    """Ingest federal bills from GovInfo / Congress.gov API."""
    asyncio.run(_ingest_federal(congress))


async def _ingest_federal(congress: int):
    from src.database import async_session_factory
    from src.ingestion.govinfo import GovInfoIngester

    logger.info("Starting federal ingestion for %dth Congress", congress)
    async with async_session_factory() as session:
        ingester = GovInfoIngester(session, congress=congress)
        try:
            await ingester.ingest()
            logger.info("Federal ingestion completed successfully")
        finally:
            await ingester.close()


@ingest.command("states")
@click.option(
    "--states",
    default="ca,tx,ny",
    help="Comma-separated state abbreviations (default: ca,tx,ny)",
)
@click.option("--all-states", is_flag=True, help="Ingest all 50 states + DC + PR")
def ingest_states(states: str, all_states: bool):
    """Ingest state bills from Open States API."""
    if all_states:
        from src.ingestion.openstates import STATE_JURISDICTIONS

        state_list = list(STATE_JURISDICTIONS.keys())
    else:
        state_list = [s.strip() for s in states.split(",")]
    asyncio.run(_ingest_states(state_list))


async def _ingest_states(state_list: list[str]):
    from src.database import async_session_factory
    from src.ingestion.openstates import OpenStatesIngester

    logger.info("Starting state ingestion for: %s", ", ".join(s.upper() for s in state_list))
    async with async_session_factory() as session:
        ingester = OpenStatesIngester(session, states=state_list)
        try:
            await ingester.ingest()
            logger.info("State ingestion completed successfully")
        finally:
            await ingester.close()


@ingest.command("legislators")
def ingest_legislators():
    """Ingest Congress legislators from unitedstates/congress-legislators."""
    asyncio.run(_ingest_legislators())


async def _ingest_legislators():
    from src.database import async_session_factory
    from src.ingestion.congress_legislators import CongressLegislatorsIngester

    logger.info("Starting Congress legislators ingestion")
    async with async_session_factory() as session:
        ingester = CongressLegislatorsIngester(session)
        try:
            await ingester.ingest()
            logger.info("Congress legislators ingestion completed")
        finally:
            await ingester.close()


@cli.command("analyze")
@click.argument("bill_id")
def analyze_bill(bill_id: str):
    """Generate AI summary for a specific bill."""
    asyncio.run(_analyze_bill(bill_id))


async def _analyze_bill(bill_id: str):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from src.database import async_session_factory
    from src.llm.harness import LLMHarness
    from src.models.bill import Bill

    async with async_session_factory() as session:
        result = await session.execute(
            select(Bill)
            .options(selectinload(Bill.texts))
            .where(Bill.id == bill_id)
        )
        bill = result.scalar_one_or_none()

        if not bill:
            click.echo(f"Bill not found: {bill_id}")
            sys.exit(1)

        # Find bill text
        bill_text = None
        if bill.texts:
            for text in bill.texts:
                if text.content_text:
                    bill_text = text.content_text
                    break

        if not bill_text:
            click.echo(f"No text content available for bill {bill_id} ({bill.identifier})")
            click.echo("Try fetching bill text first with: legis fetch-text <bill_id>")
            sys.exit(1)

        harness = LLMHarness(db_session=session)
        click.echo(f"Analyzing {bill.identifier}: {bill.title[:80]}...")

        summary = await harness.summarize(
            bill_id=bill.id,
            bill_text=bill_text,
            identifier=bill.identifier,
            jurisdiction=bill.jurisdiction_id,
            title=bill.title,
        )

        await session.commit()

        click.echo("\n--- Summary ---")
        click.echo(summary.plain_english_summary)
        click.echo(f"\nKey Provisions: {len(summary.key_provisions)}")
        for provision in summary.key_provisions:
            click.echo(f"  - {provision}")
        click.echo(f"\nAffected Populations: {', '.join(summary.affected_populations)}")
        if summary.fiscal_implications:
            click.echo(f"Fiscal Implications: {summary.fiscal_implications}")
        click.echo(f"Confidence: {summary.confidence:.0%}")
        click.echo(f"\n{harness.cost_tracker.summary()}")


@cli.command("status")
def show_status():
    """Show database and ingestion status."""
    asyncio.run(_show_status())


async def _show_status():
    from sqlalchemy import func, select

    from src.database import async_session_factory
    from src.models.ai_analysis import AiAnalysis
    from src.models.bill import Bill
    from src.models.ingestion_run import IngestionRun
    from src.models.person import Person

    async with async_session_factory() as session:
        bill_count = await session.scalar(select(func.count(Bill.id)))
        person_count = await session.scalar(select(func.count(Person.id)))
        analysis_count = await session.scalar(select(func.count(AiAnalysis.id)))

        click.echo(f"Bills:    {bill_count or 0:,}")
        click.echo(f"People:   {person_count or 0:,}")
        click.echo(f"Analyses: {analysis_count or 0:,}")

        # Recent ingestion runs
        runs = await session.execute(
            select(IngestionRun)
            .order_by(IngestionRun.started_at.desc())
            .limit(5)
        )
        click.echo("\nRecent Ingestion Runs:")
        for run in runs.scalars():
            click.echo(
                f"  [{run.status}] {run.source} ({run.run_type}) "
                f"— {run.records_created} created, {run.records_updated} updated "
                f"— {run.started_at}"
            )


if __name__ == "__main__":
    cli()
