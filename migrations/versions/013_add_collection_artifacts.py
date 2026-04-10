"""Add collection_artifacts table for investigation memo storage.

Revision ID: 013_add_collection_artifacts
Revises: 012_add_generation_rejected_at
Create Date: 2026-04-09
"""

import sqlalchemy as sa
from alembic import op

revision = "013_add_collection_artifacts"
down_revision = "012_add_generation_rejected_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collection_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "collection_id",
            sa.Integer(),
            sa.ForeignKey("collections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artifact_type", sa.String(), nullable=False, server_default="memo"),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_collection_artifacts_collection_id",
        "collection_artifacts",
        ["collection_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_collection_artifacts_collection_id", table_name="collection_artifacts")
    op.drop_table("collection_artifacts")
