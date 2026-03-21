---
status: pending
priority: p1
issue_id: "004"
tags: [code-review, security]
dependencies: []
---

# ILIKE Wildcard Injection in Search Queries

## Problem Statement

The `q` parameter in bills and people endpoints is interpolated into ILIKE patterns without escaping `%` and `_` wildcards. A user can craft queries like `%` to match all records or use `_` for single-character wildcards, bypassing intended search behavior.

## Findings

- **security-sentinel (H2)**: ILIKE wildcard injection
- **kieran-python-reviewer (CRITICAL)**: Unescaped user input in LIKE patterns

**Affected files:**
- `src/api/bills.py` — `.ilike(f"%{q}%")`
- `src/api/people.py` — `.ilike(f"%{q}%")`

```python
# Current (vulnerable):
query = query.where(Bill.title.ilike(f"%{q}%"))

# Fixed:
from sqlalchemy import func
safe_q = q.replace("%", r"\%").replace("_", r"\_")
query = query.where(Bill.title.ilike(f"%{safe_q}%", escape="\\"))
```

## Proposed Solutions

### Option A: Escape wildcards (Recommended)
- Create a utility function `escape_like(value)` that escapes `%` and `_`
- Use SQLAlchemy's `escape` parameter on `ilike()`
- **Effort**: Small
- **Risk**: Low

## Acceptance Criteria

- [ ] `%` and `_` in search queries are escaped before ILIKE
- [ ] Utility function created and reused across endpoints
- [ ] Test verifies that literal `%` in query doesn't match all records
