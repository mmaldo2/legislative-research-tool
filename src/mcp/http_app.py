"""Streamable HTTP MCP app for ChatGPT Apps / connector development.

This first slice intentionally exposes the highest-value read-oriented research
primitives over MCP so ChatGPT can search legislation and inspect bill detail
without depending on the in-app assistant/report routes.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from mcp.server.fastmcp import FastMCP
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.api.chat import execute_tool
from src.database import async_session_factory
from src.models.bill import Bill
from src.models.collection import Collection, CollectionItem
from src.models.collection_artifact import CollectionArtifact

logger = logging.getLogger(__name__)


async def _run_existing_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async with async_session_factory() as db:
        result = await execute_tool(name, arguments, db, harness=None)
    try:
        parsed = json.loads(result)
    except json.JSONDecodeError:
        parsed = {"raw": result}
    return parsed if isinstance(parsed, dict) else {"data": parsed}


def _resolve_client_id(client_id: str | None = None, connector_user_id: str | None = None) -> str:
    if client_id:
        return client_id
    if connector_user_id:
        digest = hashlib.sha256(connector_user_id.encode()).hexdigest()[:24]
        return f"chatgpt:{digest}"
    raise ValueError("Provide either client_id or connector_user_id")


async def _get_collection_or_error(client_id: str, collection_id: int, *, load_items: bool = False) -> Collection:
    async with async_session_factory() as db:
        stmt = select(Collection).where(Collection.id == collection_id)
        if load_items:
            stmt = stmt.options(selectinload(Collection.items).selectinload(CollectionItem.bill))
        result = await db.execute(stmt)
        collection = result.scalar_one_or_none()
        if not collection:
            raise ValueError("Collection not found")
        if collection.client_id != client_id:
            raise PermissionError("Not authorized to access this collection")
        return collection


def _serialize_collection_summary(collection: Collection, item_count: int) -> dict[str, Any]:
    return {
        "id": collection.id,
        "name": collection.name,
        "description": collection.description,
        "item_count": item_count,
        "created_at": collection.created_at.isoformat() if collection.created_at else None,
        "updated_at": collection.updated_at.isoformat() if collection.updated_at else None,
    }


def _serialize_collection_detail(collection: Collection) -> dict[str, Any]:
    return {
        "id": collection.id,
        "name": collection.name,
        "description": collection.description,
        "created_at": collection.created_at.isoformat() if collection.created_at else None,
        "updated_at": collection.updated_at.isoformat() if collection.updated_at else None,
        "items": [
            {
                "id": item.id,
                "bill_id": item.bill_id,
                "bill_identifier": item.bill.identifier if getattr(item, 'bill', None) else None,
                "bill_title": item.bill.title if getattr(item, 'bill', None) else None,
                "jurisdiction_id": item.bill.jurisdiction_id if getattr(item, 'bill', None) else None,
                "status": item.bill.status if getattr(item, 'bill', None) else None,
                "notes": item.notes,
                "added_at": item.added_at.isoformat() if item.added_at else None,
            }
            for item in collection.items
        ],
    }


def _serialize_artifact(artifact: CollectionArtifact) -> dict[str, Any]:
    return {
        "id": artifact.id,
        "collection_id": artifact.collection_id,
        "artifact_type": artifact.artifact_type,
        "title": artifact.title,
        "content_markdown": artifact.content_markdown,
        "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
        "updated_at": artifact.updated_at.isoformat() if artifact.updated_at else None,
    }


def build_chatgpt_mcp() -> FastMCP:
    mcp = FastMCP(
        name="Legislative Research",
        instructions=(
            "Use these tools to search bills, inspect bill detail, review jurisdictions, "
            "look up similar legislation, and retrieve GovInfo materials."
        ),
        streamable_http_path="/mcp",
        json_response=False,
        stateless_http=True,
    )

    @mcp.tool(
        name="search_bills",
        title="Search bills",
        description="Search legislation across jurisdictions and return ranked bill matches.",
        structured_output=True,
    )
    async def search_bills(
        query: str,
        jurisdiction: str | None = None,
        mode: str = "hybrid",
    ) -> dict[str, Any]:
        return await _run_existing_tool(
            "search_bills",
            {"query": query, "jurisdiction": jurisdiction, "mode": mode},
        )

    @mcp.tool(
        name="get_bill_detail",
        title="Get bill detail",
        description="Fetch bill metadata, actions, sponsors, summary, and text excerpt for a bill.",
        structured_output=True,
    )
    async def get_bill_detail(bill_id: str) -> dict[str, Any]:
        return await _run_existing_tool("get_bill_detail", {"bill_id": bill_id})

    @mcp.tool(
        name="list_jurisdictions",
        title="List jurisdictions",
        description="List supported jurisdictions in the legislative database.",
        structured_output=True,
    )
    async def list_jurisdictions() -> dict[str, Any]:
        return await _run_existing_tool("list_jurisdictions", {})

    @mcp.tool(
        name="find_similar_bills",
        title="Find similar bills",
        description="Find bills similar to a source bill using embeddings and fallback similarity data.",
        structured_output=True,
    )
    async def find_similar_bills(
        bill_id: str,
        top_k: int = 5,
    ) -> dict[str, Any]:
        return await _run_existing_tool(
            "find_similar_bills",
            {"bill_id": bill_id, "top_k": top_k},
        )

    @mcp.tool(
        name="search_govinfo",
        title="Search GovInfo",
        description="Search GovInfo collections for federal legislative and government documents.",
        structured_output=True,
    )
    async def search_govinfo(
        query: str,
        collection: str | None = None,
        congress: int | None = None,
        page_size: int = 10,
    ) -> dict[str, Any]:
        return await _run_existing_tool(
            "search_govinfo",
            {
                "query": query,
                "collection": collection,
                "congress": congress,
                "page_size": page_size,
            },
        )

    @mcp.tool(
        name="get_govinfo_document",
        title="Get GovInfo document",
        description="Fetch a specific GovInfo document/package by package_id.",
        structured_output=True,
    )
    async def get_govinfo_document(package_id: str) -> dict[str, Any]:
        return await _run_existing_tool("get_govinfo_document", {"package_id": package_id})

    @mcp.tool(
        name="list_investigations",
        title="List investigations",
        description="List saved investigations for a client/workspace id or connector user id.",
        structured_output=True,
    )
    async def list_investigations(
        client_id: str | None = None,
        connector_user_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_client_id = _resolve_client_id(client_id, connector_user_id)
        async with async_session_factory() as db:
            item_count_subq = (
                select(
                    CollectionItem.collection_id,
                    func.count(CollectionItem.id).label("item_count"),
                )
                .group_by(CollectionItem.collection_id)
                .subquery()
            )
            stmt = (
                select(Collection, func.coalesce(item_count_subq.c.item_count, 0).label("item_count"))
                .outerjoin(item_count_subq, Collection.id == item_count_subq.c.collection_id)
                .where(Collection.client_id == resolved_client_id)
                .order_by(Collection.updated_at.desc())
            )
            rows = (await db.execute(stmt)).all()
            return {
                "client_id": resolved_client_id,
                "investigations": [
                    _serialize_collection_summary(collection, item_count) for collection, item_count in rows
                ],
                "total": len(rows),
            }

    @mcp.tool(
        name="create_investigation",
        title="Create investigation",
        description="Create a new investigation for a client/workspace id or connector user id.",
        structured_output=True,
    )
    async def create_investigation(
        name: str,
        description: str | None = None,
        client_id: str | None = None,
        connector_user_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_client_id = _resolve_client_id(client_id, connector_user_id)
        async with async_session_factory() as db:
            collection = Collection(client_id=resolved_client_id, name=name, description=description)
            db.add(collection)
            await db.commit()
            await db.refresh(collection)
            return _serialize_collection_summary(collection, 0)

    @mcp.tool(
        name="get_investigation",
        title="Get investigation",
        description="Load a saved investigation with its current working set.",
        structured_output=True,
    )
    async def get_investigation(
        collection_id: int,
        client_id: str | None = None,
        connector_user_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_client_id = _resolve_client_id(client_id, connector_user_id)
        collection = await _get_collection_or_error(resolved_client_id, collection_id, load_items=True)
        return _serialize_collection_detail(collection)

    @mcp.tool(
        name="update_investigation",
        title="Update investigation",
        description="Update investigation name and/or description.",
        structured_output=True,
    )
    async def update_investigation(
        collection_id: int,
        name: str | None = None,
        description: str | None = None,
        client_id: str | None = None,
        connector_user_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_client_id = _resolve_client_id(client_id, connector_user_id)
        async with async_session_factory() as db:
            stmt = select(Collection).where(Collection.id == collection_id)
            collection = (await db.execute(stmt)).scalar_one_or_none()
            if not collection:
                raise ValueError("Collection not found")
            if collection.client_id != resolved_client_id:
                raise PermissionError("Not authorized to access this collection")
            if name is not None:
                collection.name = name
            if description is not None:
                collection.description = description
            collection.updated_at = datetime.now(UTC)
            await db.commit()
            await db.refresh(collection)
            item_count = (
                await db.execute(
                    select(func.count(CollectionItem.id)).where(CollectionItem.collection_id == collection_id)
                )
            ).scalar_one()
            return _serialize_collection_summary(collection, int(item_count))

    @mcp.tool(
        name="add_bill_to_investigation",
        title="Add bill to investigation",
        description="Add a bill to an investigation working set.",
        structured_output=True,
    )
    async def add_bill_to_investigation(
        collection_id: int,
        bill_id: str,
        notes: str | None = None,
        client_id: str | None = None,
        connector_user_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_client_id = _resolve_client_id(client_id, connector_user_id)
        async with async_session_factory() as db:
            collection = (await db.execute(select(Collection).where(Collection.id == collection_id))).scalar_one_or_none()
            if not collection:
                raise ValueError("Collection not found")
            if collection.client_id != resolved_client_id:
                raise PermissionError("Not authorized to access this collection")
            if not (await db.execute(select(Bill).where(Bill.id == bill_id))).scalar_one_or_none():
                raise ValueError("Bill not found")
            existing = (
                await db.execute(
                    select(CollectionItem).where(
                        CollectionItem.collection_id == collection_id,
                        CollectionItem.bill_id == bill_id,
                    )
                )
            ).scalar_one_or_none()
            if existing:
                raise ValueError("Bill already in collection")
            item = CollectionItem(collection_id=collection_id, bill_id=bill_id, notes=notes)
            db.add(item)
            collection.updated_at = datetime.now(UTC)
            await db.commit()
            await db.refresh(item)
            return {
                "id": item.id,
                "collection_id": collection_id,
                "bill_id": item.bill_id,
                "notes": item.notes,
                "added_at": item.added_at.isoformat() if item.added_at else None,
            }

    @mcp.tool(
        name="remove_bill_from_investigation",
        title="Remove bill from investigation",
        description="Remove a bill from an investigation working set.",
        structured_output=True,
    )
    async def remove_bill_from_investigation(
        collection_id: int,
        bill_id: str,
        client_id: str | None = None,
        connector_user_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_client_id = _resolve_client_id(client_id, connector_user_id)
        async with async_session_factory() as db:
            collection = (await db.execute(select(Collection).where(Collection.id == collection_id))).scalar_one_or_none()
            if not collection:
                raise ValueError("Collection not found")
            if collection.client_id != resolved_client_id:
                raise PermissionError("Not authorized to access this collection")
            item = (
                await db.execute(
                    select(CollectionItem).where(
                        CollectionItem.collection_id == collection_id,
                        CollectionItem.bill_id == bill_id,
                    )
                )
            ).scalar_one_or_none()
            if not item:
                raise ValueError("Item not found in collection")
            await db.delete(item)
            collection.updated_at = datetime.now(UTC)
            await db.commit()
            return {"removed": True, "collection_id": collection_id, "bill_id": bill_id}

    @mcp.tool(
        name="update_investigation_notes",
        title="Update investigation notes",
        description="Update notes for a saved bill inside an investigation.",
        structured_output=True,
    )
    async def update_investigation_notes(
        collection_id: int,
        bill_id: str,
        notes: str | None = None,
        client_id: str | None = None,
        connector_user_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_client_id = _resolve_client_id(client_id, connector_user_id)
        async with async_session_factory() as db:
            collection = (await db.execute(select(Collection).where(Collection.id == collection_id))).scalar_one_or_none()
            if not collection:
                raise ValueError("Collection not found")
            if collection.client_id != resolved_client_id:
                raise PermissionError("Not authorized to access this collection")
            item = (
                await db.execute(
                    select(CollectionItem).where(
                        CollectionItem.collection_id == collection_id,
                        CollectionItem.bill_id == bill_id,
                    )
                )
            ).scalar_one_or_none()
            if not item:
                raise ValueError("Item not found in collection")
            item.notes = notes
            collection.updated_at = datetime.now(UTC)
            await db.commit()
            await db.refresh(item)
            return {
                "id": item.id,
                "collection_id": collection_id,
                "bill_id": item.bill_id,
                "notes": item.notes,
                "added_at": item.added_at.isoformat() if item.added_at else None,
            }

    @mcp.tool(
        name="delete_investigation",
        title="Delete investigation",
        description="Delete an investigation and its working set.",
        structured_output=True,
    )
    async def delete_investigation(
        collection_id: int,
        client_id: str | None = None,
        connector_user_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_client_id = _resolve_client_id(client_id, connector_user_id)
        async with async_session_factory() as db:
            collection = (await db.execute(select(Collection).where(Collection.id == collection_id))).scalar_one_or_none()
            if not collection:
                raise ValueError("Collection not found")
            if collection.client_id != resolved_client_id:
                raise PermissionError("Not authorized to access this collection")
            await db.delete(collection)
            await db.commit()
            return {"deleted": True, "collection_id": collection_id}

    @mcp.tool(
        name="save_investigation_memo",
        title="Save investigation memo",
        description="Save a markdown memo artifact against an investigation.",
        structured_output=True,
    )
    async def save_investigation_memo(
        collection_id: int,
        title: str,
        content_markdown: str,
        artifact_type: str = "memo",
        client_id: str | None = None,
        connector_user_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_client_id = _resolve_client_id(client_id, connector_user_id)
        async with async_session_factory() as db:
            collection = (await db.execute(select(Collection).where(Collection.id == collection_id))).scalar_one_or_none()
            if not collection:
                raise ValueError("Collection not found")
            if collection.client_id != resolved_client_id:
                raise PermissionError("Not authorized to access this collection")
            artifact = CollectionArtifact(
                collection_id=collection_id,
                artifact_type=artifact_type,
                title=title,
                content_markdown=content_markdown,
            )
            db.add(artifact)
            collection.updated_at = datetime.now(UTC)
            await db.commit()
            await db.refresh(artifact)
            return _serialize_artifact(artifact)

    @mcp.tool(
        name="list_investigation_artifacts",
        title="List investigation artifacts",
        description="List saved memo/artifact records for an investigation.",
        structured_output=True,
    )
    async def list_investigation_artifacts(
        collection_id: int,
        client_id: str | None = None,
        connector_user_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_client_id = _resolve_client_id(client_id, connector_user_id)
        async with async_session_factory() as db:
            collection = (await db.execute(select(Collection).where(Collection.id == collection_id))).scalar_one_or_none()
            if not collection:
                raise ValueError("Collection not found")
            if collection.client_id != resolved_client_id:
                raise PermissionError("Not authorized to access this collection")
            artifacts = (
                await db.execute(
                    select(CollectionArtifact)
                    .where(CollectionArtifact.collection_id == collection_id)
                    .order_by(CollectionArtifact.created_at.desc())
                )
            ).scalars().all()
            return {
                "collection_id": collection_id,
                "artifacts": [_serialize_artifact(a) for a in artifacts],
                "total": len(artifacts),
            }

    @mcp.tool(
        name="get_investigation_artifact",
        title="Get investigation artifact",
        description="Load a saved memo/artifact record by id.",
        structured_output=True,
    )
    async def get_investigation_artifact(
        collection_id: int,
        artifact_id: int,
        client_id: str | None = None,
        connector_user_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_client_id = _resolve_client_id(client_id, connector_user_id)
        async with async_session_factory() as db:
            collection = (await db.execute(select(Collection).where(Collection.id == collection_id))).scalar_one_or_none()
            if not collection:
                raise ValueError("Collection not found")
            if collection.client_id != resolved_client_id:
                raise PermissionError("Not authorized to access this collection")
            artifact = (
                await db.execute(
                    select(CollectionArtifact).where(
                        CollectionArtifact.id == artifact_id,
                        CollectionArtifact.collection_id == collection_id,
                    )
                )
            ).scalar_one_or_none()
            if not artifact:
                raise ValueError("Artifact not found")
            return _serialize_artifact(artifact)

    @mcp.tool(
        name="save_investigation_snapshot",
        title="Save investigation snapshot",
        description="Create and save a markdown snapshot of the current investigation working set.",
        structured_output=True,
    )
    async def save_investigation_snapshot(
        collection_id: int,
        title: str | None = None,
        client_id: str | None = None,
        connector_user_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_client_id = _resolve_client_id(client_id, connector_user_id)
        collection = await _get_collection_or_error(resolved_client_id, collection_id, load_items=True)
        heading = title or f"{collection.name} snapshot"
        lines = [f"# {heading}", "", f"Investigation: {collection.name}"]
        if collection.description:
            lines.extend(["", f"Description: {collection.description}"])
        lines.extend(["", "## Working set"])
        if collection.items:
            for item in collection.items:
                lines.append(
                    f"- {item.bill.identifier if getattr(item, 'bill', None) else item.bill_id}: "
                    f"{item.bill.title if getattr(item, 'bill', None) else item.bill_id}"
                )
                if item.notes:
                    lines.append(f"  - Notes: {item.notes}")
        else:
            lines.append("- No bills saved yet.")
        snapshot_markdown = "\n".join(lines)
        async with async_session_factory() as db:
            artifact = CollectionArtifact(
                collection_id=collection_id,
                artifact_type="snapshot",
                title=heading,
                content_markdown=snapshot_markdown,
            )
            db.add(artifact)
            collection_db = (await db.execute(select(Collection).where(Collection.id == collection_id))).scalar_one()
            collection_db.updated_at = datetime.now(UTC)
            await db.commit()
            await db.refresh(artifact)
            return _serialize_artifact(artifact)

    @mcp.tool(
        name="save_investigation_research_brief",
        title="Save investigation research brief",
        description="Create and save a richer markdown research brief from investigation items and saved artifacts.",
        structured_output=True,
    )
    async def save_investigation_research_brief(
        collection_id: int,
        title: str | None = None,
        client_id: str | None = None,
        connector_user_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_client_id = _resolve_client_id(client_id, connector_user_id)
        collection = await _get_collection_or_error(resolved_client_id, collection_id, load_items=True)
        async with async_session_factory() as db:
            artifacts = (
                await db.execute(
                    select(CollectionArtifact)
                    .where(CollectionArtifact.collection_id == collection_id)
                    .order_by(CollectionArtifact.created_at.desc())
                )
            ).scalars().all()
            heading = title or f"{collection.name} research brief"
            lines = [f"# {heading}", "", f"Investigation: {collection.name}"]
            if collection.description:
                lines.extend(["", f"Description: {collection.description}"])
            lines.extend(["", "## Bills in scope"])
            if collection.items:
                for item in collection.items:
                    lines.append(
                        f"- {item.bill.identifier if getattr(item, 'bill', None) else item.bill_id}: "
                        f"{item.bill.title if getattr(item, 'bill', None) else item.bill_id}"
                    )
                    meta = []
                    if getattr(item, 'bill', None) and item.bill.jurisdiction_id:
                        meta.append(item.bill.jurisdiction_id)
                    if getattr(item, 'bill', None) and item.bill.status:
                        meta.append(item.bill.status)
                    if meta:
                        lines.append(f"  - Context: {' • '.join(meta)}")
                    if item.notes:
                        lines.append(f"  - Notes: {item.notes}")
            else:
                lines.append("- No bills saved yet.")
            lines.extend(["", "## Saved artifacts"])
            if artifacts:
                for artifact in artifacts[:10]:
                    lines.append(f"- [{artifact.artifact_type}] {artifact.title}")
            else:
                lines.append("- No saved artifacts yet.")
            lines.extend(["", "## Suggested next moves"])
            if not collection.items:
                lines.append("- Add 2-5 relevant bills to build the working set.")
            elif len(collection.items) == 1:
                lines.append("- Add a second bill so the investigation can compare approaches.")
            else:
                lines.append("- Compare the top bills and save a memo capturing the major differences.")
            brief_markdown = '\n'.join(lines)
            artifact = CollectionArtifact(
                collection_id=collection_id,
                artifact_type="research_brief",
                title=heading,
                content_markdown=brief_markdown,
            )
            db.add(artifact)
            collection_db = (await db.execute(select(Collection).where(Collection.id == collection_id))).scalar_one()
            collection_db.updated_at = datetime.now(UTC)
            await db.commit()
            await db.refresh(artifact)
            return _serialize_artifact(artifact)

    @mcp.resource(
        "legislative://connector/workflow",
        name="connector-workflow",
        title="Legislative connector workflow",
        description="Quick reference for the ChatGPT legislative connector workflow.",
        mime_type="text/markdown",
    )
    async def connector_workflow() -> str:
        return (
            "# Legislative Connector Workflow\n\n"
            "1. Resolve identity with a stable connector_user_id or explicit client_id.\n"
            "2. Search bills and inspect bill details.\n"
            "3. Create an investigation and add bills to the working set.\n"
            "4. Save memos, snapshots, or research briefs back into the investigation.\n"
            "5. Re-open investigations and artifacts in later chats.\n"
        )

    return mcp


chatgpt_mcp = build_chatgpt_mcp()
chatgpt_mcp_app = chatgpt_mcp.streamable_http_app()
