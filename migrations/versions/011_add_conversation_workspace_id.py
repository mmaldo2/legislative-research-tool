"""Add workspace_id to conversations for workspace-scoped chat.

Revision ID: 011_add_conversation_workspace_id
Revises: 010_add_policy_workspace_tables
Create Date: 2026-03-21
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "011_add_conversation_workspace_id"
down_revision = "010_add_policy_workspace_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "workspace_id",
            sa.String(),
            sa.ForeignKey("policy_workspaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_conversations_workspace_id",
        "conversations",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_workspace_id", table_name="conversations")
    op.drop_column("conversations", "workspace_id")
