---
status: pending
priority: p3
issue_id: "021"
tags: [code-review, quality]
dependencies: []
---

# Duplicate get_session Definition

## Problem Statement

`get_session()` is defined in both `src/api/deps.py` and `src/database.py`. Having two session factories creates confusion about which to import and risks configuration drift.

## Findings

- **kieran-python-reviewer (LOW)**: Duplicate function

**Affected files:**
- `src/api/deps.py` — `get_session()`
- `src/database.py` — `get_session()` or similar

## Proposed Solutions

### Option A: Single source in deps.py (Recommended)
- Remove duplicate from `src/database.py`
- All API code imports from `src/api/deps.py`
- Non-API code (CLI, ingestion) uses `async_session_factory` directly
- **Effort**: Small
- **Risk**: Low

## Acceptance Criteria

- [ ] `get_session` defined in exactly one place
- [ ] All imports updated
