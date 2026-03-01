from datetime import datetime

from pydantic import BaseModel

from src.schemas.common import MetaResponse


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None  # None = start new conversation


class ToolCallInfo(BaseModel):
    tool_name: str
    arguments: dict
    result_summary: str | None = None


class ChatMessageResponse(BaseModel):
    role: str
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
