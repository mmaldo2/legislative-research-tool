"""Policy workspace composer CRUD endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_llm_harness, get_session, limiter
from src.llm.harness import LLMHarness
from src.models.policy_workspace import PolicyWorkspace
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
)
from src.services.policy_composer_service import (
    ComposeError,
    OutlineGenerationError,
    accept_generation,
    compose_section,
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
            db,
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
            db,
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
    except (ValueError, ComposeError) as exc:
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
