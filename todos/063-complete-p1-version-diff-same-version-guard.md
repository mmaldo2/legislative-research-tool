---
status: pending
priority: p1
issue_id: "063"
tags: [code-review, security, validation, python]
dependencies: []
---

# Missing version_a == version_b Guard in Version-Diff Endpoint

## Problem Statement

The `/analyze/version-diff` endpoint does not guard against the user passing the same version ID for both `version_a_id` and `version_b_id`. This would produce a meaningless diff comparing identical texts and waste an LLM call.

## Findings

- **Source**: Python Reviewer, Architecture Strategist
- **Location**: `src/api/analysis.py` — version-diff endpoint
- **Evidence**: No validation that version_a_id != version_b_id before invoking the harness

## Proposed Solutions

### Option A: Add validation at the endpoint level
- Add a check after resolving version IDs: if they resolve to the same text (by index or ID), raise HTTPException(400)
- **Pros**: Simple, catches the issue early, saves LLM cost
- **Cons**: None
- **Effort**: Small
- **Risk**: None

## Recommended Action

Option A — add a simple guard.

## Technical Details

- **Affected files**: `src/api/analysis.py`

## Acceptance Criteria

- [ ] Passing same version_a_id and version_b_id returns 400 error
- [ ] Passing same resolved versions (e.g., both default to first) returns 400
- [ ] Error message is descriptive

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from Phase 3 code review | |
