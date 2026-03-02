"""Add time-series indexes for trend aggregation queries.

Revision ID: 007_add_timeseries_indexes
Revises: 006_add_delivery_queue_composite_index
Create Date: 2026-03-02
"""

from alembic import op

# revision identifiers
revision = "007_add_timeseries_indexes"
down_revision = "006_add_delivery_queue_composite_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # bill_actions: btree on action_date for time-bucketed action queries
    op.create_index("ix_bill_actions_action_date", "bill_actions", ["action_date"])

    # bill_actions: composite for bill-scoped action lookups ordered by date
    op.create_index(
        "ix_bill_actions_bill_id_action_date",
        "bill_actions",
        ["bill_id", "action_date"],
    )

    # bills: btree on created_at for time-bucketed bill queries
    op.create_index("ix_bills_created_at", "bills", ["created_at"])

    # bills: btree on updated_at for freshness sorting
    op.create_index("ix_bills_updated_at", "bills", ["updated_at"])

    # bills: GIN on subject ARRAY for containment queries (topic=X)
    op.create_index(
        "ix_bills_subject_gin",
        "bills",
        ["subject"],
        postgresql_using="gin",
    )

    # ai_analyses: btree on created_at for analysis trend bucketing
    op.create_index("ix_ai_analyses_created_at", "ai_analyses", ["created_at"])

    # ingestion_runs: composite for source-filtered time queries
    op.create_index(
        "ix_ingestion_runs_source_started_at",
        "ingestion_runs",
        ["source", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_runs_source_started_at", "ingestion_runs")
    op.drop_index("ix_ai_analyses_created_at", "ai_analyses")
    op.drop_index("ix_bills_subject_gin", "bills")
    op.drop_index("ix_bills_updated_at", "bills")
    op.drop_index("ix_bills_created_at", "bills")
    op.drop_index("ix_bill_actions_bill_id_action_date", "bill_actions")
    op.drop_index("ix_bill_actions_action_date", "bill_actions")
