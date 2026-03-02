"""Add organizations and api_keys tables, add org_id to collections and conversations.

Revision ID: 004_add_org_apikey_tables
Revises: 003_add_vote_record_person_index
Create Date: 2026-03-01
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers
revision = "004_add_org_apikey_tables"
down_revision = "003_add_vote_record_person_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Organizations table
    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("plan", sa.String(), nullable=False, server_default="free"),
        sa.Column("settings", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    # API keys table
    op.create_table(
        "api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("prefix", sa.String(), nullable=False, server_default="sk_live_"),
        sa.Column("key_hash", sa.String(), nullable=False),
        sa.Column("key_hint", sa.String(), nullable=False),
        sa.Column("scopes", JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index("ix_api_keys_org_id", "api_keys", ["org_id"])
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])

    # Add org_id to collections
    op.add_column(
        "collections",
        sa.Column(
            "org_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_collections_org_id", "collections", ["org_id"])

    # Add org_id to conversations
    op.add_column(
        "conversations",
        sa.Column(
            "org_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_conversations_org_id", "conversations", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_conversations_org_id", "conversations")
    op.drop_column("conversations", "org_id")
    op.drop_index("ix_collections_org_id", "collections")
    op.drop_column("collections", "org_id")
    op.drop_index("ix_api_keys_key_hash", "api_keys")
    op.drop_index("ix_api_keys_org_id", "api_keys")
    op.drop_table("api_keys")
    op.drop_index("ix_organizations_slug", "organizations")
    op.drop_table("organizations")
