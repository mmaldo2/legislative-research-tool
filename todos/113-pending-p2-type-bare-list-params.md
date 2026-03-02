---
status: pending
priority: p2
issue_id: "113"
tags: [code-review, quality, type-safety]
dependencies: []
---

# Type Bare list Parameters with Protocol/NamedTuple

## Problem Statement

`_apply_top_n(rows: list, ...)` and `_trend_to_csv(data: list, ...)` use bare `list` with no element type. The type system cannot verify that elements have `.period`, `.dimension`, `.count` attributes. Also, test helper `_make_row` returns `MagicMock` instead of a typed object.

## Findings

- **Python Reviewer (HIGH)**: Bare `list` is a type safety failure.
- **Python Reviewer (LOW)**: Test helper should use NamedTuple instead of MagicMock.

**Affected files:**
- `src/services/trend_service.py` line 300
- `src/api/trends.py` line 35
- `tests/test_services/test_trend_service.py` line 27

## Proposed Solutions

### Option A: Define Protocol + NamedTuple (Recommended)
```python
from typing import Protocol
class AggregateRow(Protocol):
    period: datetime
    dimension: str
    count: int
```
Use `NamedTuple` for test rows. Type `_trend_to_csv` as `data: Sequence[BaseModel]`.
- Effort: Small | Risk: Low

## Acceptance Criteria

- [ ] `_apply_top_n` parameter typed with Protocol
- [ ] `_trend_to_csv` parameter typed appropriately
- [ ] Test `_make_row` uses NamedTuple instead of MagicMock
