---
status: pending
priority: p2
issue_id: "070"
tags: [code-review, refactor, python, duplication, architecture]
dependencies: []
---

# Extract Similar-Bills Lookup to Shared Module (4 Copies)

## Problem Statement

The "find similar bills" logic exists in 4 locations with slightly different implementations:
1. `src/api/compare.py:56-93` — pgvector + fallback, with optional jurisdiction filter
2. `src/api/analysis.py:218-261` — pgvector + fallback, with jurisdiction exclusion
3. `src/api/chat.py:183-244` — ORM-based `BillSimilarity`, no jurisdiction filter
4. `src/api/chat.py:304-330` — ORM-based `BillSimilarity`, no jurisdiction filter (bug: see todo 064)

These divergent implementations cause bugs (missing jurisdiction filter in chat) and make maintenance difficult.

## Findings

- **Source**: Architecture Strategist, Code Simplicity Reviewer, Python Reviewer
- **Location**: 4 files listed above
- **Evidence**: Raw SQL duplicated, ORM version diverges from SQL version

## Proposed Solutions

### Option A: Extract to `src/search/similarity.py`
```python
async def find_similar_bills(
    session: AsyncSession,
    bill_id: str,
    exclude_jurisdiction: str | None = None,
    min_score: float = 0.0,
    top_k: int = 10,
) -> list[tuple[str, float]]:
    """Try pgvector first, fall back to bill_similarities table."""
```
- **Pros**: Single source of truth, fixes jurisdiction bug, ~40 LOC saved per caller
- **Cons**: Requires updating 4 call sites
- **Effort**: Medium
- **Risk**: Low

## Recommended Action

Option A. This also fixes todo 064 (jurisdiction filter bug).

## Technical Details

- **Affected files**: `src/search/similarity.py` (new), `src/api/compare.py`, `src/api/analysis.py`, `src/api/chat.py`
- **Related**: todo 064 (jurisdiction filter bug)

## Acceptance Criteria

- [ ] Single `find_similar_bills()` function in search layer
- [ ] All 4 callers use the shared function
- [ ] Jurisdiction exclusion parameter works correctly
- [ ] Fallback from pgvector to bill_similarities works

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from Phase 3 code review | |
