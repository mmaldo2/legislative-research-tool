"""Add time-series indexes for trend aggregation queries.

Revision ID: 007_add_timeseries_indexes
Revises: 006_add_delivery_queue_composite_index
Create Date: 2026-03-02

Note: All indexes use CONCURRENTLY to avoid ACCESS EXCLUSIVE locks in production.
This migration must run outside a transaction (autocommit_block).
"""

from alembic import op

# revision identifiers
revision = "007_add_timeseries_indexes"
down_revision = "006_add_delivery_queue_composite_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        # bill_actions: btree on action_date for time-bucketed action queries
        op.create_index(
            "ix_bill_actions_action_date",
            "bill_actions",
            ["action_date"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )

        # bill_actions: composite for bill-scoped action lookups ordered by date
        op.create_index(
            "ix_bill_actions_bill_id_action_date",
            "bill_actions",
            ["bill_id", "action_date"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )

        # bills: btree on created_at for time-bucketed bill queries
        op.create_index(
            "ix_bills_created_at",
            "bills",
            ["created_at"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )

        # bills: btree on updated_at for freshness sorting
        op.create_index(
            "ix_bills_updated_at",
            "bills",
            ["updated_at"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )

        # bills: partial GIN on subject ARRAY for containment queries (topic=X)
        op.create_index(
            "ix_bills_subject_gin",
            "bills",
            ["subject"],
            postgresql_using="gin",
            postgresql_concurrently=True,
            postgresql_where="subject IS NOT NULL",
            if_not_exists=True,
        )

        # ai_analyses: btree on created_at for analysis trend bucketing
        op.create_index(
            "ix_ai_analyses_created_at",
            "ai_analyses",
            ["created_at"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )

        # ingestion_runs: composite for source-filtered time queries
        op.create_index(
            "ix_ingestion_runs_source_started_at",
            "ingestion_runs",
            ["source", "started_at"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )

        # Composite indexes for filtered trend queries (P2-110)
        # bills: jurisdiction + date range for filtered bill trend queries
        op.create_index(
            "ix_bills_jurisdiction_created_at",
            "bills",
            ["jurisdiction_id", "created_at"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )

        # bills: session + date range for session-filtered bill trend queries
        op.create_index(
            "ix_bills_session_created_at",
            "bills",
            ["session_id", "created_at"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )

        # bill_actions: GIN on classification ARRAY for action_type queries
        op.create_index(
            "ix_bill_actions_classification_gin",
            "bill_actions",
            ["classification"],
            postgresql_using="gin",
            postgresql_concurrently=True,
            postgresql_where="classification IS NOT NULL",
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_bill_actions_classification_gin",
            "bill_actions",
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.drop_index(
            "ix_bills_session_created_at",
            "bills",
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.drop_index(
            "ix_bills_jurisdiction_created_at",
            "bills",
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.drop_index(
            "ix_ingestion_runs_source_started_at",
            "ingestion_runs",
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.drop_index(
            "ix_ai_analyses_created_at",
            "ai_analyses",
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.drop_index(
            "ix_bills_subject_gin",
            "bills",
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.drop_index(
            "ix_bills_updated_at",
            "bills",
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.drop_index(
            "ix_bills_created_at",
            "bills",
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.drop_index(
            "ix_bill_actions_bill_id_action_date",
            "bill_actions",
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.drop_index(
            "ix_bill_actions_action_date",
            "bill_actions",
            postgresql_concurrently=True,
            if_not_exists=True,
        )
