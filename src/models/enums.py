"""Shared enums for webhook delivery and bill change tracking."""

from enum import StrEnum


class DeliveryStatus(StrEnum):
    """Webhook delivery lifecycle states."""

    QUEUED = "queued"
    DELIVERED = "delivered"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class ChangeType(StrEnum):
    """Bill change event types emitted during ingestion."""

    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    TEXT_ADDED = "text_added"
    ACTION_ADDED = "action_added"
