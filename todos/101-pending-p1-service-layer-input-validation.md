---
status: pending
priority: p1
issue_id: "101"
tags: [code-review, security, architecture]
dependencies: []
---

# Service-Layer Input Validation for bucket/group_by

## Problem Statement

The `bucket` and `group_by` parameters are validated only in the API layer (`src/api/trends.py`), not in the service functions themselves. Any direct caller (CLI, background job, another service) can pass arbitrary strings to `func.date_trunc()` and control which column expression is built.

While SQLAlchemy parameterizes the value, PostgreSQL's `date_trunc()` with an unexpected value like `'microsecond'` could produce extremely granular buckets that blow up result sets.

## Findings

- **Python Reviewer (CRITICAL)**: Service functions blindly trust their caller. Validation must live in the service layer.
- **Security Sentinel (LOW)**: Defense-in-depth concern — if any non-API code path calls these functions, the allowlist is bypassed.
- **Pattern Recognition (P2)**: Other endpoints use FastAPI validation to reject invalid input (422). Silent fallback violates the principle of least surprise.

**Affected files:**
- `src/services/trend_service.py` lines 45-56 (`bill_count_by_period`), 116-127 (`action_count_by_period`), 193-202 (`topic_distribution_by_period`)

## Proposed Solutions

### Option A: Raise ValueError in service functions (Recommended)
Add explicit validation at the top of each service function:
```python
if bucket not in VALID_BUCKETS:
    raise ValueError(f"Invalid bucket: {bucket!r}. Must be one of {VALID_BUCKETS}")
if group_by not in VALID_BILL_GROUP_BY:
    raise ValueError(f"Invalid group_by: {group_by!r}. Must be one of {VALID_BILL_GROUP_BY}")
```
- Pros: Catches programming errors, clear error messages, defense-in-depth
- Cons: Requires updating API layer to either catch ValueError or validate before calling
- Effort: Small
- Risk: Low

### Option B: Silent fallback in service layer
Move the existing fallback logic from the API layer into the service layer.
- Pros: No callers break
- Cons: Masks programming errors silently
- Effort: Small
- Risk: Low

## Acceptance Criteria

- [ ] All three service functions validate `bucket` against `VALID_BUCKETS`
- [ ] `bill_count_by_period` and `action_count_by_period` validate `group_by`
- [ ] Tests cover invalid parameter rejection
