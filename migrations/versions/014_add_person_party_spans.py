"""Add person_party_spans table for vote-time party resolution.

Revision ID: 014_add_person_party_spans
Revises: 013_add_collection_artifacts
Create Date: 2026-06-26
"""

import sqlalchemy as sa
from alembic import op

revision = "014_add_person_party_spans"
down_revision = "013_add_collection_artifacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "person_party_spans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "person_id",
            sa.String(),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("party", sa.String(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.UniqueConstraint(
            "person_id", "start_date", name="uq_person_party_spans_person_start"
        ),
    )


def downgrade() -> None:
    op.drop_table("person_party_spans")
