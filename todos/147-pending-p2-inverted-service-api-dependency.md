---
status: pending
priority: p2
issue_id: 147
tags: [architecture, code-review]
---

# Inverted Dependency — chat_service.py Imports from API Layer

## Problem Statement

`chat_service.py` imports `execute_tool` from `src/api/chat.py`, creating a service ->
API layer dependency inversion. Services should not depend on API layer modules; the
dependency should flow API -> Service.

## Findings

- `src/services/chat_service.py` has a direct import from `src/api/chat.py`.
- This makes the service untestable without the full API layer and creates a circular
  dependency risk.
- The tool handler logic and dispatch registry logically belong in the service layer.

## Technical Details

**Files:**
- `src/services/chat_service.py` — contains the inverted import
- `src/api/chat.py` — source of `execute_tool` and tool handler functions

**Recommended fix:**
1. Move the tool handler functions and the dispatch registry from `src/api/chat.py` to
   either `src/services/chat_service.py` or a new `src/services/tool_registry.py`.
2. Update `src/api/chat.py` to import from the service layer.
3. Ensure all existing tests and imports are updated accordingly.

## Acceptance Criteria

- [ ] No imports from `src/api/` exist in `src/services/`.
- [ ] Tool handlers and dispatch registry live in the service layer.
- [ ] `src/api/chat.py` imports from the service layer, not vice versa.
- [ ] All existing tests pass after the move.
