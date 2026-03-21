"""Policy workspace models for composer-driven legislative drafting."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


def _hex_uuid() -> str:
    return uuid.uuid4().hex


class PolicyWorkspace(Base):
    __tablename__ = "policy_workspaces"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_hex_uuid)
    client_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    target_jurisdiction_id: Mapped[str] = mapped_column(
        ForeignKey("jurisdictions.id"),
        nullable=False,
        index=True,
    )
    drafting_template: Mapped[str] = mapped_column(String, nullable=False)
    goal_prompt: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False, default="setup", index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    precedents: Mapped[list["PolicyWorkspacePrecedent"]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="PolicyWorkspacePrecedent.position",
    )
    sections: Mapped[list["PolicySection"]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="PolicySection.position",
    )
    generations: Mapped[list["PolicyGeneration"]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="PolicyGeneration.created_at",
    )


class PolicyWorkspacePrecedent(Base):
    __tablename__ = "policy_workspace_precedents"
    __table_args__ = (UniqueConstraint("workspace_id", "bill_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("policy_workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bill_id: Mapped[str] = mapped_column(ForeignKey("bills.id"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    workspace: Mapped["PolicyWorkspace"] = relationship(back_populates="precedents")
    bill: Mapped["Bill"] = relationship()


class PolicySection(Base):
    __tablename__ = "policy_sections"
    __table_args__ = (UniqueConstraint("workspace_id", "section_key"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_hex_uuid)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("policy_workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_key: Mapped[str] = mapped_column(String, nullable=False)
    heading: Mapped[str] = mapped_column(String, nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String, nullable=False, default="outlined")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    workspace: Mapped["PolicyWorkspace"] = relationship(back_populates="sections")
    generations: Mapped[list["PolicyGeneration"]] = relationship(
        back_populates="section",
        cascade="save-update, merge",
        passive_deletes=True,
        order_by="PolicyGeneration.created_at",
    )
    revisions: Mapped[list["PolicySectionRevision"]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="PolicySectionRevision.created_at",
    )


class PolicyGeneration(Base):
    __tablename__ = "policy_generations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_hex_uuid)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("policy_workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_id: Mapped[str | None] = mapped_column(
        ForeignKey("policy_sections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(String, nullable=False)
    instruction_text: Mapped[str | None] = mapped_column(Text)
    selected_text: Mapped[str | None] = mapped_column(Text)
    output_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    accepted_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("policy_section_revisions.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    workspace: Mapped["PolicyWorkspace"] = relationship(back_populates="generations")
    section: Mapped["PolicySection | None"] = relationship(back_populates="generations")


class PolicySectionRevision(Base):
    __tablename__ = "policy_section_revisions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_hex_uuid)
    section_id: Mapped[str] = mapped_column(
        ForeignKey("policy_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    generation_id: Mapped[str | None] = mapped_column(
        ForeignKey("policy_generations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    change_source: Mapped[str] = mapped_column(String, nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    section: Mapped["PolicySection"] = relationship(back_populates="revisions")
