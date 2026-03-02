"""Add composite index on webhook_deliveries for queue polling.

Revision ID: 006_add_delivery_queue_composite_index
Revises: 005_add_webhook_alert_tables
Create Date: 2026-03-01
"""

from alembic import op

# revision identifiers
revision = "006_add_delivery_queue_composite_index"
down_revision = "005_add_webhook_alert_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Composite index for the delivery queue poll query:
    # WHERE status IN ('queued','failed') AND next_retry_at <= now()
    # ORDER BY next_retry_at
    op.create_index(
        "ix_webhook_deliveries_status_next_retry_at",
        "webhook_deliveries",
        ["status", "next_retry_at"],
    )

    # Drop individual indexes now covered by the composite
    op.drop_index("ix_webhook_deliveries_status", "webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_next_retry_at", "webhook_deliveries")


def downgrade() -> None:
    # Restore individual indexes
    op.create_index("ix_webhook_deliveries_status", "webhook_deliveries", ["status"])
    op.create_index(
        "ix_webhook_deliveries_next_retry_at", "webhook_deliveries", ["next_retry_at"]
    )

    op.drop_index("ix_webhook_deliveries_status_next_retry_at", "webhook_deliveries")
