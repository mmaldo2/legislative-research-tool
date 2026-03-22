"""Add rejected_at timestamp to policy_generations.

Revision ID: 012_add_generation_rejected_at
Revises: 011_add_conversation_workspace_id
Create Date: 2026-03-21
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "012_add_generation_rejected_at"
down_revision = "011_add_conversation_workspace_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "policy_generations",
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("policy_generations", "rejected_at")
