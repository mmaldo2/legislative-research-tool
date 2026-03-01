"""Rename bills_created/bills_updated to records_created/records_updated.

These fields track records for all source types (bills, people, etc.),
not just bills. Generic names avoid semantic confusion.

Revision ID: 002
"""

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("ingestion_runs", "bills_created", new_column_name="records_created")
    op.alter_column("ingestion_runs", "bills_updated", new_column_name="records_updated")


def downgrade() -> None:
    op.alter_column("ingestion_runs", "records_created", new_column_name="bills_created")
    op.alter_column("ingestion_runs", "records_updated", new_column_name="bills_updated")
