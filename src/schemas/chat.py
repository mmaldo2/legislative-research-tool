from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.schemas.common import MetaResponse


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10_000)
    conversation_id: str | None = None  # None = start new conversation


class ToolCallInfo(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    result_summary: str | None = None


class ChatMessageResponse(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    tool_calls: list[ToolCallInfo] | None = None
    created_at: datetime | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    message: ChatMessageResponse


class ConversationResponse(BaseModel):
    id: str
    title: str | None = None
    messages: list[ChatMessageResponse] = []
    created_at: datetime | None = None


class ConversationListResponse(BaseModel):
    data: list[ConversationResponse]
    meta: MetaResponse
