---
status: pending
priority: p2
issue_id: "112"
tags: [code-review, security, validation]
dependencies: []
---

# Add Max Date Range Validation

## Problem Statement

When `date_from` and `date_to` are user-supplied, there is no validation that the range is reasonable. A request with `date_from=1900-01-01&date_to=2100-12-31` could produce massive intermediate result sets, especially for `unnest()` queries on ARRAY columns.

## Findings

- **Security Sentinel (MEDIUM)**: Unbounded date range enables expensive queries (DoS vector).
- **Performance Oracle**: Combined with 256-entry cache, varied expensive queries bypass caching.

**Affected file:** `src/api/trends.py` lines 62-63

## Proposed Solutions

### Option A: Add validation in API endpoints (Recommended)
```python
MAX_DATE_RANGE_DAYS = 1095  # ~3 years
if date_from and date_to:
    if date_from > date_to:
        raise HTTPException(400, "date_from must be before date_to")
    if (date_to - date_from).days > MAX_DATE_RANGE_DAYS:
        raise HTTPException(400, f"Date range cannot exceed {MAX_DATE_RANGE_DAYS} days")
```
- Effort: Small | Risk: Low

## Acceptance Criteria

- [ ] `date_from <= date_to` validation added
- [ ] Maximum date range enforced (e.g., 3 years)
- [ ] Structured JSON error response for invalid ranges
- [ ] Tests cover both validation cases
