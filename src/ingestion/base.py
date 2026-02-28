from abc import ABC, abstractmethod
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ingestion_run import IngestionRun


class BaseIngester(ABC):
    """Base class for all data source ingesters."""

    source_name: str = ""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.run: IngestionRun | None = None

    async def start_run(self, run_type: str = "full") -> IngestionRun:
        self.run = IngestionRun(
            source=self.source_name,
            run_type=run_type,
            status="running",
        )
        self.session.add(self.run)
        await self.session.flush()
        return self.run

    async def finish_run(self, status: str = "completed") -> None:
        if self.run:
            self.run.status = status
            self.run.finished_at = datetime.now()
            await self.session.commit()

    @abstractmethod
    async def ingest(self) -> None:
        """Run the ingestion pipeline."""
        ...
