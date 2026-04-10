"""Research assistant chat endpoints — conversational AI with tool use."""

import asyncio
import json
import logging
import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import get_agentic_client, get_llm_client, get_session, limiter
from src.config import settings
from src.database import async_session_factory
from src.llm.codex_local_bridge import CodexLocalBridge
from src.llm.harness import LLMHarness
from src.llm.prompts import research_assistant_v1
from src.models.bill import Bill
from src.models.bill_text import texts_without_markup
from src.models.conversation import Conversation, ConversationMessage
from src.models.jurisdiction import Jurisdiction
from src.models.sponsorship import Sponsorship
from src.schemas.chat import (
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ConversationListResponse,
    ConversationResponse,
    ToolCallInfo,
)
from src.schemas.common import MetaResponse
from src.search.engine import hybrid_search
from src.search.govinfo import get_govinfo_package, search_govinfo
from src.search.vector import find_similar_bill_ids
from src.services.bill_service import extract_bill_text

logger = logging.getLogger(__name__)

router = APIRouter()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


async def _run_codex_chat_once(message: str) -> tuple[str, list[dict]]:
    def _run() -> tuple[list[str], str]:
        with CodexLocalBridge(_repo_root()) as bridge:
            return bridge.run_prompt(message, cwd=_repo_root())

    deltas, final_text = await asyncio.to_thread(_run)
    return final_text, []


async def _stream_codex_chat_once(message: str):
    def _run() -> tuple[list[str], str]:
        with CodexLocalBridge(_repo_root()) as bridge:
            return bridge.run_prompt(message, cwd=_repo_root())

    deltas, final_text = await asyncio.to_thread(_run)
    for delta in deltas:
        yield f"event: token\ndata: {json.dumps({'text': delta})}\n\n"
    yield f"event: done\ndata: {json.dumps({'text': final_text, 'tool_calls': []})}\n\n"


def get_client_id(x_client_id: str | None = Header(None)) -> str:
    """Get client ID from header or return 'anonymous'."""
    return x_client_id or "anonymous"


# ---------------------------------------------------------------------------
# Tool handlers — each tool gets its own async function
# ---------------------------------------------------------------------------


async def _tool_search_bills(
    arguments: dict[str, Any], db: AsyncSession, harness: LLMHarness
) -> str:
    query = arguments.get("query", "")
    jurisdiction = arguments.get("jurisdiction")
    mode = arguments.get("mode", "hybrid")

    results = await hybrid_search(
        session=db, query=query, mode=mode, jurisdiction=jurisdiction, top_k=20
    )

    if not results:
        return json.dumps({"bills": [], "total": 0})

    bill_ids = [r[0] for r in results]
    stmt = select(Bill).where(Bill.id.in_(bill_ids))
    result = await db.execute(stmt)
    bills_by_id = {b.id: b for b in result.scalars().all()}

    bills_out = []
    for bill_id, score in results:
        bill = bills_by_id.get(bill_id)
        if not bill:
            continue
        bills_out.append(
            {
                "bill_id": bill.id,
                "identifier": bill.identifier,
                "title": bill.title,
                "jurisdiction_id": bill.jurisdiction_id,
                "status": bill.status,
                "status_date": (str(bill.status_date) if bill.status_date else None),
                "introduced_date": (str(bill.introduced_date) if bill.introduced_date else None),
                "score": round(score, 4),
            }
        )

    return json.dumps({"bills": bills_out, "total": len(bills_out)})


async def _tool_get_bill_detail(
    arguments: dict[str, Any], db: AsyncSession, harness: LLMHarness
) -> str:
    bill_id = arguments.get("bill_id", "")
    stmt = (
        select(Bill)
        .where(Bill.id == bill_id)
        .options(
            texts_without_markup(Bill.texts),
            selectinload(Bill.actions),
            selectinload(Bill.sponsorships).selectinload(Sponsorship.person),
            selectinload(Bill.analyses),
        )
    )
    result = await db.execute(stmt)
    bill = result.scalar_one_or_none()
    if not bill:
        return json.dumps({"error": f"Bill '{bill_id}' not found."})

    ai_summary = None
    for a in bill.analyses:
        if a.analysis_type == "summary":
            ai_summary = a.result
            break

    bill_text = None
    for t in bill.texts:
        if t.content_text:
            bill_text = t.content_text[:20000]
            break

    actions = sorted(
        [
            {
                "date": str(a.action_date),
                "description": a.description,
                "classification": a.classification,
                "chamber": a.chamber,
            }
            for a in bill.actions
        ],
        key=lambda a: a["date"],
    )

    sponsors = [
        {
            "name": s.person.name,
            "party": s.person.party,
            "classification": s.classification,
        }
        for s in bill.sponsorships
    ]

    detail = {
        "bill_id": bill.id,
        "identifier": bill.identifier,
        "title": bill.title,
        "jurisdiction_id": bill.jurisdiction_id,
        "status": bill.status,
        "status_date": str(bill.status_date) if bill.status_date else None,
        "introduced_date": str(bill.introduced_date) if bill.introduced_date else None,
        "classification": bill.classification,
        "subject": bill.subject,
        "ai_summary": ai_summary,
        "bill_text_excerpt": bill_text,
        "actions": actions,
        "sponsors": sponsors,
    }
    return json.dumps(detail)


async def _tool_list_jurisdictions(
    arguments: dict[str, Any], db: AsyncSession, harness: LLMHarness
) -> str:
    stmt = select(Jurisdiction).order_by(Jurisdiction.name)
    result = await db.execute(stmt)
    jurisdictions = result.scalars().all()

    data = [
        {
            "id": j.id,
            "name": j.name,
            "classification": j.classification,
            "abbreviation": j.abbreviation,
        }
        for j in jurisdictions
    ]
    return json.dumps({"jurisdictions": data, "total": len(data)})


async def _tool_find_similar_bills(
    arguments: dict[str, Any], db: AsyncSession, harness: LLMHarness
) -> str:
    bill_id = arguments.get("bill_id", "")
    top_k = arguments.get("top_k", 5)

    matches = await find_similar_bill_ids(db, bill_id, top_k=top_k)
    if not matches:
        return json.dumps({"similar_bills": [], "source_bill_id": bill_id})

    matched_ids = [m.bill_id for m in matches]
    score_map = {m.bill_id: m.score for m in matches}

    result = await db.execute(select(Bill).where(Bill.id.in_(matched_ids)))
    bills_by_id = {b.id: b for b in result.scalars().all()}

    similar = []
    for m in matches:
        bill = bills_by_id.get(m.bill_id)
        if not bill:
            continue
        similar.append(
            {
                "bill_id": bill.id,
                "identifier": bill.identifier,
                "title": bill.title,
                "jurisdiction_id": bill.jurisdiction_id,
                "status": bill.status,
                "similarity_score": round(score_map[m.bill_id], 4),
            }
        )

    return json.dumps({"similar_bills": similar, "source_bill_id": bill_id})


async def _tool_analyze_version_diff(
    arguments: dict[str, Any], db: AsyncSession, harness: LLMHarness
) -> str:
    bill_id = arguments.get("bill_id", "")
    stmt = select(Bill).where(Bill.id == bill_id).options(texts_without_markup(Bill.texts))
    result = await db.execute(stmt)
    bill = result.scalar_one_or_none()
    if not bill:
        return json.dumps({"error": f"Bill '{bill_id}' not found."})

    sorted_texts = sorted(
        [t for t in bill.texts if t.content_text],
        key=lambda t: t.version_date or t.created_at,
    )
    if len(sorted_texts) < 2:
        return json.dumps({"error": "Bill must have at least 2 text versions with content."})

    # Resolve version A (default: oldest)
    version_a_id = arguments.get("version_a_id")
    if version_a_id:
        version_a = next((t for t in sorted_texts if t.id == version_a_id), None)
        if not version_a:
            return json.dumps({"error": "Version A text not found."})
    else:
        version_a = sorted_texts[0]

    # Resolve version B (default: latest)
    version_b_id = arguments.get("version_b_id")
    if version_b_id:
        version_b = next((t for t in sorted_texts if t.id == version_b_id), None)
        if not version_b:
            return json.dumps({"error": "Version B text not found."})
    else:
        version_b = sorted_texts[-1]

    if version_a.id == version_b.id:
        return json.dumps({"error": "Version A and Version B must be different."})

    output = await harness.version_diff(
        bill_id=bill.id,
        identifier=bill.identifier,
        jurisdiction=bill.jurisdiction_id,
        version_a_name=version_a.version_name or "Earlier Version",
        version_a_text=version_a.content_text,
        version_b_name=version_b.version_name or "Later Version",
        version_b_text=version_b.content_text,
    )
    await db.commit()
    return json.dumps(output.model_dump())


async def _tool_analyze_constitutional(
    arguments: dict[str, Any], db: AsyncSession, harness: LLMHarness
) -> str:
    bill_id = arguments.get("bill_id", "")
    stmt = select(Bill).where(Bill.id == bill_id).options(texts_without_markup(Bill.texts))
    result = await db.execute(stmt)
    bill = result.scalar_one_or_none()
    if not bill:
        return json.dumps({"error": f"Bill '{bill_id}' not found."})

    bill_text = extract_bill_text(bill)

    output = await harness.constitutional_analysis(
        bill_id=bill.id,
        bill_text=bill_text,
        identifier=bill.identifier,
        jurisdiction=bill.jurisdiction_id,
        title=bill.title,
    )
    await db.commit()
    return json.dumps(output.model_dump())


async def _tool_analyze_patterns(
    arguments: dict[str, Any], db: AsyncSession, harness: LLMHarness
) -> str:
    bill_id = arguments.get("bill_id", "")
    top_k = arguments.get("top_k", 5)

    stmt = select(Bill).where(Bill.id == bill_id).options(texts_without_markup(Bill.texts))
    result = await db.execute(stmt)
    bill = result.scalar_one_or_none()
    if not bill:
        return json.dumps({"error": f"Bill '{bill_id}' not found."})

    source_text = extract_bill_text(bill)

    # Find similar bills from other jurisdictions
    matches = await find_similar_bill_ids(
        db,
        bill_id,
        exclude_jurisdiction=bill.jurisdiction_id,
        top_k=top_k,
    )
    if not matches:
        return json.dumps({"error": "No similar bills found in other jurisdictions."})

    matched_ids = [m.bill_id for m in matches]
    bills_result = await db.execute(
        select(Bill).where(Bill.id.in_(matched_ids)).options(texts_without_markup(Bill.texts))
    )
    similar_bills = bills_result.scalars().all()

    similar_parts: list[str] = []
    for sb in similar_bills:
        sb_text = extract_bill_text(sb)
        similar_parts.append(
            f"Bill: {sb.identifier}\n"
            f"Jurisdiction: {sb.jurisdiction_id}\n"
            f"Title: {sb.title}\n"
            f"Text:\n{sb_text[:10000]}\n"
        )

    output = await harness.pattern_detect(
        source_bill_id=bill.id,
        source_text=source_text,
        source_identifier=bill.identifier,
        source_jurisdiction=bill.jurisdiction_id,
        source_title=bill.title,
        similar_bills_text="\n---\n".join(similar_parts),
    )
    await db.commit()
    return json.dumps(output.model_dump())


async def _tool_predict_bill_passage(
    arguments: dict[str, Any], db: AsyncSession, harness: LLMHarness
) -> str:
    from src.prediction.service import is_model_loaded, predict_bill

    if not is_model_loaded():
        return json.dumps({"error": "Prediction model not currently loaded."})

    bill_id = arguments.get("bill_id", "")
    result = await predict_bill(db, bill_id)
    if result is None:
        return json.dumps({"error": f"Bill '{bill_id}' not found."})
    return json.dumps(result)


async def _tool_search_govinfo(
    arguments: dict[str, Any], db: AsyncSession, harness: LLMHarness
) -> str:
    query = arguments.get("query", "")
    collection = arguments.get("collection")
    congress = arguments.get("congress")
    page_size = arguments.get("page_size", 10)

    result = await search_govinfo(
        query=query,
        collection=collection,
        congress=congress,
        page_size=page_size,
    )
    return json.dumps(result)


async def _tool_get_govinfo_document(
    arguments: dict[str, Any], db: AsyncSession, harness: LLMHarness
) -> str:
    package_id = arguments.get("package_id", "")
    result = await get_govinfo_package(package_id)
    return json.dumps(result)


# Registry mapping tool names to handler functions
_ToolHandler = Callable[[dict[str, Any], AsyncSession, LLMHarness], Coroutine[Any, Any, str]]
_TOOL_HANDLERS: dict[str, _ToolHandler] = {
    "search_bills": _tool_search_bills,
    "get_bill_detail": _tool_get_bill_detail,
    "list_jurisdictions": _tool_list_jurisdictions,
    "find_similar_bills": _tool_find_similar_bills,
    "analyze_version_diff": _tool_analyze_version_diff,
    "analyze_constitutional": _tool_analyze_constitutional,
    "analyze_patterns": _tool_analyze_patterns,
    "predict_bill_passage": _tool_predict_bill_passage,
    "search_govinfo": _tool_search_govinfo,
    "get_govinfo_document": _tool_get_govinfo_document,
}

_HARNESS_REQUIRED_TOOLS = {
    "analyze_version_diff",
    "analyze_constitutional",
    "analyze_patterns",
    "predict_bill_passage",
}


async def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    db: AsyncSession,
    harness: LLMHarness | None = None,
) -> str:
    """Dispatch tool calls to the appropriate handler."""
    handler = _TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    if harness is None and tool_name in _HARNESS_REQUIRED_TOOLS:
        harness = LLMHarness(db_session=db, client=get_llm_client())
    return await handler(arguments, db, harness)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_title(message: str) -> str:
    """Generate a short conversation title from the first user message."""
    text = message.strip()
    if not text:
        return "Untitled conversation"
    for sep in (".", "?", "!"):
        idx = text.find(sep)
        if 0 < idx < 80:
            return text[: idx + 1]
    return text[:80] + ("..." if len(text) > 80 else "")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("30/minute")
async def chat(
    request: Request,
    req: ChatRequest,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> ChatResponse:
    """Send a message to the research assistant and get a response.

    Supports multi-turn conversation with automatic tool use for bill search,
    detail retrieval, jurisdiction listing, and similarity analysis.
    """
    # 1. Create or retrieve conversation
    if req.conversation_id:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.id == req.conversation_id)
            .options(selectinload(Conversation.messages))
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if conversation.client_id != client_id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to access this conversation",
            )
    else:
        conversation = Conversation(
            id=uuid.uuid4().hex,
            client_id=client_id,
            title=_generate_title(req.message),
        )
        db.add(conversation)
        await db.flush()

    # 2. Store user message
    user_msg = ConversationMessage(
        conversation_id=conversation.id,
        role="user",
        content=req.message,
    )
    db.add(user_msg)

    # 3. Build message history from conversation (with budget trimming)
    messages: list[dict] = []
    if req.conversation_id:
        for msg in conversation.messages:
            if msg.role == "user":
                messages.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                messages.append({"role": "assistant", "content": msg.content})

    # Commit user message and release DB connection before agentic loop
    conversation_id = conversation.id
    await db.commit()

    # 4. Run agentic loop — no DB connection held during LLM calls
    from src.services.chat_service import HISTORY_CHAR_BUDGET, run_agentic_chat, trim_history

    trimmed = trim_history(messages, HISTORY_CHAR_BUDGET)

    if settings.agentic_provider.strip().lower() == "codex-local":
        prompt_parts = [research_assistant_v1.SYSTEM_PROMPT]
        for msg in trimmed:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt_parts.append(f"<{role}>\n{content}\n</{role}>")
        final_text, all_tool_calls = await _run_codex_chat_once("\n\n".join(prompt_parts))
    else:
        try:
            client = get_agentic_client()
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        final_text, all_tool_calls = await run_agentic_chat(
            system_prompt=research_assistant_v1.SYSTEM_PROMPT,
            messages=trimmed,
            client=client,
        )

    # 5. Store assistant message — brief DB connection for persist
    tool_calls_meta = all_tool_calls if all_tool_calls else None
    async with async_session_factory() as persist_db:
        assistant_msg = ConversationMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=final_text,
            tool_calls=tool_calls_meta,
        )
        persist_db.add(assistant_msg)

        # Update conversation timestamp
        conv = await persist_db.get(Conversation, conversation_id)
        if conv:
            conv.updated_at = datetime.now(UTC)
        await persist_db.commit()
        await persist_db.refresh(assistant_msg)

    # 7. Build response
    tool_call_infos = [ToolCallInfo(**tc) for tc in all_tool_calls] if all_tool_calls else None

    return ChatResponse(
        conversation_id=conversation_id,
        message=ChatMessageResponse(
            role="assistant",
            content=final_text,
            tool_calls=tool_call_infos,
            created_at=assistant_msg.created_at,
        ),
    )


@router.post("/chat/stream")
@limiter.limit("30/minute")
async def chat_stream(
    request: Request,
    req: ChatRequest,
    client_id: str = Depends(get_client_id),
) -> StreamingResponse:
    """Stream a chat response via Server-Sent Events.

    Same as POST /chat but returns SSE events: tool_status during tool use,
    token for streaming text, done with final message and metadata.
    """
    # 1. Load phase — own session, closed before streaming begins
    async with async_session_factory() as db:
        if req.conversation_id:
            result = await db.execute(
                select(Conversation)
                .where(Conversation.id == req.conversation_id)
                .options(selectinload(Conversation.messages))
            )
            conversation = result.scalar_one_or_none()
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
            if conversation.client_id != client_id:
                raise HTTPException(status_code=404, detail="Conversation not found")
        else:
            conversation = Conversation(
                id=uuid.uuid4().hex,
                client_id=client_id,
                title=_generate_title(req.message),
            )
            db.add(conversation)
            await db.flush()

        user_msg = ConversationMessage(
            conversation_id=conversation.id,
            role="user",
            content=req.message,
        )
        db.add(user_msg)

        messages: list[dict] = []
        if req.conversation_id:
            # Only load history for existing conversations
            for msg in conversation.messages:
                if msg.role == "user":
                    messages.append({"role": "user", "content": msg.content})
                elif msg.role == "assistant":
                    messages.append({"role": "assistant", "content": msg.content})

        # Append the new user message to the history
        messages.append({"role": "user", "content": req.message})

        conversation_id = conversation.id
        await db.commit()

    # 2. Call phase — stream agentic loop (no DB held)
    from src.llm.claude_sdk_adapter import ClaudeSDKClient
    from src.services.chat_service import (
        HISTORY_CHAR_BUDGET,
        stream_agentic_chat,
        stream_sdk_agentic_chat,
        trim_history,
    )

    trimmed = trim_history(messages, HISTORY_CHAR_BUDGET)
    use_codex = settings.agentic_provider.strip().lower() == "codex-local"
    use_sdk = False
    client = None
    if not use_codex:
        try:
            client = get_agentic_client()
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        use_sdk = isinstance(client, ClaudeSDKClient)

    async def event_generator():
        final_text = ""
        all_tool_calls: list[dict] = []

        if use_codex:
            prompt_parts = [research_assistant_v1.SYSTEM_PROMPT]
            for msg in trimmed:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                prompt_parts.append(f"<{role}>\n{content}\n</{role}>")
            event_stream = _stream_codex_chat_once("\n\n".join(prompt_parts))
        elif use_sdk:
            # Agent SDK path: MCP server provides tools to Claude's agentic loop
            event_stream = stream_sdk_agentic_chat(
                system_prompt=research_assistant_v1.SYSTEM_PROMPT,
                messages=trimmed,
            )
        else:
            # Standard Anthropic/OpenAI compatibility path: our app-managed research loop
            event_stream = stream_agentic_chat(
                system_prompt=research_assistant_v1.SYSTEM_PROMPT,
                messages=trimmed,
                client=client,
            )

        async for event_str in event_stream:
            # Parse the event to capture done data for persistence
            if event_str.startswith("event: done\n"):
                data_line = event_str.split("data: ", 1)[1].split("\n")[0]
                done_data = json.loads(data_line)
                final_text = done_data.get("text", "")
                all_tool_calls = done_data.get("tool_calls", [])
                done_data["conversation_id"] = conversation_id
                event_str = (
                    f"event: done\ndata: {json.dumps(done_data)}\n\n"
                )

            yield event_str

        # 3. Persist phase — store assistant message
        if final_text:
            tool_calls_meta = all_tool_calls if all_tool_calls else None
            async with async_session_factory() as persist_db:
                assistant_msg = ConversationMessage(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=final_text,
                    tool_calls=tool_calls_meta,
                )
                persist_db.add(assistant_msg)
                conv = await persist_db.get(Conversation, conversation_id)
                if conv:
                    conv.updated_at = datetime.now(UTC)
                await persist_db.commit()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    client_id: str = Depends(get_client_id),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
) -> ConversationListResponse:
    """List conversations owned by the current client."""
    stmt = select(Conversation).where(Conversation.client_id == client_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Conversation.updated_at.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    conversations = result.scalars().all()

    data = [
        ConversationResponse(
            id=c.id,
            title=c.title,
            created_at=c.created_at,
        )
        for c in conversations
    ]

    return ConversationListResponse(
        data=data,
        meta=MetaResponse(total_count=total, page=page, per_page=per_page),
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
)
async def get_conversation(
    conversation_id: str,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> ConversationResponse:
    """Get a conversation with its full message history."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.client_id != client_id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to access this conversation",
        )

    messages = [
        ChatMessageResponse(
            role=m.role,
            content=m.content,
            tool_calls=([ToolCallInfo(**tc) for tc in m.tool_calls] if m.tool_calls else None),
            created_at=m.created_at,
        )
        for m in conversation.messages
    ]

    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        messages=messages,
        created_at=conversation.created_at,
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> None:
    """Delete a conversation and all its messages."""
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.client_id != client_id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to access this conversation",
        )
    await db.delete(conversation)
    await db.commit()
