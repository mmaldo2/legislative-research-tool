---
status: pending
priority: p2
issue_id: "123"
tags: [code-review, prediction, security, quality]
dependencies: []
---

# Schema Strictness and Input Validation

## Problem Statement

Several schema and validation gaps flagged by Security and Python reviewers.

## Findings

1. **`PredictionFactor.impact` is `str` not `Literal["positive", "negative"]`** (`schemas.py:13`): Comment documents two values but type is unconstrained. Loses OpenAPI enum documentation and validation.

2. **No input validation on `bill_id`** (`prediction.py:22`): Accepts arbitrary strings with no format constraint or max length. SQL injection is not possible (parameterized), but allows arbitrarily long strings and special characters.

3. **`_build_single_bill_features` takes untyped `row`** (`service.py:177`): No type hint at all — should be at least `Mapping[str, Any]`.

## Proposed Solutions

### Fix all three (Small effort each):
1. `impact: Literal["positive", "negative"]`
2. `bill_id: str = Path(..., max_length=128, pattern=r"^[a-zA-Z0-9/_-]+$")`
3. `def _build_single_bill_features(row: Mapping[str, Any])`

## Acceptance Criteria

- [ ] `impact` field uses Literal type
- [ ] `bill_id` has Path validation with max_length and pattern
- [ ] `_build_single_bill_features` has type-hinted parameter

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-18 | Created | Security + Python reviewers |
