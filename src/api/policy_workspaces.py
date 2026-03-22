"""Policy workspace composer CRUD endpoints."""

import json
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import get_anthropic_client, get_llm_harness, get_session, limiter
from src.database import async_session_factory
from src.llm.harness import LLMHarness
from src.models.conversation import Conversation, ConversationMessage
from src.models.policy_workspace import PolicyWorkspace
from src.schemas.chat import (
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ToolCallInfo,
)
from src.schemas.common import MetaResponse
from src.schemas.policy_workspace import (
    PolicyComposeRequest,
    PolicyGenerationResponse,
    PolicyHistoryResponse,
    PolicyRevisionResponse,
    PolicySectionResponse,
    PolicySectionSourceResponse,
    PolicySectionUpdate,
    PolicyWorkspaceCreate,
    PolicyWorkspaceDetailResponse,
    PolicyWorkspaceListResponse,
    PolicyWorkspacePrecedentAdd,
    PolicyWorkspacePrecedentResponse,
    PolicyWorkspaceResponse,
    PolicyWorkspaceUpdate,
    PrecedentInsightsResponse,
    WorkspaceConversationListResponse,
    WorkspaceConversationSummary,
)
from src.services.policy_composer_service import (
    OutlineGenerationError,
    accept_generation,
    compose_section,
    export_workspace_markdown,
    generate_outline_for_workspace,
    get_section_history,
    update_workspace_section,
)
from src.services.policy_workspace_service import (
    add_precedent,
    create_workspace,
    delete_workspace,
    get_workspace_detail,
    get_workspace_for_client,
    list_workspaces,
    remove_precedent,
    update_workspace,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_client_id(x_client_id: str | None = Header(None)) -> str:
    """Get client ID from header or return 'anonymous'."""
    return x_client_id or "anonymous"


def _latest_outline_generation(workspace: PolicyWorkspace):
    outline_generations = [
        generation for generation in workspace.generations if generation.action_type == "outline"
    ]
    if not outline_generations:
        return None
    return max(
        outline_generations,
        key=lambda generation: generation.created_at or datetime.min.replace(tzinfo=UTC),
    )


def _build_workspace_detail_response(workspace: PolicyWorkspace) -> PolicyWorkspaceDetailResponse:
    latest_outline = _latest_outline_generation(workspace)
    provenance_map: dict[str, list[dict]] = {}
    outline_notes: list[str] = []
    outline_confidence: float | None = None
    outline_generated_at = None

    if latest_outline is not None:
        output_payload = latest_outline.output_payload or {}
        outline_notes = output_payload.get("drafting_notes", [])
        outline_confidence = output_payload.get("confidence")
        outline_generated_at = latest_outline.created_at
        for section_payload in output_payload.get("sections", []):
            section_key = section_payload.get("section_key")
            if section_key:
                provenance_map[section_key] = section_payload.get("sources", [])

    precedents = [
        PolicyWorkspacePrecedentResponse(
            id=precedent.id,
            bill_id=precedent.bill_id,
            position=precedent.position,
            added_at=precedent.added_at,
            identifier=precedent.bill.identifier,
            title=precedent.bill.title,
            jurisdiction_id=precedent.bill.jurisdiction_id,
            status=precedent.bill.status,
        )
        for precedent in sorted(workspace.precedents, key=lambda precedent: precedent.position)
    ]
    sections = [
        PolicySectionResponse(
            id=section.id,
            section_key=section.section_key,
            heading=section.heading,
            purpose=section.purpose,
            position=section.position,
            content_markdown=section.content_markdown,
            status=section.status,
            provenance=provenance_map.get(section.section_key, []),
            created_at=section.created_at,
            updated_at=section.updated_at,
        )
        for section in sorted(workspace.sections, key=lambda section: section.position)
    ]
    return PolicyWorkspaceDetailResponse(
        id=workspace.id,
        title=workspace.title,
        target_jurisdiction_id=workspace.target_jurisdiction_id,
        drafting_template=workspace.drafting_template,
        goal_prompt=workspace.goal_prompt,
        status=workspace.status,
        precedents=precedents,
        sections=sections,
        outline_drafting_notes=outline_notes,
        outline_confidence=outline_confidence,
        outline_generated_at=outline_generated_at,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
    )


async def _get_workspace_or_error(
    db: AsyncSession,
    *,
    workspace_id: str,
    client_id: str,
    load_detail: bool = False,
):
    getter = get_workspace_detail if load_detail else get_workspace_for_client
    try:
        workspace = await getter(db, workspace_id=workspace_id, client_id=client_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if workspace is None:
        raise HTTPException(status_code=404, detail="Policy workspace not found")
    return workspace


@router.post("/policy-workspaces", response_model=PolicyWorkspaceResponse, status_code=201)
@limiter.limit("30/minute")
async def create_policy_workspace(
    request: Request,
    body: PolicyWorkspaceCreate,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> PolicyWorkspaceResponse:
    try:
        workspace = await create_workspace(
            db,
            client_id=client_id,
            title=body.title,
            target_jurisdiction_id=body.target_jurisdiction_id,
            drafting_template=body.drafting_template,
            goal_prompt=body.goal_prompt,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PolicyWorkspaceResponse(
        id=workspace.id,
        title=workspace.title,
        target_jurisdiction_id=workspace.target_jurisdiction_id,
        drafting_template=workspace.drafting_template,
        goal_prompt=workspace.goal_prompt,
        status=workspace.status,
        precedent_count=0,
        section_count=0,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
    )


@router.get("/policy-workspaces", response_model=PolicyWorkspaceListResponse)
async def list_policy_workspaces(
    client_id: str = Depends(get_client_id),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
) -> PolicyWorkspaceListResponse:
    rows, total = await list_workspaces(db, client_id=client_id, page=page, per_page=per_page)
    data = [
        PolicyWorkspaceResponse(
            id=workspace.id,
            title=workspace.title,
            target_jurisdiction_id=workspace.target_jurisdiction_id,
            drafting_template=workspace.drafting_template,
            goal_prompt=workspace.goal_prompt,
            status=workspace.status,
            precedent_count=precedent_count,
            section_count=section_count,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
        )
        for workspace, precedent_count, section_count in rows
    ]
    latest = max((workspace.updated_at for workspace, _, _ in rows), default=None)
    return PolicyWorkspaceListResponse(
        data=data,
        meta=MetaResponse(
            total_count=total,
            page=page,
            per_page=per_page,
            sources=["policy-workspaces"],
            last_updated=latest.isoformat() if latest else None,
        ),
    )


@router.get("/policy-workspaces/{workspace_id}", response_model=PolicyWorkspaceDetailResponse)
async def get_policy_workspace(
    workspace_id: str,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> PolicyWorkspaceDetailResponse:
    workspace = await _get_workspace_or_error(
        db,
        workspace_id=workspace_id,
        client_id=client_id,
        load_detail=True,
    )
    return _build_workspace_detail_response(workspace)


@router.patch("/policy-workspaces/{workspace_id}", response_model=PolicyWorkspaceResponse)
@limiter.limit("30/minute")
async def update_policy_workspace(
    request: Request,
    workspace_id: str,
    body: PolicyWorkspaceUpdate,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> PolicyWorkspaceResponse:
    workspace = await _get_workspace_or_error(
        db,
        workspace_id=workspace_id,
        client_id=client_id,
    )

    try:
        updated = await update_workspace(
            db,
            workspace=workspace,
            title=body.title,
            target_jurisdiction_id=body.target_jurisdiction_id,
            drafting_template=body.drafting_template,
            goal_prompt=body.goal_prompt,
            update_goal_prompt="goal_prompt" in body.model_fields_set,
            status=body.status,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    detail = await _get_workspace_or_error(
        db,
        workspace_id=updated.id,
        client_id=client_id,
        load_detail=True,
    )
    return PolicyWorkspaceResponse(
        id=detail.id,
        title=detail.title,
        target_jurisdiction_id=detail.target_jurisdiction_id,
        drafting_template=detail.drafting_template,
        goal_prompt=detail.goal_prompt,
        status=detail.status,
        precedent_count=len(detail.precedents),
        section_count=len(detail.sections),
        created_at=detail.created_at,
        updated_at=detail.updated_at,
    )


@router.delete("/policy-workspaces/{workspace_id}", status_code=204)
@limiter.limit("30/minute")
async def delete_policy_workspace(
    request: Request,
    workspace_id: str,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> None:
    workspace = await _get_workspace_or_error(
        db,
        workspace_id=workspace_id,
        client_id=client_id,
    )
    await delete_workspace(db, workspace=workspace)


@router.post(
    "/policy-workspaces/{workspace_id}/precedents",
    response_model=PolicyWorkspacePrecedentResponse,
    status_code=201,
)
@limiter.limit("30/minute")
async def add_policy_workspace_precedent(
    request: Request,
    workspace_id: str,
    body: PolicyWorkspacePrecedentAdd,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> PolicyWorkspacePrecedentResponse:
    workspace = await _get_workspace_or_error(
        db,
        workspace_id=workspace_id,
        client_id=client_id,
    )

    try:
        precedent = await add_precedent(
            db,
            workspace=workspace,
            bill_id=body.bill_id,
            position=body.position,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        status_code = 409 if "already in workspace precedents" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    return PolicyWorkspacePrecedentResponse(
        id=precedent.id,
        bill_id=precedent.bill_id,
        position=precedent.position,
        added_at=precedent.added_at,
        identifier=precedent.bill.identifier,
        title=precedent.bill.title,
        jurisdiction_id=precedent.bill.jurisdiction_id,
        status=precedent.bill.status,
    )


@router.delete("/policy-workspaces/{workspace_id}/precedents/{bill_id}", status_code=204)
@limiter.limit("30/minute")
async def delete_policy_workspace_precedent(
    request: Request,
    workspace_id: str,
    bill_id: str,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> None:
    workspace = await _get_workspace_or_error(
        db,
        workspace_id=workspace_id,
        client_id=client_id,
    )

    try:
        await remove_precedent(db, workspace=workspace, bill_id=bill_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/policy-workspaces/{workspace_id}/outline/generate",
    response_model=PolicyWorkspaceDetailResponse,
)
@limiter.limit("5/minute")
async def generate_policy_workspace_outline(
    request: Request,
    workspace_id: str,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
    harness: LLMHarness = Depends(get_llm_harness),
) -> PolicyWorkspaceDetailResponse:
    try:
        workspace = await generate_outline_for_workspace(
            harness=harness,
            workspace_id=workspace_id,
            client_id=client_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OutlineGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if workspace is None:
        raise HTTPException(status_code=404, detail="Policy workspace not found")
    return _build_workspace_detail_response(workspace)


@router.patch(
    "/policy-workspaces/{workspace_id}/sections/{section_id}",
    response_model=PolicySectionResponse,
)
@limiter.limit("30/minute")
async def patch_policy_workspace_section(
    request: Request,
    workspace_id: str,
    section_id: str,
    body: PolicySectionUpdate,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> PolicySectionResponse:
    try:
        workspace = await update_workspace_section(
            db,
            workspace_id=workspace_id,
            section_id=section_id,
            client_id=client_id,
            heading=body.heading,
            update_heading="heading" in body.model_fields_set,
            purpose=body.purpose,
            update_purpose="purpose" in body.model_fields_set,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if workspace is None:
        raise HTTPException(status_code=404, detail="Policy workspace not found")

    detail = _build_workspace_detail_response(workspace)
    section = next((candidate for candidate in detail.sections if candidate.id == section_id), None)
    if section is None:
        raise HTTPException(status_code=404, detail="Policy section not found")
    return section


def _build_generation_response(generation) -> PolicyGenerationResponse:
    output = generation.output_payload or {}
    prov = generation.provenance or {}
    sources = [PolicySectionSourceResponse(**s) for s in prov.get("sources", [])]
    return PolicyGenerationResponse(
        id=generation.id,
        workspace_id=generation.workspace_id,
        section_id=generation.section_id,
        action_type=generation.action_type,
        instruction_text=generation.instruction_text,
        selected_text=generation.selected_text,
        output_markdown=output.get("content_markdown", ""),
        rationale=output.get("rationale", ""),
        provenance=sources,
        accepted=generation.accepted_revision_id is not None,
        created_at=generation.created_at,
    )


@router.post(
    "/policy-workspaces/{workspace_id}/sections/{section_id}/compose",
    response_model=PolicyGenerationResponse,
)
@limiter.limit("5/minute")
async def compose_policy_section(
    request: Request,
    workspace_id: str,
    section_id: str,
    body: PolicyComposeRequest,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
    harness: LLMHarness = Depends(get_llm_harness),
) -> PolicyGenerationResponse:
    try:
        generation = await compose_section(
            harness=harness,
            workspace_id=workspace_id,
            section_id=section_id,
            client_id=client_id,
            action_type=body.action_type,
            instruction_text=body.instruction_text,
            selected_text=body.selected_text,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _build_generation_response(generation)


@router.post(
    "/policy-workspaces/{workspace_id}/generations/{generation_id}/accept",
    response_model=PolicySectionResponse,
)
@limiter.limit("10/minute")
async def accept_policy_generation(
    request: Request,
    workspace_id: str,
    generation_id: str,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> PolicySectionResponse:
    try:
        section = await accept_generation(
            db,
            workspace_id=workspace_id,
            generation_id=generation_id,
            client_id=client_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    workspace = await _get_workspace_or_error(
        db, workspace_id=workspace_id, client_id=client_id, load_detail=True
    )
    detail = _build_workspace_detail_response(workspace)
    section_resp = next((s for s in detail.sections if s.id == section.id), None)
    if section_resp is None:
        raise HTTPException(status_code=404, detail="Section not found after accept")
    return section_resp


@router.post(
    "/policy-workspaces/{workspace_id}/generations/{generation_id}/reject",
    status_code=204,
)
@limiter.limit("10/minute")
async def reject_policy_generation(
    request: Request,
    workspace_id: str,
    generation_id: str,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> None:
    """Mark a generation as rejected (server-side record)."""
    from src.services.policy_composer_service import get_workspace_for_composer

    workspace = await get_workspace_for_composer(db, workspace_id=workspace_id, client_id=client_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Policy workspace not found")

    generation = next((g for g in workspace.generations if g.id == generation_id), None)
    if generation is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    if generation.accepted_revision_id is not None:
        raise HTTPException(status_code=400, detail="Cannot reject an accepted generation")

    generation.rejected_at = datetime.now(UTC)
    await db.commit()


@router.get(
    "/policy-workspaces/{workspace_id}/history",
    response_model=PolicyHistoryResponse,
)
async def get_policy_workspace_history(
    workspace_id: str,
    section_id: str | None = Query(None),
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> PolicyHistoryResponse:
    try:
        revisions = await get_section_history(
            db,
            workspace_id=workspace_id,
            client_id=client_id,
            section_id=section_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return PolicyHistoryResponse(
        revisions=[
            PolicyRevisionResponse(
                id=rev.id,
                section_id=rev.section_id,
                generation_id=rev.generation_id,
                change_source=rev.change_source,
                content_markdown=rev.content_markdown,
                created_at=rev.created_at,
            )
            for rev in revisions
        ]
    )


@router.get(
    "/policy-workspaces/{workspace_id}/export",
    response_class=PlainTextResponse,
)
async def export_policy_workspace(
    workspace_id: str,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> PlainTextResponse:
    try:
        markdown = await export_workspace_markdown(
            db, workspace_id=workspace_id, client_id=client_id
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return PlainTextResponse(
        content=markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{workspace_id}.md"'},
    )


# ---------------------------------------------------------------------------
# Workspace Chat
# ---------------------------------------------------------------------------


def _build_workspace_context_for_chat(
    workspace: PolicyWorkspace,
) -> tuple[list[dict], list[dict]]:
    """Build precedent summaries and section data for prompt context."""
    precedent_summaries = []
    for prec in sorted(workspace.precedents, key=lambda p: p.position):
        bill = prec.bill
        precedent_summaries.append(
            {
                "identifier": bill.identifier,
                "title": bill.title,
                "jurisdiction_id": bill.jurisdiction_id,
                "status": bill.status,
            }
        )

    sections = []
    for sec in sorted(workspace.sections, key=lambda s: s.position):
        sections.append(
            {
                "heading": sec.heading,
                "status": sec.status,
                "content_markdown": sec.content_markdown or "",
            }
        )

    return precedent_summaries, sections


@router.post(
    "/policy-workspaces/{workspace_id}/chat",
    response_model=ChatResponse,
)
@limiter.limit("30/minute")
async def workspace_chat(
    request: Request,
    workspace_id: str,
    body: ChatRequest,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> ChatResponse:
    """Chat with a workspace-aware research assistant."""
    from src.llm.prompts.workspace_assistant_v1 import (
        SYSTEM_PROMPT_TEMPLATE,
        format_workspace_context,
    )
    from src.services.chat_service import (
        HISTORY_CHAR_BUDGET,
        run_agentic_chat,
        trim_history,
    )

    message = body.message
    conversation_id = body.conversation_id

    # 1. Load workspace with full context
    workspace = await _get_workspace_or_error(
        db, workspace_id=workspace_id, client_id=client_id, load_detail=True
    )

    # 2. Build workspace context for system prompt
    precedent_summaries, sections = _build_workspace_context_for_chat(workspace)
    workspace_context = format_workspace_context(
        title=workspace.title,
        target_jurisdiction=workspace.target_jurisdiction_id or "",
        drafting_template=workspace.drafting_template or "",
        goal_prompt=workspace.goal_prompt,
        precedent_summaries=precedent_summaries,
        sections=sections,
    )
    system_prompt = SYSTEM_PROMPT_TEMPLATE.replace("{workspace_context}", workspace_context)

    # 3. Load or create conversation scoped to this workspace
    if conversation_id:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.messages))
        )
        conversation = result.scalar_one_or_none()
        if (
            not conversation
            or conversation.client_id != client_id
            or conversation.workspace_id != workspace_id
        ):
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(
            id=uuid.uuid4().hex,
            client_id=client_id,
            workspace_id=workspace_id,
            title=f"Research: {workspace.title[:60]}",
        )
        db.add(conversation)
        await db.flush()

    # 4. Store user message
    user_msg = ConversationMessage(
        conversation_id=conversation.id,
        role="user",
        content=message,
    )
    db.add(user_msg)

    # 5. Build message history
    messages: list[dict] = []
    for msg in conversation.messages:
        if msg.role in ("user", "assistant"):
            messages.append({"role": msg.role, "content": msg.content})

    conv_id = conversation.id
    await db.commit()

    # 6. Run agentic loop (no DB connection held)
    client = get_anthropic_client()
    trimmed = trim_history(messages, HISTORY_CHAR_BUDGET)

    final_text, all_tool_calls = await run_agentic_chat(
        system_prompt=system_prompt,
        messages=trimmed,
        client=client,
    )

    # 7. Persist assistant message
    tool_calls_meta = all_tool_calls if all_tool_calls else None
    async with async_session_factory() as persist_db:
        assistant_msg = ConversationMessage(
            conversation_id=conv_id,
            role="assistant",
            content=final_text,
            tool_calls=tool_calls_meta,
        )
        persist_db.add(assistant_msg)

        conv = await persist_db.get(Conversation, conv_id)
        if conv:
            conv.updated_at = datetime.now(UTC)
        await persist_db.commit()
        await persist_db.refresh(assistant_msg)

    # 8. Build response
    tool_call_infos = [ToolCallInfo(**tc) for tc in all_tool_calls] if all_tool_calls else None
    return ChatResponse(
        conversation_id=conv_id,
        message=ChatMessageResponse(
            role="assistant",
            content=final_text,
            tool_calls=tool_call_infos,
            created_at=assistant_msg.created_at,
        ),
    )


@router.post("/policy-workspaces/{workspace_id}/chat/stream")
@limiter.limit("30/minute")
async def workspace_chat_stream(
    request: Request,
    workspace_id: str,
    body: ChatRequest,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Stream a workspace-aware chat response via Server-Sent Events."""
    from src.llm.prompts.workspace_assistant_v1 import (
        SYSTEM_PROMPT_TEMPLATE,
        format_workspace_context,
    )
    from src.services.chat_service import (
        HISTORY_CHAR_BUDGET,
        stream_agentic_chat,
        trim_history,
    )

    message = body.message
    conversation_id = body.conversation_id

    # 1. Load workspace context
    workspace = await _get_workspace_or_error(
        db, workspace_id=workspace_id, client_id=client_id, load_detail=True
    )
    precedent_summaries, sections = _build_workspace_context_for_chat(workspace)
    workspace_context = format_workspace_context(
        title=workspace.title,
        target_jurisdiction=workspace.target_jurisdiction_id or "",
        drafting_template=workspace.drafting_template or "",
        goal_prompt=workspace.goal_prompt,
        precedent_summaries=precedent_summaries,
        sections=sections,
    )
    system_prompt = SYSTEM_PROMPT_TEMPLATE.replace(
        "{workspace_context}", workspace_context
    )

    # 2. Load or create conversation
    if conversation_id:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.messages))
        )
        conversation = result.scalar_one_or_none()
        if (
            not conversation
            or conversation.client_id != client_id
            or conversation.workspace_id != workspace_id
        ):
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(
            id=uuid.uuid4().hex,
            client_id=client_id,
            workspace_id=workspace_id,
            title=f"Research: {workspace.title[:60]}",
        )
        db.add(conversation)
        await db.flush()

    user_msg = ConversationMessage(
        conversation_id=conversation.id,
        role="user",
        content=message,
    )
    db.add(user_msg)

    messages: list[dict] = []
    for msg in conversation.messages:
        if msg.role in ("user", "assistant"):
            messages.append({"role": msg.role, "content": msg.content})

    conv_id = conversation.id
    await db.commit()

    # 3. Stream agentic loop (no DB held)
    client = get_anthropic_client()
    trimmed = trim_history(messages, HISTORY_CHAR_BUDGET)

    async def event_generator():
        final_text = ""
        all_tool_calls: list[dict] = []

        async for event_str in stream_agentic_chat(
            system_prompt=system_prompt,
            messages=trimmed,
            client=client,
        ):
            if event_str.startswith("event: done\n"):
                data_line = event_str.split("data: ", 1)[1].split("\n")[0]
                done_data = json.loads(data_line)
                final_text = done_data.get("text", "")
                all_tool_calls = done_data.get("tool_calls", [])
                done_data["conversation_id"] = conv_id
                event_str = (
                    f"event: done\ndata: {json.dumps(done_data)}\n\n"
                )
            yield event_str

        # 4. Persist assistant message
        if final_text:
            tool_calls_meta = all_tool_calls if all_tool_calls else None
            async with async_session_factory() as persist_db:
                assistant_msg = ConversationMessage(
                    conversation_id=conv_id,
                    role="assistant",
                    content=final_text,
                    tool_calls=tool_calls_meta,
                )
                persist_db.add(assistant_msg)
                conv = await persist_db.get(Conversation, conv_id)
                if conv:
                    conv.updated_at = datetime.now(UTC)
                await persist_db.commit()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post(
    "/policy-workspaces/{workspace_id}/sections/{section_id}/compose/stream",
)
@limiter.limit("5/minute")
async def compose_policy_section_stream(
    request: Request,
    workspace_id: str,
    section_id: str,
    body: PolicyComposeRequest,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Stream a compose/analyze action via Server-Sent Events.

    Streams token events during LLM generation, then emits a done event
    with the full structured PolicyGenerationResponse.
    """
    from src.services.policy_composer_service import (
        stream_compose_section,
    )

    try:
        event_gen = await stream_compose_section(
            workspace_id=workspace_id,
            section_id=section_id,
            client_id=client_id,
            action_type=body.action_type,
            instruction_text=body.instruction_text,
            selected_text=body.selected_text,
            client=get_anthropic_client(),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StreamingResponse(event_gen, media_type="text/event-stream")


@router.get(
    "/policy-workspaces/{workspace_id}/conversations",
    response_model=WorkspaceConversationListResponse,
)
async def list_workspace_conversations(
    workspace_id: str,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> WorkspaceConversationListResponse:
    """List conversations for a workspace."""
    await _get_workspace_or_error(db, workspace_id=workspace_id, client_id=client_id)

    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.client_id == client_id,
        )
        .order_by(Conversation.updated_at.desc())
    )
    conversations = result.scalars().all()

    return WorkspaceConversationListResponse(
        conversations=[
            WorkspaceConversationSummary(
                id=c.id,
                title=c.title,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in conversations
        ]
    )


# ---------------------------------------------------------------------------
# Precedent Insights
# ---------------------------------------------------------------------------


@router.get(
    "/policy-workspaces/{workspace_id}/precedent-insights",
    response_model=PrecedentInsightsResponse,
)
async def get_precedent_insights(
    workspace_id: str,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> PrecedentInsightsResponse:
    """Get ML prediction + AI summary for each precedent bill."""
    from src.prediction.service import is_model_loaded, predict_bill

    workspace = await _get_workspace_or_error(
        db, workspace_id=workspace_id, client_id=client_id, load_detail=True
    )

    precedents = sorted(workspace.precedents, key=lambda p: p.position)
    bill_ids = [prec.bill_id for prec in precedents]

    # Batch-load AI summaries in one query instead of N+1
    from src.models.ai_analysis import AiAnalysis

    summary_map: dict[str, str] = {}
    if bill_ids:
        summary_result = await db.execute(
            select(AiAnalysis)
            .where(
                AiAnalysis.bill_id.in_(bill_ids),
                AiAnalysis.analysis_type == "summary",
            )
            .order_by(AiAnalysis.created_at.desc())
        )
        for row in summary_result.scalars().all():
            if row.bill_id not in summary_map and row.result:
                text = row.result.get("plain_english_summary")
                if text:
                    summary_map[row.bill_id] = text

    # Build insights with optional predictions
    insights = []
    for prec in precedents:
        bill = prec.bill
        insight: dict = {
            "bill_id": bill.id,
            "identifier": bill.identifier,
            "title": bill.title,
            "jurisdiction_id": bill.jurisdiction_id,
            "status": bill.status,
            "prediction_probability": None,
            "prediction_factors": None,
            "ai_summary": summary_map.get(bill.id),
        }

        if is_model_loaded():
            try:
                pred = await predict_bill(db, bill.id)
                if pred:
                    insight["prediction_probability"] = pred.get("committee_passage_probability")
                    insight["prediction_factors"] = pred.get("key_factors", [])[:3]
            except Exception:
                logger.warning("Prediction failed for bill %s", bill.id, exc_info=True)

        insights.append(insight)

    return PrecedentInsightsResponse(insights=insights)
