"""Add indexes on API filter columns.

Revision ID: 001_add_filter_indexes
Revises:
Create Date: 2026-02-28
"""

from alembic import op

# revision identifiers
revision = "001_add_filter_indexes"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Bill filter columns
    op.create_index("ix_bills_jurisdiction_id", "bills", ["jurisdiction_id"])
    op.create_index("ix_bills_session_id", "bills", ["session_id"])

    # Person filter columns
    op.create_index("ix_people_party", "people", ["party"])
    op.create_index("ix_people_current_jurisdiction_id", "people", ["current_jurisdiction_id"])
    op.create_index("ix_people_current_chamber", "people", ["current_chamber"])


def downgrade() -> None:
    op.drop_index("ix_people_current_chamber", "people")
    op.drop_index("ix_people_current_jurisdiction_id", "people")
    op.drop_index("ix_people_party", "people")
    op.drop_index("ix_bills_session_id", "bills")
    op.drop_index("ix_bills_jurisdiction_id", "bills")
