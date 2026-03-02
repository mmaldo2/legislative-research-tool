"""Add webhook, alert, saved search, and bill change event tables.

Revision ID: 005_add_webhook_alert_tables
Revises: 004_add_org_apikey_tables
Create Date: 2026-03-01
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers
revision = "005_add_webhook_alert_tables"
down_revision = "004_add_org_apikey_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Bill change events — per-bill change tracking
    op.create_table(
        "bill_change_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "bill_id",
            sa.String(),
            sa.ForeignKey("bills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("change_type", sa.String(), nullable=False),
        sa.Column("field_name", sa.String(), nullable=True),
        sa.Column("old_value", sa.String(), nullable=True),
        sa.Column("new_value", sa.String(), nullable=True),
        sa.Column(
            "ingestion_run_id",
            sa.Integer(),
            sa.ForeignKey("ingestion_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_bill_change_events_bill_id", "bill_change_events", ["bill_id"])
    op.create_index("ix_bill_change_events_created_at", "bill_change_events", ["created_at"])

    # Saved searches — server-side persisted search criteria
    op.create_table(
        "saved_searches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("criteria", JSONB(), nullable=False),
        sa.Column("alerts_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_saved_searches_org_id", "saved_searches", ["org_id"])

    # Webhook endpoints — registered URLs for event delivery
    op.create_table(
        "webhook_endpoints",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("secret", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_webhook_endpoints_org_id", "webhook_endpoints", ["org_id"])

    # Alert subscriptions — link saved searches to webhook endpoints
    op.create_table(
        "alert_subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "saved_search_id",
            UUID(as_uuid=True),
            sa.ForeignKey("saved_searches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "webhook_endpoint_id",
            UUID(as_uuid=True),
            sa.ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_types", JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_alert_subscriptions_saved_search_id", "alert_subscriptions", ["saved_search_id"]
    )
    op.create_index(
        "ix_alert_subscriptions_webhook_endpoint_id",
        "alert_subscriptions",
        ["webhook_endpoint_id"],
    )

    # Webhook deliveries — delivery log / job queue with retry state
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "endpoint_id",
            UUID(as_uuid=True),
            sa.ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_webhook_deliveries_endpoint_id", "webhook_deliveries", ["endpoint_id"])
    op.create_index("ix_webhook_deliveries_status", "webhook_deliveries", ["status"])
    op.create_index(
        "ix_webhook_deliveries_next_retry_at", "webhook_deliveries", ["next_retry_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_deliveries_next_retry_at", "webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_status", "webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_endpoint_id", "webhook_deliveries")
    op.drop_table("webhook_deliveries")

    op.drop_index("ix_alert_subscriptions_webhook_endpoint_id", "alert_subscriptions")
    op.drop_index("ix_alert_subscriptions_saved_search_id", "alert_subscriptions")
    op.drop_table("alert_subscriptions")

    op.drop_index("ix_webhook_endpoints_org_id", "webhook_endpoints")
    op.drop_table("webhook_endpoints")

    op.drop_index("ix_saved_searches_org_id", "saved_searches")
    op.drop_table("saved_searches")

    op.drop_index("ix_bill_change_events_created_at", "bill_change_events")
    op.drop_index("ix_bill_change_events_bill_id", "bill_change_events")
    op.drop_table("bill_change_events")
