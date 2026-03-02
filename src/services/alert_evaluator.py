"""Alert evaluator — matches bill change events against saved searches."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.alert_subscription import AlertSubscription
from src.models.bill import Bill
from src.models.bill_change_event import BillChangeEvent
from src.models.saved_search import SavedSearch
from src.models.webhook_endpoint import WebhookEndpoint
from src.services.webhook_dispatcher import enqueue_delivery

logger = logging.getLogger(__name__)

# Map change_type to webhook event_type
CHANGE_TYPE_TO_EVENT = {
    "created": "bill.created",
    "status_changed": "bill.status_changed",
    "updated": "bill.updated",
    "text_added": "bill.text_added",
    "action_added": "bill.action_added",
}


async def evaluate_alerts_for_changes(
    session: AsyncSession,
    change_events: list[BillChangeEvent],
) -> int:
    """Match change events against saved searches with active alerts.

    Returns the number of webhook deliveries enqueued.
    """
    if not change_events:
        return 0

    # Collect unique bill IDs from changes
    bill_ids = {e.bill_id for e in change_events}

    # Fetch bill metadata for matching
    bill_result = await session.execute(select(Bill).where(Bill.id.in_(bill_ids)))
    bills = {b.id: b for b in bill_result.scalars().all()}

    # Find all saved searches with alerts enabled
    search_result = await session.execute(
        select(SavedSearch).where(SavedSearch.alerts_enabled.is_(True))
    )
    saved_searches = list(search_result.scalars().all())

    if not saved_searches:
        return 0

    search_ids = [s.id for s in saved_searches]

    # Batch-load all active subscriptions for these searches (avoids N+1)
    sub_result = await session.execute(
        select(AlertSubscription).where(
            AlertSubscription.saved_search_id.in_(search_ids),
            AlertSubscription.is_active.is_(True),
        )
    )
    all_subs = list(sub_result.scalars().all())

    if not all_subs:
        return 0

    # Group subscriptions by saved_search_id
    subs_by_search: dict[int, list[AlertSubscription]] = {}
    for sub in all_subs:
        subs_by_search.setdefault(sub.saved_search_id, []).append(sub)

    # Batch-load all active webhook endpoints referenced by subscriptions (avoids N+1)
    endpoint_ids = {sub.webhook_endpoint_id for sub in all_subs}
    ep_result = await session.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id.in_(endpoint_ids),
            WebhookEndpoint.is_active.is_(True),
        )
    )
    endpoints = {ep.id: ep for ep in ep_result.scalars().all()}

    enqueued = 0

    for search in saved_searches:
        subscriptions = subs_by_search.get(search.id, [])
        if not subscriptions:
            continue

        # Evaluate each change event against search criteria
        for event in change_events:
            bill = bills.get(event.bill_id)
            if not bill:
                continue

            if not _matches_criteria(bill, search.criteria):
                continue

            event_type = CHANGE_TYPE_TO_EVENT.get(event.change_type, "bill.updated")

            for sub in subscriptions:
                if event_type not in sub.event_types:
                    continue

                endpoint = endpoints.get(sub.webhook_endpoint_id)
                if not endpoint:
                    continue

                payload = _build_payload(event, bill, event_type)
                await enqueue_delivery(session, endpoint, event_type, payload)
                enqueued += 1

    if enqueued:
        await session.flush()
        logger.info(
            "Enqueued %d webhook deliveries from %d changes",
            enqueued,
            len(change_events),
        )

    return enqueued


def _matches_criteria(bill: Bill, criteria: dict) -> bool:
    """Check if a bill matches saved search criteria (filter-only evaluation)."""
    # Jurisdiction filter
    jurisdiction_id = criteria.get("jurisdiction_id")
    if jurisdiction_id and bill.jurisdiction_id != jurisdiction_id:
        return False

    # Status filter
    status = criteria.get("status")
    if status and bill.status != status:
        return False

    # Keyword filter (case-insensitive substring match on title)
    query = criteria.get("query")
    if query and query.lower() not in (bill.title or "").lower():
        return False

    return True


def _build_payload(event: BillChangeEvent, bill: Bill, event_type: str) -> dict:
    """Build the webhook delivery payload."""
    return {
        "event_type": event_type,
        "bill_id": bill.id,
        "identifier": bill.identifier,
        "jurisdiction_id": bill.jurisdiction_id,
        "title": bill.title,
        "change_summary": {
            "change_type": event.change_type,
            "field_name": event.field_name,
            "old_value": event.old_value,
            "new_value": event.new_value,
        },
        "detail_url": f"/api/v1/bills/{bill.id}",
    }
