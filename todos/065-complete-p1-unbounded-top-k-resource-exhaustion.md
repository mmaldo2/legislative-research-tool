---
status: pending
priority: p1
issue_id: "065"
tags: [code-review, security, validation, python]
dependencies: []
---

# Unbounded top_k Parameter Enables Resource Exhaustion

## Problem Statement

The `top_k` parameter in `PatternDetectRequest` has no upper bound. A malicious or careless caller can pass `top_k=10000`, causing the endpoint to load thousands of bills and concatenate their full texts into an LLM prompt, exhausting memory and token budget.

## Findings

- **Source**: Security Sentinel, Performance Oracle
- **Location**: `src/schemas/analysis.py` — `PatternDetectRequest`, `src/api/analysis.py` — patterns endpoint
- **Evidence**: No `Field(ge=1, le=20)` or similar constraint on `top_k`

## Proposed Solutions

### Option A: Add Pydantic Field validation
- Use `top_k: int = Field(default=5, ge=1, le=20)` in `PatternDetectRequest`
- **Pros**: Simple, enforced at schema level
- **Cons**: None
- **Effort**: Small
- **Risk**: None

## Recommended Action

Option A.

## Technical Details

- **Affected files**: `src/schemas/analysis.py`

## Acceptance Criteria

- [ ] `top_k` has `ge=1, le=20` constraint
- [ ] Passing top_k > 20 returns 422 validation error
- [ ] Chat tool `analyze_patterns` tool schema documents the limit

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from Phase 3 code review | |
