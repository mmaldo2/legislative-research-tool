"""Add GIN index on bills.classification for array containment queries.

Revision ID: 009_add_bills_classification_gin_index
Revises: 008_add_introduced_date
Create Date: 2026-03-18

Supports @> array containment operator on bills.classification.
Uses CONCURRENTLY to avoid ACCESS EXCLUSIVE locks in production.
"""

from alembic import op

# revision identifiers
revision = "009_add_bills_classification_gin_index"
down_revision = "008_add_introduced_date"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_bills_classification_gin",
            "bills",
            ["classification"],
            postgresql_using="gin",
            postgresql_concurrently=True,
            postgresql_where="classification IS NOT NULL",
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_bills_classification_gin",
            "bills",
            postgresql_concurrently=True,
            if_not_exists=True,
        )
