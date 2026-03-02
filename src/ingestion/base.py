from abc import ABC, abstractmethod
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.bill_change_event import BillChangeEvent
from src.models.ingestion_run import IngestionRun
from src.services.change_tracker import (
    batch_get_existing_bills,
    get_existing_bill,
    track_bill_changes,
)


class BaseIngester(ABC):
    """Base class for all data source ingesters."""

    source_name: str = ""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.run: IngestionRun | None = None
        self.change_events: list[BillChangeEvent] = []
        self._old_values_cache: dict[str, dict | None] = {}

    async def start_run(self, run_type: str = "full") -> IngestionRun:
        self.run = IngestionRun(
            source=self.source_name,
            run_type=run_type,
            status="running",
        )
        self.session.add(self.run)
        await self.session.flush()
        self.change_events = []
        return self.run

    async def finish_run(self, status: str = "completed") -> None:
        if self.run:
            self.run.status = status
            self.run.finished_at = datetime.now(tz=UTC)
            await self.session.commit()

    async def _prefetch_old_values(self, bill_ids: list[str]) -> None:
        """Batch-load tracked field values for a page of bills (single IN query)."""
        self._old_values_cache = await batch_get_existing_bills(self.session, bill_ids)

    async def _get_old_values(self, bill_id: str) -> dict | None:
        """Fetch existing bill field values before upsert (for change tracking).

        Uses batch cache when available, falls back to individual query.
        """
        if bill_id in self._old_values_cache:
            return self._old_values_cache.pop(bill_id)
        return await get_existing_bill(self.session, bill_id)

    async def _track_changes(
        self,
        bill_id: str,
        old_values: dict | None,
        new_values: dict,
    ) -> list[BillChangeEvent]:
        """Record field-level changes for a bill. Call after upsert."""
        run_id = self.run.id if self.run else None
        events = await track_bill_changes(self.session, bill_id, old_values, new_values, run_id)
        self.change_events.extend(events)
        return events

    @abstractmethod
    async def ingest(self) -> None:
        """Run the ingestion pipeline."""
        ...
