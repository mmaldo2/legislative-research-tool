---
status: pending
priority: p2
issue_id: 174
tags: [code-review, quality]
dependencies: []
---

# Duplicated _build_sdk_prompt Logic

## Problem Statement
`_build_sdk_prompt()` in `src/services/chat_service.py:353-375` is character-for-character identical to `_build_prompt()` in `src/llm/claude_sdk_adapter.py:209-235`. Both flatten system prompt + messages into XML-tagged text. DRY violation — changes must be made in two places.

## Proposed Solutions
### Option A: Delete duplicate, import from adapter
- **Effort**: Small
- Import `_build_prompt` from `claude_sdk_adapter.py` in `chat_service.py`

### Option B: Move to shared location
- **Effort**: Small
- Create `src/llm/prompt_utils.py` with the shared function

## Technical Details
- **Files**: `src/services/chat_service.py:353-375`, `src/llm/claude_sdk_adapter.py:209-235`

## Acceptance Criteria
- [ ] Single source of truth for prompt flattening logic
- [ ] Both adapter and chat_service use the same function

## Work Log
- 2026-03-22: Created from code review
