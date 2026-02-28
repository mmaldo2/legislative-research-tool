---
status: pending
priority: p3
issue_id: "016"
tags: [code-review, quality]
dependencies: []
---

# Dead and Unused Code Cleanup

## Problem Statement

Several schemas, models, and test utilities are defined but never used, adding ~151 lines of dead weight to the codebase.

## Findings

- **code-simplicity-reviewer**: BillComparisonOutput, PaginationParams, SearchRequest are unused
- **code-simplicity-reviewer**: Dead test mock code in test files
- **kieran-python-reviewer**: BillSimilarity model appears unused

**Items to remove:**
- `BillComparisonOutput` schema — speculative, no endpoint uses it
- `PaginationParams` — defined but endpoints use inline Query params
- `SearchRequest` — dead code in search.py
- Dead mock/fixture code in test files
- Unused `BillSimilarity` model (if confirmed unused)

## Proposed Solutions

### Option A: Remove all dead code (Recommended)
- Delete unused schemas, models, and test code
- Verify nothing references them via grep
- **Effort**: Small
- **Risk**: Low

## Acceptance Criteria

- [ ] No unused schema/model definitions remain
- [ ] grep confirms removed items have no references
- [ ] Tests still pass after removal
