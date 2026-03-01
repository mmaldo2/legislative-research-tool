"""Research assistant chat endpoints — conversational AI with tool use."""

import json
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import get_session, limiter
from src.config import settings
from src.llm.prompts import research_assistant_v1
from src.llm.tools import RESEARCH_TOOLS
from src.models.bill import Bill
from src.models.bill_similarity import BillSimilarity
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

logger = logging.getLogger(__name__)

router = APIRouter()

# Maximum tool-use rounds before forcing a text response
_MAX_TOOL_ROUNDS = 10


async def execute_tool(tool_name: str, arguments: dict, db: AsyncSession) -> str:
    """Dispatch tool calls to the appropriate service.

    Returns a JSON string with the tool result for the model to consume.
    """
    if tool_name == "search_bills":
        query = arguments.get("query", "")
        jurisdiction = arguments.get("jurisdiction")
        mode = arguments.get("mode", "hybrid")

        results = await hybrid_search(
            session=db,
            query=query,
            mode=mode,
            jurisdiction=jurisdiction,
            top_k=20,
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
                    "status_date": str(bill.status_date) if bill.status_date else None,
                    "score": round(score, 4),
                }
            )

        return json.dumps({"bills": bills_out, "total": len(bills_out)})

    elif tool_name == "get_bill_detail":
        bill_id = arguments.get("bill_id", "")
        stmt = (
            select(Bill)
            .where(Bill.id == bill_id)
            .options(
                selectinload(Bill.texts),
                selectinload(Bill.actions),
                selectinload(Bill.sponsorships).selectinload(Sponsorship.person),
                selectinload(Bill.analyses),
            )
        )
        result = await db.execute(stmt)
        bill = result.scalar_one_or_none()
        if not bill:
            return json.dumps({"error": f"Bill '{bill_id}' not found."})

        # Find latest AI summary
        ai_summary = None
        for a in bill.analyses:
            if a.analysis_type == "summary":
                ai_summary = a.result
                break

        # Get latest text content (truncate for context window)
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
            "classification": bill.classification,
            "subject": bill.subject,
            "ai_summary": ai_summary,
            "bill_text_excerpt": bill_text,
            "actions": actions,
            "sponsors": sponsors,
        }
        return json.dumps(detail)

    elif tool_name == "list_jurisdictions":
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

    elif tool_name == "find_similar_bills":
        bill_id = arguments.get("bill_id", "")
        top_k = arguments.get("top_k", 5)

        # Check that the source bill exists
        result = await db.execute(select(Bill).where(Bill.id == bill_id))
        source_bill = result.scalar_one_or_none()
        if not source_bill:
            return json.dumps({"error": f"Bill '{bill_id}' not found."})

        # Query pre-computed similarities (canonical ordering: bill_id_a < bill_id_b)
        stmt = (
            select(BillSimilarity)
            .where((BillSimilarity.bill_id_a == bill_id) | (BillSimilarity.bill_id_b == bill_id))
            .order_by(BillSimilarity.similarity_score.desc())
            .limit(top_k)
        )
        result = await db.execute(stmt)
        similarities = result.scalars().all()

        if not similarities:
            return json.dumps({"similar_bills": [], "source_bill_id": bill_id})

        # Collect the other bill IDs
        other_ids = []
        sim_map: dict[str, float] = {}
        for s in similarities:
            other_id = s.bill_id_b if s.bill_id_a == bill_id else s.bill_id_a
            other_ids.append(other_id)
            sim_map[other_id] = float(s.similarity_score)

        stmt = select(Bill).where(Bill.id.in_(other_ids))
        result = await db.execute(stmt)
        bills_by_id = {b.id: b for b in result.scalars().all()}

        similar = []
        for other_id in other_ids:
            bill = bills_by_id.get(other_id)
            if not bill:
                continue
            similar.append(
                {
                    "bill_id": bill.id,
                    "identifier": bill.identifier,
                    "title": bill.title,
                    "jurisdiction_id": bill.jurisdiction_id,
                    "status": bill.status,
                    "similarity_score": round(sim_map.get(other_id, 0.0), 4),
                }
            )

        return json.dumps({"similar_bills": similar, "source_bill_id": bill_id})

    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})


def _generate_title(message: str) -> str:
    """Generate a short conversation title from the first user message."""
    # Take the first sentence or first 80 characters, whichever is shorter
    text = message.strip()
    for sep in (".", "?", "!"):
        idx = text.find(sep)
        if 0 < idx < 80:
            return text[: idx + 1]
    return text[:80] + ("..." if len(text) > 80 else "")


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("30/minute")
async def chat(
    request: Request,
    req: ChatRequest,
    db: AsyncSession = Depends(get_session),
) -> ChatResponse:
    """Send a message to the research assistant and get a response.

    Supports multi-turn conversation with automatic tool use for bill search,
    detail retrieval, jurisdiction listing, and similarity analysis.
    """
    import anthropic

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
    else:
        conversation = Conversation(
            id=uuid.uuid4().hex,
            client_id=request.client.host if request.client else "unknown",
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
    await db.flush()

    # 3. Build message history from conversation
    messages: list[dict] = []
    for msg in conversation.messages:
        if msg.role == "user":
            messages.append({"role": "user", "content": msg.content})
        elif msg.role == "assistant":
            messages.append({"role": "assistant", "content": msg.content})

    # 4. Call Anthropic SDK with tool_use enabled
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    model = settings.summary_model

    # Track tool calls for metadata storage
    all_tool_calls: list[dict] = []

    # 5. Agentic loop — handle multiple tool_use rounds
    api_messages = list(messages)
    for _round in range(_MAX_TOOL_ROUNDS):
        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=research_assistant_v1.SYSTEM_PROMPT,
            messages=api_messages,
            tools=RESEARCH_TOOLS,
        )

        # Check stop reason
        if response.stop_reason == "end_turn":
            # Model produced a final text response
            text_parts = []
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
            final_text = "\n".join(text_parts)
            break

        elif response.stop_reason == "tool_use":
            # Model wants to use tools — execute them and continue
            # First, add the assistant's response (with tool_use blocks) to the history
            api_messages.append({"role": "assistant", "content": response.content})

            # Process each tool_use block
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input

                    logger.info(
                        "Chat tool call: %s(%s) in conversation %s",
                        tool_name,
                        json.dumps(tool_input)[:200],
                        conversation.id,
                    )

                    try:
                        result_str = await execute_tool(tool_name, tool_input, db)
                    except Exception:
                        logger.exception("Tool execution error: %s", tool_name)
                        result_str = json.dumps(
                            {"error": f"Tool '{tool_name}' encountered an internal error."}
                        )

                    # Summarize for metadata
                    result_data = json.loads(result_str)
                    if "error" in result_data:
                        summary = result_data["error"]
                    elif "total" in result_data:
                        summary = f"{result_data['total']} results"
                    elif "bill_id" in result_data:
                        ident = result_data.get("identifier", result_data["bill_id"])
                        summary = f"Retrieved {ident}"
                    else:
                        summary = f"{len(result_str)} chars"

                    all_tool_calls.append(
                        {
                            "tool_name": tool_name,
                            "arguments": tool_input,
                            "result_summary": summary,
                        }
                    )

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str,
                        }
                    )

            # Add tool results to the conversation for the next round
            api_messages.append({"role": "user", "content": tool_results})

        else:
            # Unexpected stop reason — extract whatever text we got
            text_parts = []
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
            fallback = "I was unable to complete the request."
            final_text = "\n".join(text_parts) if text_parts else fallback
            break
    else:
        # Exhausted max rounds — extract whatever text is available
        final_text = "I reached the maximum number of research steps. Here is what I found so far."
        for block in response.content:
            if block.type == "text":
                final_text = block.text
                break

    # 6. Store assistant message with tool_calls metadata
    tool_calls_meta = all_tool_calls if all_tool_calls else None
    assistant_msg = ConversationMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=final_text,
        tool_calls=tool_calls_meta,
    )
    db.add(assistant_msg)

    # Update conversation timestamp
    conversation.updated_at = datetime.now(UTC)
    await db.commit()

    # 7. Build response
    tool_call_infos = [ToolCallInfo(**tc) for tc in all_tool_calls] if all_tool_calls else None

    return ChatResponse(
        conversation_id=conversation.id,
        message=ChatMessageResponse(
            role="assistant",
            content=final_text,
            tool_calls=tool_call_infos,
            created_at=assistant_msg.created_at,
        ),
    )


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    client_id: str | None = Query(None, description="Filter by client ID"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
) -> ConversationListResponse:
    """List conversations, optionally filtered by client ID."""
    stmt = select(Conversation)
    if client_id:
        stmt = stmt.where(Conversation.client_id == client_id)

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


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
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
