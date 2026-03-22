"""Service layer for composer outline generation, section drafting, and acceptance."""

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database import async_session_factory
from src.llm.harness import LLMHarness
from src.models.bill import Bill
from src.models.bill_text import texts_without_markup
from src.models.policy_workspace import (
    PolicyGeneration,
    PolicySection,
    PolicySectionRevision,
    PolicyWorkspace,
    PolicyWorkspacePrecedent,
)
from src.schemas.policy_workspace import COMPOSE_ACTION_TYPES, PolicyOutlineOutput
from src.services.bill_service import extract_bill_text

MAX_PRECEDENT_TEXT_CHARS = 4000


class OutlineGenerationError(RuntimeError):
    """Raised when the model returns an outline that fails domain validation."""


def _normalize_section_key(raw_key: str) -> str:
    """Convert a model-provided key into a stable slug."""
    slug = re.sub(r"[^a-z0-9]+", "_", raw_key.lower()).strip("_")
    return slug or "section"


def _latest_summary_text(bill: Bill) -> str | None:
    summaries = [
        analysis
        for analysis in bill.analyses
        if analysis.analysis_type == "summary" and analysis.result
    ]
    if not summaries:
        return None

    latest = max(
        summaries,
        key=lambda analysis: analysis.created_at or datetime.min.replace(tzinfo=UTC),
    )
    summary = latest.result.get("plain_english_summary")
    if not summary:
        return None
    return str(summary)


async def get_workspace_for_composer(
    session: AsyncSession,
    *,
    workspace_id: str,
    client_id: str,
) -> PolicyWorkspace | None:
    stmt = (
        select(PolicyWorkspace)
        .where(PolicyWorkspace.id == workspace_id)
        .options(
            selectinload(PolicyWorkspace.precedents).selectinload(PolicyWorkspacePrecedent.bill),
            selectinload(PolicyWorkspace.sections),
            selectinload(PolicyWorkspace.generations),
        )
    )
    result = await session.execute(stmt)
    workspace = result.scalar_one_or_none()
    if workspace is None:
        return None
    if workspace.client_id != client_id:
        raise PermissionError("Not authorized to access this policy workspace")
    return workspace


async def _load_precedent_bills(
    session: AsyncSession,
    *,
    workspace: PolicyWorkspace,
) -> dict[str, Bill]:
    bill_ids = [precedent.bill_id for precedent in workspace.precedents]
    result = await session.execute(
        select(Bill)
        .where(Bill.id.in_(bill_ids))
        .options(
            texts_without_markup(Bill.texts),
            selectinload(Bill.analyses),
        )
    )
    bills = result.scalars().all()
    return {bill.id: bill for bill in bills}


def _format_precedent_context(workspace: PolicyWorkspace, bill_map: dict[str, Bill]) -> str:
    parts: list[str] = []

    for precedent in workspace.precedents:
        bill = bill_map.get(precedent.bill_id)
        if bill is None:
            continue

        subjects = ", ".join(bill.subject) if bill.subject else "None"
        summary = _latest_summary_text(bill) or "No AI summary available."
        bill_text = extract_bill_text(bill)[:MAX_PRECEDENT_TEXT_CHARS]
        parts.append(
            f"Bill ID: {bill.id}\n"
            f"Identifier: {bill.identifier}\n"
            f"Jurisdiction: {bill.jurisdiction_id}\n"
            f"Title: {bill.title}\n"
            f"Status: {bill.status or 'unknown'}\n"
            f"Subjects: {subjects}\n"
            f"Summary: {summary}\n"
            f"Text Excerpt:\n{bill_text}\n"
        )

    return "\n---\n".join(parts)


def _unique_section_key(base_key: str, used_keys: set[str]) -> str:
    if base_key not in used_keys:
        used_keys.add(base_key)
        return base_key

    suffix = 2
    while f"{base_key}_{suffix}" in used_keys:
        suffix += 1
    section_key = f"{base_key}_{suffix}"
    used_keys.add(section_key)
    return section_key


def _enrich_outline_payload(
    outline: PolicyOutlineOutput,
    *,
    bill_map: dict[str, Bill],
) -> dict:
    if not outline.sections:
        raise OutlineGenerationError("Outline generation returned no sections")

    used_keys: set[str] = set()
    sections_payload: list[dict] = []

    for section in outline.sections:
        section_key = _unique_section_key(
            _normalize_section_key(section.section_key or section.heading),
            used_keys,
        )
        invalid_ids = [bill_id for bill_id in section.source_bill_ids if bill_id not in bill_map]
        if invalid_ids:
            raise OutlineGenerationError(
                f"Outline section '{section.heading}' cited unknown precedent IDs: "
                f"{', '.join(invalid_ids)}"
            )

        sources = []
        for index, bill_id in enumerate(section.source_bill_ids):
            bill = bill_map[bill_id]
            note = section.source_notes[index] if index < len(section.source_notes) else None
            sources.append(
                {
                    "bill_id": bill.id,
                    "identifier": bill.identifier,
                    "title": bill.title,
                    "jurisdiction_id": bill.jurisdiction_id,
                    "note": note,
                }
            )

        sections_payload.append(
            {
                "section_key": section_key,
                "heading": section.heading,
                "purpose": section.purpose,
                "sources": sources,
            }
        )

    return {
        "sections": sections_payload,
        "drafting_notes": outline.drafting_notes,
        "confidence": outline.confidence,
    }


async def generate_outline_for_workspace(
    *,
    harness: LLMHarness,
    workspace_id: str,
    client_id: str,
) -> PolicyWorkspace | None:
    # --- Load phase: hold DB connection briefly ---
    async with async_session_factory() as session:
        workspace = await get_workspace_for_composer(
            session,
            workspace_id=workspace_id,
            client_id=client_id,
        )
        if workspace is None:
            return None
        if not workspace.precedents:
            raise ValueError("Add at least one precedent bill before generating an outline")
        if workspace.sections:
            raise ValueError("Outline already exists for this workspace")
        if not workspace.target_jurisdiction_id or not workspace.drafting_template:
            raise ValueError("Target jurisdiction and drafting template are required")

        bill_map = await _load_precedent_bills(session, workspace=workspace)
        if len(bill_map) != len(workspace.precedents):
            raise LookupError("One or more precedent bills could not be loaded")

        # Extract values for LLM call before releasing connection
        ws_id = workspace.id
        ws_title = workspace.title
        ws_jurisdiction = workspace.target_jurisdiction_id
        ws_template = workspace.drafting_template
        ws_goal = workspace.goal_prompt
        precedents_text = _format_precedent_context(workspace, bill_map)
        precedent_count = len(workspace.precedents)

    # --- Call phase: no DB connection held ---
    outline = await harness.generate_policy_outline(
        workspace_id=ws_id,
        workspace_title=ws_title,
        target_jurisdiction=ws_jurisdiction,
        drafting_template=ws_template,
        goal_prompt=ws_goal,
        precedents_text=precedents_text,
        precedent_count=precedent_count,
    )
    outline_payload = _enrich_outline_payload(outline, bill_map=bill_map)

    # --- Persist phase: hold DB connection briefly ---
    async with async_session_factory() as session:
        generation = PolicyGeneration(
            workspace_id=ws_id,
            action_type="outline",
            output_payload=outline_payload,
            provenance={"precedent_bill_ids": list(bill_map.keys())},
        )
        session.add(generation)

        for position, section_payload in enumerate(outline_payload["sections"]):
            session.add(
                PolicySection(
                    workspace_id=ws_id,
                    section_key=section_payload["section_key"],
                    heading=section_payload["heading"],
                    purpose=section_payload["purpose"],
                    position=position,
                    content_markdown="",
                    status="outlined",
                )
            )

        # Update workspace status
        ws = await session.get(PolicyWorkspace, ws_id)
        if ws:
            ws.status = "outline_ready"
            ws.updated_at = datetime.now(UTC)

        await session.commit()

        return await get_workspace_for_composer(
            session,
            workspace_id=ws_id,
            client_id=client_id,
        )


async def update_workspace_section(
    session: AsyncSession,
    *,
    workspace_id: str,
    section_id: str,
    client_id: str,
    heading: str | None = None,
    update_heading: bool = False,
    purpose: str | None = None,
    update_purpose: bool = False,
) -> PolicyWorkspace | None:
    workspace = await get_workspace_for_composer(
        session,
        workspace_id=workspace_id,
        client_id=client_id,
    )
    if workspace is None:
        return None

    section = next(
        (candidate for candidate in workspace.sections if candidate.id == section_id),
        None,
    )
    if section is None:
        raise LookupError("Policy section not found")

    changed = False
    if update_heading:
        if not heading:
            raise ValueError("Section heading cannot be empty")
        if heading != section.heading:
            section.heading = heading
            changed = True
    if update_purpose and purpose != section.purpose:
        section.purpose = purpose
        changed = True

    if changed:
        section.status = "edited" if section.status == "outlined" else section.status
        section.updated_at = datetime.now(UTC)
        workspace.updated_at = datetime.now(UTC)
        await session.commit()

    return await get_workspace_for_composer(
        session,
        workspace_id=workspace_id,
        client_id=client_id,
    )


class ComposeError(RuntimeError):
    """Raised when a compose action fails domain validation."""


def _other_sections_summary(workspace: PolicyWorkspace, exclude_id: str) -> str:
    parts = []
    for section in sorted(workspace.sections, key=lambda s: s.position):
        if section.id == exclude_id:
            continue
        parts.append(f"- {section.heading}: {section.purpose or 'No purpose specified'}")
    return "\n".join(parts) or "No other sections"


async def compose_section(
    *,
    harness: LLMHarness,
    workspace_id: str,
    section_id: str,
    client_id: str,
    action_type: str,
    instruction_text: str | None = None,
    selected_text: str | None = None,
) -> PolicyGeneration:
    """Execute a compose action on a section, returning a pending generation."""
    if action_type not in COMPOSE_ACTION_TYPES:
        raise ValueError(f"Invalid action type: {action_type}")

    # --- Load phase: hold DB connection briefly ---
    async with async_session_factory() as session:
        workspace = await get_workspace_for_composer(
            session, workspace_id=workspace_id, client_id=client_id
        )
        if workspace is None:
            raise LookupError("Policy workspace not found")
        if not workspace.sections:
            raise ValueError("Generate an outline before composing sections")

        section = next((s for s in workspace.sections if s.id == section_id), None)
        if section is None:
            raise LookupError("Policy section not found")

        bill_map = await _load_precedent_bills(session, workspace=workspace)
        precedents_text = _format_precedent_context(workspace, bill_map)

        # Extract values for LLM call before releasing connection
        ws_id = workspace.id
        ws_title = workspace.title
        ws_jurisdiction = workspace.target_jurisdiction_id
        ws_template = workspace.drafting_template
        ws_goal = workspace.goal_prompt
        sec_id = section.id
        sec_heading = section.heading
        sec_purpose = section.purpose or ""
        sec_content = section.content_markdown
        other_sections = _other_sections_summary(workspace, section.id)

    # --- Call phase: no DB connection held ---
    if action_type == "analyze_constitutional":
        if not sec_content:
            raise ValueError("Section must have content before analyzing")
        analysis = await harness.analyze_draft_constitutional(
            workspace_id=ws_id,
            section_id=sec_id,
            draft_text=sec_content,
            section_heading=sec_heading,
            jurisdiction=ws_jurisdiction or "",
            goal_prompt=ws_goal,
        )
        output_payload = analysis.model_dump()
        output_payload["content_markdown"] = analysis.summary
        output_payload["rationale"] = f"Risk level: {analysis.risk_level}"
        provenance_sources: list[dict] = []
    elif action_type == "analyze_patterns":
        if not sec_content:
            raise ValueError("Section must have content before analyzing")
        analysis = await harness.analyze_draft_patterns(
            workspace_id=ws_id,
            section_id=sec_id,
            draft_text=sec_content,
            section_heading=sec_heading,
            jurisdiction=ws_jurisdiction or "",
            goal_prompt=ws_goal,
            precedent_context=precedents_text,
        )
        output_payload = analysis.model_dump()
        output_payload["content_markdown"] = analysis.summary
        output_payload["rationale"] = f"Pattern type: {analysis.pattern_type}"
        provenance_sources = []
    elif action_type == "draft_section":
        result = await harness.draft_policy_section(
            workspace_id=ws_id,
            section_id=sec_id,
            workspace_title=ws_title,
            target_jurisdiction=ws_jurisdiction,
            drafting_template=ws_template,
            goal_prompt=ws_goal,
            section_heading=sec_heading,
            section_purpose=sec_purpose,
            other_sections_summary=other_sections,
            precedents_text=precedents_text,
            instruction_text=instruction_text,
        )
        output_payload = None  # set below
        provenance_sources = []
    else:
        if not sec_content:
            raise ValueError("Section must have content before rewriting")
        result = await harness.rewrite_policy_section(
            workspace_id=ws_id,
            section_id=sec_id,
            action_type=action_type,
            workspace_title=ws_title,
            target_jurisdiction=ws_jurisdiction,
            section_heading=sec_heading,
            current_text=sec_content,
            selected_text=selected_text,
            instruction_text=instruction_text,
            precedents_text=precedents_text,
        )
        output_payload = None  # set below
        provenance_sources = []

    # Build output_payload and provenance for drafting/rewriting actions
    if output_payload is None:
        provenance_sources = []
        for idx, bid in enumerate(result.source_bill_ids):
            bill = bill_map.get(bid)
            if bill:
                note = result.source_notes[idx] if idx < len(result.source_notes) else None
                provenance_sources.append(
                    {
                        "bill_id": bill.id,
                        "identifier": bill.identifier,
                        "title": bill.title,
                        "jurisdiction_id": bill.jurisdiction_id,
                        "note": note,
                    }
                )
        output_payload = {
            "content_markdown": result.content_markdown,
            "rationale": result.rationale,
        }

    # --- Persist phase: hold DB connection briefly ---
    async with async_session_factory() as session:
        generation = PolicyGeneration(
            workspace_id=ws_id,
            section_id=sec_id,
            action_type=action_type,
            instruction_text=instruction_text,
            selected_text=selected_text,
            output_payload=output_payload,
            provenance={
                "precedent_bill_ids": list(bill_map.keys()),
                "sources": provenance_sources,
            },
        )
        session.add(generation)
        await session.commit()
        await session.refresh(generation)
        return generation


async def accept_generation(
    session: AsyncSession,
    *,
    workspace_id: str,
    generation_id: str,
    client_id: str,
) -> PolicySection:
    """Accept a pending generation: create revision and update section content atomically."""
    workspace = await get_workspace_for_composer(
        session, workspace_id=workspace_id, client_id=client_id
    )
    if workspace is None:
        raise LookupError("Policy workspace not found")

    generation = next((g for g in workspace.generations if g.id == generation_id), None)
    if generation is None:
        raise LookupError("Generation not found")
    if generation.accepted_revision_id is not None:
        raise ValueError("Generation already accepted")
    if generation.section_id is None:
        raise ValueError("Cannot accept a generation without a target section")

    section = next((s for s in workspace.sections if s.id == generation.section_id), None)
    if section is None:
        raise LookupError("Target section not found")

    content_markdown = (generation.output_payload or {}).get("content_markdown", "")
    if not content_markdown:
        raise ValueError("Generation has no content to accept")

    revision = PolicySectionRevision(
        section_id=section.id,
        generation_id=generation.id,
        change_source="ai",
        content_markdown=content_markdown,
    )
    session.add(revision)
    await session.flush()

    generation.accepted_revision_id = revision.id
    section.content_markdown = content_markdown
    section.status = "drafted"
    section.updated_at = datetime.now(UTC)
    workspace.status = "drafting"
    workspace.updated_at = datetime.now(UTC)

    await session.commit()
    await session.refresh(section)
    return section


async def get_section_history(
    session: AsyncSession,
    *,
    workspace_id: str,
    client_id: str,
    section_id: str | None = None,
) -> list[PolicySectionRevision]:
    """Return revision history for a workspace, optionally filtered to one section."""
    workspace = await get_workspace_for_composer(
        session, workspace_id=workspace_id, client_id=client_id
    )
    if workspace is None:
        raise LookupError("Policy workspace not found")

    section_ids = [s.id for s in workspace.sections]
    if not section_ids:
        return []

    stmt = (
        select(PolicySectionRevision)
        .where(PolicySectionRevision.section_id.in_(section_ids))
        .order_by(PolicySectionRevision.created_at.desc())
    )
    if section_id:
        if section_id not in section_ids:
            raise LookupError("Section not found in this workspace")
        stmt = stmt.where(PolicySectionRevision.section_id == section_id)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def export_workspace_markdown(
    session: AsyncSession,
    *,
    workspace_id: str,
    client_id: str,
) -> str:
    """Render a workspace draft as a single markdown document."""
    workspace = await get_workspace_for_composer(
        session, workspace_id=workspace_id, client_id=client_id
    )
    if workspace is None:
        raise LookupError("Policy workspace not found")

    lines: list[str] = []
    lines.append(f"# {workspace.title}")
    lines.append("")
    lines.append(f"**Target Jurisdiction:** {workspace.target_jurisdiction_id}")
    lines.append(f"**Drafting Template:** {workspace.drafting_template}")
    if workspace.goal_prompt:
        lines.append(f"**Policy Goal:** {workspace.goal_prompt}")
    lines.append("")
    lines.append("---")
    lines.append("")

    sections = sorted(workspace.sections, key=lambda s: s.position)
    for section in sections:
        lines.append(f"## Section {section.position + 1}. {section.heading}")
        lines.append("")
        if section.purpose:
            lines.append(f"*{section.purpose}*")
            lines.append("")
        if section.content_markdown:
            lines.append(section.content_markdown)
        else:
            lines.append("*(Not yet drafted)*")
        lines.append("")

    return "\n".join(lines)
