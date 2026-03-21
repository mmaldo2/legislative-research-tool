"""Service layer for policy workspace CRUD and precedent membership."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.bill import Bill
from src.models.jurisdiction import Jurisdiction
from src.models.policy_workspace import (
    PolicySection,
    PolicyWorkspace,
    PolicyWorkspacePrecedent,
)


async def _ensure_jurisdiction_exists(session: AsyncSession, jurisdiction_id: str) -> None:
    result = await session.execute(
        select(Jurisdiction.id).where(Jurisdiction.id == jurisdiction_id)
    )
    if result.scalar_one_or_none() is None:
        raise LookupError("Jurisdiction not found")


async def create_workspace(
    session: AsyncSession,
    *,
    client_id: str,
    title: str,
    target_jurisdiction_id: str,
    drafting_template: str,
    goal_prompt: str | None = None,
) -> PolicyWorkspace:
    await _ensure_jurisdiction_exists(session, target_jurisdiction_id)
    workspace = PolicyWorkspace(
        client_id=client_id,
        title=title,
        target_jurisdiction_id=target_jurisdiction_id,
        drafting_template=drafting_template,
        goal_prompt=goal_prompt,
    )
    session.add(workspace)
    await session.commit()
    await session.refresh(workspace)
    return workspace


async def list_workspaces(
    session: AsyncSession,
    *,
    client_id: str,
    page: int,
    per_page: int,
) -> tuple[list[tuple[PolicyWorkspace, int, int]], int]:
    base_stmt = select(PolicyWorkspace).where(PolicyWorkspace.client_id == client_id)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    precedent_count_subq = (
        select(
            PolicyWorkspacePrecedent.workspace_id,
            func.count(PolicyWorkspacePrecedent.id).label("precedent_count"),
        )
        .group_by(PolicyWorkspacePrecedent.workspace_id)
        .subquery()
    )
    section_count_subq = (
        select(
            PolicySection.workspace_id,
            func.count(PolicySection.id).label("section_count"),
        )
        .group_by(PolicySection.workspace_id)
        .subquery()
    )

    stmt = (
        select(
            PolicyWorkspace,
            func.coalesce(precedent_count_subq.c.precedent_count, 0).label("precedent_count"),
            func.coalesce(section_count_subq.c.section_count, 0).label("section_count"),
        )
        .outerjoin(precedent_count_subq, PolicyWorkspace.id == precedent_count_subq.c.workspace_id)
        .outerjoin(section_count_subq, PolicyWorkspace.id == section_count_subq.c.workspace_id)
        .where(PolicyWorkspace.client_id == client_id)
        .order_by(PolicyWorkspace.updated_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )

    result = await session.execute(stmt)
    rows = result.all()
    return rows, total


async def get_workspace_detail(
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


async def get_workspace_for_client(
    session: AsyncSession,
    *,
    workspace_id: str,
    client_id: str,
) -> PolicyWorkspace | None:
    result = await session.execute(
        select(PolicyWorkspace)
        .where(PolicyWorkspace.id == workspace_id)
        .options(selectinload(PolicyWorkspace.sections))
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        return None
    if workspace.client_id != client_id:
        raise PermissionError("Not authorized to access this policy workspace")
    return workspace


async def update_workspace(
    session: AsyncSession,
    *,
    workspace: PolicyWorkspace,
    title: str | None = None,
    target_jurisdiction_id: str | None = None,
    drafting_template: str | None = None,
    goal_prompt: str | None = None,
    update_goal_prompt: bool = False,
    status: str | None = None,
) -> PolicyWorkspace:
    if title is not None:
        workspace.title = title
    if target_jurisdiction_id is not None:
        if workspace.sections and target_jurisdiction_id != workspace.target_jurisdiction_id:
            raise ValueError("Cannot change target jurisdiction after outline generation")
        await _ensure_jurisdiction_exists(session, target_jurisdiction_id)
        workspace.target_jurisdiction_id = target_jurisdiction_id
    if drafting_template is not None:
        if workspace.sections and drafting_template != workspace.drafting_template:
            raise ValueError("Cannot change drafting template after outline generation")
        workspace.drafting_template = drafting_template
    if update_goal_prompt:
        workspace.goal_prompt = goal_prompt
    if status is not None:
        workspace.status = status
    workspace.updated_at = datetime.now(UTC)

    await session.commit()
    await session.refresh(workspace)
    return workspace


async def delete_workspace(session: AsyncSession, *, workspace: PolicyWorkspace) -> None:
    await session.delete(workspace)
    await session.commit()


async def add_precedent(
    session: AsyncSession,
    *,
    workspace: PolicyWorkspace,
    bill_id: str,
    position: int | None = None,
) -> PolicyWorkspacePrecedent:
    if workspace.sections:
        raise ValueError("Cannot modify precedents after outline generation")

    bill_result = await session.execute(select(Bill).where(Bill.id == bill_id))
    if bill_result.scalar_one_or_none() is None:
        raise LookupError("Bill not found")

    dup_result = await session.execute(
        select(PolicyWorkspacePrecedent).where(
            PolicyWorkspacePrecedent.workspace_id == workspace.id,
            PolicyWorkspacePrecedent.bill_id == bill_id,
        )
    )
    if dup_result.scalar_one_or_none() is not None:
        raise ValueError("Bill already in workspace precedents")

    precedent_position = position
    if precedent_position is None:
        max_pos_result = await session.execute(
            select(func.max(PolicyWorkspacePrecedent.position)).where(
                PolicyWorkspacePrecedent.workspace_id == workspace.id
            )
        )
        max_position = max_pos_result.scalar_one()
        precedent_position = (max_position if max_position is not None else -1) + 1

    precedent = PolicyWorkspacePrecedent(
        workspace_id=workspace.id,
        bill_id=bill_id,
        position=precedent_position,
    )
    session.add(precedent)
    workspace.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(precedent)
    detail_stmt = (
        select(PolicyWorkspacePrecedent)
        .where(PolicyWorkspacePrecedent.id == precedent.id)
        .options(selectinload(PolicyWorkspacePrecedent.bill))
    )
    detail_result = await session.execute(detail_stmt)
    return detail_result.scalar_one()


async def remove_precedent(
    session: AsyncSession,
    *,
    workspace: PolicyWorkspace,
    bill_id: str,
) -> None:
    if workspace.sections:
        raise ValueError("Cannot modify precedents after outline generation")

    result = await session.execute(
        select(PolicyWorkspacePrecedent).where(
            PolicyWorkspacePrecedent.workspace_id == workspace.id,
            PolicyWorkspacePrecedent.bill_id == bill_id,
        )
    )
    precedent = result.scalar_one_or_none()
    if precedent is None:
        raise LookupError("Precedent not found")

    await session.delete(precedent)
    workspace.updated_at = datetime.now(UTC)
    await session.commit()
