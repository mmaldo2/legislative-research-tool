---
status: complete
priority: p2
issue_id: "057"
tags: [code-review, architecture, api-design]
dependencies: []
---

# PUT with Partial-Update Semantics (Should Be PATCH) + Missing DELETE Conversations

## Problem Statement

Collection update uses `PUT` but accepts partial updates (optional fields) — should be `PATCH`. No DELETE endpoint exists for conversations, so they accumulate indefinitely.

## Findings

1. `PUT /collections/{id}` accepts `CollectionUpdate(name: str | None, description: str | None)` — partial update semantics are `PATCH`, not `PUT` (`src/api/collections.py` ~line 163)
2. Same for `PUT /collections/{id}/items/{bill_id}` with optional `notes`
3. No `DELETE /conversations/{id}` endpoint — conversations cannot be cleaned up
4. The ORM supports cascade deletion (`cascade="all, delete-orphan"`) but no route exposes it
5. Agents: Python Reviewer (#15), Agent-Native Reviewer (#1)

## Proposed Solutions

### Option A: Change to PATCH + add DELETE conversations (Recommended)
- Change `@router.put` to `@router.patch` for partial updates
- Add `DELETE /conversations/{conversation_id}` endpoint with ownership check
- **Effort**: Small
- **Risk**: Low

## Technical Details

- **Files**: `src/api/collections.py`, `src/api/chat.py`

## Acceptance Criteria

- [ ] Partial collection updates use PATCH method
- [ ] DELETE /conversations/{id} exists with ownership enforcement
- [ ] Frontend updated if needed for PATCH

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from PR #8 review | |

## Resources

- PR: #8
