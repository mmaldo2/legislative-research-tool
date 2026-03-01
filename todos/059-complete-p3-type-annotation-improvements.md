---
status: complete
priority: p3
issue_id: "059"
tags: [code-review, quality, types]
dependencies: []
---

# Type Annotation Improvements: dict Params, Literal Role, Mapped Type

## Problem Statement

Several type annotations are insufficiently specific: bare `dict` without type params, `str` for constrained `role` field, and `dict` Mapped type for what's actually `list[dict]`.

## Findings

1. `arguments: dict` → `dict[str, Any]` in `execute_tool`, `ToolCallInfo` schema (`src/api/chat.py`, `src/schemas/chat.py`)
2. `role: str` → `Literal["user", "assistant"]` in `ChatMessageResponse` and `ConversationMessage` (`src/schemas/chat.py`, `src/models/conversation.py`)
3. `tool_calls: Mapped[dict | None]` → `Mapped[list[dict[str, Any]] | None]` in ConversationMessage (`src/models/conversation.py`)
4. Frontend: `role: string` → `"user" | "assistant"` in ChatMessageResponse type (`frontend/src/types/api.ts`)
5. Agent: Python Reviewer (#4-7), TypeScript Reviewer (#7)

## Proposed Solutions

### Option A: Fix all annotations
- Update all type annotations as described
- **Effort**: Small

## Technical Details

- **Files**: `src/api/chat.py`, `src/schemas/chat.py`, `src/models/conversation.py`, `frontend/src/types/api.ts`

## Acceptance Criteria

- [ ] All `dict` params have type parameters
- [ ] role fields use Literal/union types
- [ ] Mapped type on tool_calls matches actual data shape

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from PR #8 review | |

## Resources

- PR: #8
