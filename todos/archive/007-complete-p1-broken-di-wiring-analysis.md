---
status: pending
priority: p1
issue_id: "007"
tags: [code-review, architecture]
dependencies: []
---

# Broken Dependency Injection in Analysis Endpoints

## Problem Statement

`src/api/analysis.py` calls `get_llm_harness(db)` directly instead of using `Depends(get_llm_harness)`. This bypasses FastAPI's DI system and means the harness doesn't participate in the request lifecycle properly.

## Findings

- **kieran-python-reviewer (HIGH)**: Missing Depends injection
- **architecture-strategist**: Incomplete DI wiring

**Affected file:** `src/api/analysis.py`

```python
# Current (broken):
async def summarize_bill(request: SummarizeRequest, db: AsyncSession = Depends(get_session)):
    harness = get_llm_harness(db)  # Direct call, not injected

# Fixed:
async def summarize_bill(
    request: SummarizeRequest,
    db: AsyncSession = Depends(get_session),
    harness: LLMHarness = Depends(get_llm_harness),
):
```

## Proposed Solutions

### Option A: Fix Depends chain (Recommended)
- Update `get_llm_harness` to use `Depends(get_session)`
- Inject harness via `Depends` in endpoint signature
- **Effort**: Small
- **Risk**: Low

## Acceptance Criteria

- [ ] `get_llm_harness` uses `Depends(get_session)` for its session
- [ ] Analysis endpoints inject harness via `Depends`
- [ ] No direct function calls bypassing DI
