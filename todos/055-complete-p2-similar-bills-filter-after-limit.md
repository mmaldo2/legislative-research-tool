---
status: complete
priority: p2
issue_id: "055"
tags: [code-review, performance, quality]
dependencies: []
---

# exclude_same_jurisdiction Filter Applied After SQL LIMIT

## Problem Statement

The `exclude_same_jurisdiction` parameter is accepted but applied in Python after the database query returns `top_k` results. If many top results are from the same jurisdiction, the user gets fewer than `top_k` results.

## Findings

1. pgvector query applies `LIMIT :top_k` in SQL (`src/api/compare.py` ~line 58)
2. Jurisdiction exclusion applied in Python post-fetch (~line 109)
3. User requesting top_k=10 with exclude_same_jurisdiction=True may get 3 results if 7 are same-jurisdiction
4. Agents: Python Reviewer (#1), Architecture Strategist (C), Performance Oracle

## Proposed Solutions

### Option A: Push filter into SQL (Recommended)
- Add `AND b.jurisdiction_id != (SELECT jurisdiction_id FROM bills WHERE id = :bill_id)` to the query
- **Effort**: Small
- **Risk**: Low

## Technical Details

- **Files**: `src/api/compare.py`

## Acceptance Criteria

- [ ] Jurisdiction exclusion happens in SQL, before LIMIT
- [ ] Users always get up to top_k results when available

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from PR #8 review | |

## Resources

- PR: #8
