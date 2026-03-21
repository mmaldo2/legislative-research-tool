"""Add policy workspace composer tables.

Revision ID: 010_add_policy_workspace_tables
Revises: 009_add_bills_classification_gin_index
Create Date: 2026-03-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "010_add_policy_workspace_tables"
down_revision = "009_add_bills_classification_gin_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policy_workspaces",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("target_jurisdiction_id", sa.String(), nullable=False),
        sa.Column("drafting_template", sa.String(), nullable=False),
        sa.Column("goal_prompt", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_jurisdiction_id"], ["jurisdictions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_policy_workspaces_client_id"), "policy_workspaces", ["client_id"])
    op.create_index(op.f("ix_policy_workspaces_org_id"), "policy_workspaces", ["org_id"])
    op.create_index(
        op.f("ix_policy_workspaces_target_jurisdiction_id"),
        "policy_workspaces",
        ["target_jurisdiction_id"],
    )
    op.create_index(op.f("ix_policy_workspaces_status"), "policy_workspaces", ["status"])

    op.create_table(
        "policy_workspace_precedents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("bill_id", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["bill_id"], ["bills.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["policy_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "bill_id"),
    )
    op.create_index(
        op.f("ix_policy_workspace_precedents_workspace_id"),
        "policy_workspace_precedents",
        ["workspace_id"],
    )
    op.create_index(
        op.f("ix_policy_workspace_precedents_bill_id"),
        "policy_workspace_precedents",
        ["bill_id"],
    )

    op.create_table(
        "policy_sections",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("section_key", sa.String(), nullable=False),
        sa.Column("heading", sa.String(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["policy_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "section_key"),
    )
    op.create_index(op.f("ix_policy_sections_workspace_id"), "policy_sections", ["workspace_id"])

    op.create_table(
        "policy_generations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("section_id", sa.String(), nullable=True),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("instruction_text", sa.Text(), nullable=True),
        sa.Column("selected_text", sa.Text(), nullable=True),
        sa.Column("output_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("accepted_revision_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["section_id"], ["policy_sections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["policy_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_policy_generations_workspace_id"), "policy_generations", ["workspace_id"])
    op.create_index(op.f("ix_policy_generations_section_id"), "policy_generations", ["section_id"])

    op.create_table(
        "policy_section_revisions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("section_id", sa.String(), nullable=False),
        sa.Column("generation_id", sa.String(), nullable=True),
        sa.Column("change_source", sa.String(), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["generation_id"], ["policy_generations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["section_id"], ["policy_sections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_policy_section_revisions_section_id"),
        "policy_section_revisions",
        ["section_id"],
    )
    op.create_index(
        op.f("ix_policy_section_revisions_generation_id"),
        "policy_section_revisions",
        ["generation_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_policy_section_revisions_generation_id"), table_name="policy_section_revisions")
    op.drop_index(op.f("ix_policy_section_revisions_section_id"), table_name="policy_section_revisions")
    op.drop_table("policy_section_revisions")

    op.drop_index(op.f("ix_policy_generations_section_id"), table_name="policy_generations")
    op.drop_index(op.f("ix_policy_generations_workspace_id"), table_name="policy_generations")
    op.drop_table("policy_generations")

    op.drop_index(op.f("ix_policy_sections_workspace_id"), table_name="policy_sections")
    op.drop_table("policy_sections")

    op.drop_index(op.f("ix_policy_workspace_precedents_bill_id"), table_name="policy_workspace_precedents")
    op.drop_index(
        op.f("ix_policy_workspace_precedents_workspace_id"),
        table_name="policy_workspace_precedents",
    )
    op.drop_table("policy_workspace_precedents")

    op.drop_index(op.f("ix_policy_workspaces_status"), table_name="policy_workspaces")
    op.drop_index(
        op.f("ix_policy_workspaces_target_jurisdiction_id"),
        table_name="policy_workspaces",
    )
    op.drop_index(op.f("ix_policy_workspaces_org_id"), table_name="policy_workspaces")
    op.drop_index(op.f("ix_policy_workspaces_client_id"), table_name="policy_workspaces")
    op.drop_table("policy_workspaces")
