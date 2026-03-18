"""Add introduced_date to bills table.

Revision ID: 008_add_introduced_date
Revises: 007_add_timeseries_indexes
Create Date: 2026-03-17

Adds a dedicated introduced_date column to bills, backfilled from the earliest
bill_action date per bill. This supports both Phase 4C trend bucketing and
autoresearch temporal train/val/test splits.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "008_add_introduced_date"
down_revision = "007_add_timeseries_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bills", sa.Column("introduced_date", sa.Date(), nullable=True))

    # Backfill from earliest action per bill
    op.execute(
        """
        UPDATE bills b
        SET introduced_date = sub.earliest_date
        FROM (
            SELECT bill_id, MIN(action_date) AS earliest_date
            FROM bill_actions
            GROUP BY bill_id
        ) sub
        WHERE b.id = sub.bill_id AND b.introduced_date IS NULL
        """
    )

    # Concurrent indexes
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_bills_introduced_date",
            "bills",
            ["introduced_date"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        # Unique index for bulk action upserts (on_conflict_do_nothing)
        op.create_index(
            "ix_bill_actions_bill_date_desc_unique",
            "bill_actions",
            ["bill_id", "action_date", "description"],
            unique=True,
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_bill_actions_bill_date_desc_unique",
            "bill_actions",
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.drop_index(
            "ix_bills_introduced_date",
            "bills",
            postgresql_concurrently=True,
            if_not_exists=True,
        )
    op.drop_column("bills", "introduced_date")
