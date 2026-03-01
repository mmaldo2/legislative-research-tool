---
status: complete
priority: p2
issue_id: "012"
tags: [code-review, bug]
dependencies: []
---

# Search Pagination total_count Reports Wrong Value

## Problem Statement

The search endpoint returns `total_count = len(results)` which is just the page size, not the true total number of matching results. This breaks client-side pagination.

## Findings

- **kieran-python-reviewer (HIGH)**: `total_count` is page count, not total
- **agent-native-reviewer**: Search pagination is lossy

**Affected file:** `src/api/search.py`

## Proposed Solutions

### Option A: Separate count query (Recommended)
- Run a COUNT query before paginating results
- Return true total in response
- **Effort**: Small
- **Risk**: Low (adds one DB query)

### Option B: Return has_more flag instead
- Don't report total, just indicate if more pages exist
- **Effort**: Small
- **Risk**: Low

## Acceptance Criteria

- [ ] `total_count` reflects true number of matching results, not page size
- [ ] Pagination metadata (page, per_page, total) is consistent
