---
status: pending
priority: p1
issue_id: "005"
tags: [code-review, security]
dependencies: []
---

# F-String SQL Composition in Vector Search

## Problem Statement

`src/search/vector.py` constructs SQL using f-string interpolation with `text()`. While the current `where_clause` is hardcoded and not user-controlled, this pattern is fragile and could become a SQL injection vector if the function signature changes.

## Findings

- **kieran-python-reviewer (CRITICAL)**: f-string SQL composition
- **security-sentinel (H1)**: SQL injection pattern

**Affected file:** `src/search/vector.py`

```python
sql = text(f"""
    SELECT be.bill_id, 1 - (be.embedding <=> :embedding::vector) AS similarity
    FROM bill_embeddings be JOIN bills b ON b.id = be.bill_id
    WHERE be.embedding IS NOT NULL {where_clause}
    ORDER BY be.embedding <=> :embedding::vector LIMIT :limit
""")
```

## Proposed Solutions

### Option A: SQLAlchemy Core query builder (Recommended)
- Use `select()`, `join()`, `where()` instead of raw SQL
- Dynamically add where clauses via `.where()` chaining
- **Effort**: Medium
- **Risk**: Low

### Option B: Parameterized SQL with conditional clauses
- Build where clause list and join with AND, using only bound params
- **Effort**: Small
- **Risk**: Low

## Acceptance Criteria

- [ ] No f-string interpolation in SQL queries
- [ ] All user-facing values use bound parameters
- [ ] Vector search still works correctly with jurisdiction filter
