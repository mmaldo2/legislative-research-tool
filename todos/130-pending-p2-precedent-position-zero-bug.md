---
status: complete
priority: p2
issue_id: "130"
tags: [code-review, composer, backend, data-integrity, ordering]
dependencies: []
---

# Auto-Appended Precedents Reuse Position 0

## Problem Statement

The auto-positioning logic for new precedents treats `0` as falsy, so once the first precedent is stored at position `0`, the next auto-appended precedent is also assigned position `0` instead of `1`. That breaks deterministic ordering for precedent lists and can change the order fed into outline generation.

## Findings

1. **The append path computes the next position with `scalar_one() or -1`** in `src/services/policy_workspace_service.py:199-205`.
2. **Because `0` is falsy in Python**, an existing max position of `0` is converted to `-1`, yielding another `0` on increment.
3. **Composer relies on precedent order as meaningful input** for the drafting flow, so duplicate positions can make UI ordering and LLM context ordering unstable.

## Proposed Solutions

### Option A: Treat `None` distinctly from `0` (Recommended)
1. Store `max_position = max_pos_result.scalar_one()`.
2. Compute `precedent_position = (max_position if max_position is not None else -1) + 1`.
3. Add a service test that inserts one precedent at `0` and verifies the next auto-appended precedent gets `1`.
- Effort: Small
- Risk: Low

### Option B: Enforce a unique ordering strategy per workspace
1. Add normalization logic that rewrites positions after insert/delete.
2. Optionally add a `(workspace_id, position)` uniqueness constraint if the project wants strict ordering guarantees.
3. Cover reorder and delete scenarios in tests.
- Effort: Medium
- Risk: Medium

## Acceptance Criteria

- [ ] Auto-appended precedents increment correctly from `0` to `1`, `2`, and so on
- [ ] Duplicate positions are no longer created by the default append path
- [ ] Tests cover the `max position == 0` case explicitly
- [ ] Composer detail view preserves deterministic precedent ordering after multiple adds

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-20 | Created | Found during Phase 1/2 composer review |
