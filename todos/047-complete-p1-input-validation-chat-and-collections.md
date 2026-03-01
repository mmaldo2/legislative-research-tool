---
status: complete
priority: p1
issue_id: "047"
tags: [code-review, security, validation]
dependencies: []
---

# Missing Input Validation: Unbounded Chat Message + Collection Name

## Problem Statement

`ChatRequest.message` has no length constraint, enabling cost-of-service attacks via Anthropic API. `CollectionCreate.name` and `description` also have no length limits, enabling database storage abuse.

## Findings

1. `ChatRequest.message: str` has no `max_length` — attacker can send megabytes of text per request (`src/schemas/chat.py` line 9)
2. Each message is stored in DB (Text column, unlimited) and replayed in conversation history, compounding costs
3. With 30 req/min rate limit, an attacker could rapidly accumulate massive Anthropic API costs
4. `CollectionCreate.name: str` has no constraints — zero-length or 10K+ character names pass validation (`src/schemas/collection.py` line 11)
5. Agents: Security Sentinel (C3, L1), Python Reviewer (#16)

## Proposed Solutions

### Option A: Pydantic Field constraints (Recommended)
- Add `Field(min_length=1, max_length=10_000)` to ChatRequest.message
- Add `Field(min_length=1, max_length=200)` to CollectionCreate.name
- Add `Field(max_length=2000)` to CollectionCreate.description
- **Effort**: Small
- **Risk**: Low

## Technical Details

- **Files**: `src/schemas/chat.py`, `src/schemas/collection.py`

## Acceptance Criteria

- [ ] ChatRequest.message rejects empty and >10K character messages with 422
- [ ] CollectionCreate.name rejects empty and >200 character names with 422
- [ ] CollectionCreate.description rejects >2000 characters with 422

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from PR #8 review | |

## Resources

- PR: #8
