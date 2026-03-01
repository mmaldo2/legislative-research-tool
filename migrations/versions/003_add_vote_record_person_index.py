"""Add index on vote_records.person_id for person-centric vote queries.

Revision ID: 003_add_vote_record_person_index
Revises: 002_rename_ingestion_run_fields
Create Date: 2026-03-01
"""

from alembic import op

# revision identifiers
revision = "003_add_vote_record_person_index"
down_revision = "002_rename_ingestion_run_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_vote_records_person_id", "vote_records", ["person_id"])


def downgrade() -> None:
    op.drop_index("ix_vote_records_person_id", "vote_records")
