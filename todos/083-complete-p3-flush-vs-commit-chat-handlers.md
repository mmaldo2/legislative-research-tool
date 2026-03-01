---
status: pending
priority: p3
issue_id: "083"
tags: [code-review, quality, python, database]
dependencies: []
---

# flush() vs commit() Inconsistency in Chat Handlers

## Problem Statement

API endpoints use `await db.commit()` after harness calls, but chat tool handlers use `await db.flush()`. If a tool handler error occurs between `flush()` and the eventual `commit()` in the chat endpoint, the analysis result (and LLM cost) will be rolled back even though it was successfully computed.

## Findings

- **Source**: Architecture Strategist
- **Location**: `src/api/chat.py:276,356`

## Proposed Solutions

### Option A: Use commit() in tool handlers
- Match API endpoint pattern
- **Effort**: Small
- **Risk**: Need to verify no transaction management expects flush-only behavior

## Acceptance Criteria

- [ ] Chat tool handlers use commit() consistently with API endpoints
- [ ] Or document why flush() is intentionally used

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from Phase 3 code review | |
