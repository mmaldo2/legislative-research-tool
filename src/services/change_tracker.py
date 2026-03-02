"""Change tracker — detects field-level changes during bill ingestion."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.bill import Bill
from src.models.bill_change_event import BillChangeEvent

logger = logging.getLogger(__name__)

# Fields compared during upsert to detect meaningful changes
TRACKED_FIELDS = ["title", "status", "status_date", "subject"]


async def get_existing_bill(session: AsyncSession, bill_id: str) -> dict | None:
    """Fetch current values for tracked fields. Returns None if bill doesn't exist."""
    result = await session.execute(select(Bill).where(Bill.id == bill_id))
    bill = result.scalar_one_or_none()
    if not bill:
        return None
    return {field: _serialize(getattr(bill, field, None)) for field in TRACKED_FIELDS}


async def track_bill_changes(
    session: AsyncSession,
    bill_id: str,
    old_values: dict | None,
    new_values: dict,
    ingestion_run_id: int | None = None,
) -> list[BillChangeEvent]:
    """Compare old vs new field values and emit BillChangeEvent records.

    Args:
        old_values: Previous field values (None if bill is new).
        new_values: New field values being upserted.
        ingestion_run_id: FK to current ingestion run.

    Returns:
        List of created BillChangeEvent records.
    """
    changes: list[BillChangeEvent] = []

    if old_values is None:
        # Brand new bill — emit a single "created" event
        event = BillChangeEvent(
            bill_id=bill_id,
            change_type="created",
            ingestion_run_id=ingestion_run_id,
        )
        session.add(event)
        changes.append(event)
        return changes

    # Compare tracked fields
    for field in TRACKED_FIELDS:
        old_val = old_values.get(field)
        new_val = _serialize(new_values.get(field))

        if old_val == new_val:
            continue

        change_type = "status_changed" if field == "status" else "updated"
        event = BillChangeEvent(
            bill_id=bill_id,
            change_type=change_type,
            field_name=field,
            old_value=str(old_val) if old_val is not None else None,
            new_value=str(new_val) if new_val is not None else None,
            ingestion_run_id=ingestion_run_id,
        )
        session.add(event)
        changes.append(event)

    if changes:
        logger.debug("Tracked %d changes for bill %s", len(changes), bill_id)

    return changes


def _serialize(value: object) -> str | None:
    """Normalize a value for comparison."""
    if value is None:
        return None
    if isinstance(value, list):
        return ",".join(str(v) for v in sorted(value))
    return str(value)
