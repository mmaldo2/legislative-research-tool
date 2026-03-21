---
status: pending
priority: p2
issue_id: "141"
tags: [code-review, composer, backend, quality, conventions]
dependencies: []
---

# Missing Type Annotations on Helper Functions

## Problem Statement

Three helper functions in `src/api/policy_workspaces.py` lack type annotations, violating the project convention of "type hints everywhere."

## Findings

1. **`_build_generation_response(generation)`** at line 441 — missing `generation: PolicyGeneration`
2. **`_latest_outline_generation(workspace)`** at line 56 — missing return type `-> PolicyGeneration | None`
3. **`_get_workspace_or_error`** at line 130 — missing return type `-> PolicyWorkspace`

## Proposed Solutions

### Option A: Add annotations (Recommended)
- Effort: Small
- Risk: Low

## Acceptance Criteria

- [ ] All three functions have complete type annotations

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-21 | Created | Found during code review by Python reviewer |
