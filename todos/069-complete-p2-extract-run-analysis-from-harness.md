---
status: pending
priority: p2
issue_id: "069"
tags: [code-review, refactor, python, duplication]
dependencies: []
---

# Extract _run_analysis from Harness to Reduce Duplication (~120 LOC)

## Problem Statement

All 6 harness methods (`summarize`, `classify`, `compare`, `version_diff`, `constitutional_analysis`, `pattern_detect`) follow an identical 10-step template: check cache, format prompt, call API, parse JSON with fallback, record cost, store result, return. The only differences are the prompt module, model, content hash, max_tokens, and output type.

## Findings

- **Source**: Code Simplicity Reviewer, Python Reviewer
- **Location**: `src/llm/harness.py` — all 6 methods
- **Evidence**: ~80 lines of identical boilerplate per method, only ~5-10 lines differ

## Proposed Solutions

### Option A: Extract `_run_analysis()` generic method
```python
async def _run_analysis(
    self,
    analysis_type: str,
    content_hash: str,
    system_prompt: str,
    user_prompt: str,
    prompt_version: str,
    model: str,
    max_tokens: int,
    output_type: type[T],
    bill_id: str,
    **kwargs,
) -> T:
```
- **Pros**: ~120 LOC saved, single place to add guard for empty response.content, DRY
- **Cons**: Requires generic type parameter handling
- **Effort**: Medium
- **Risk**: Low — each method becomes a thin wrapper

## Recommended Action

Option A.

## Technical Details

- **Affected files**: `src/llm/harness.py`
- **Related**: todo 068 (empty response guard can be added to _run_analysis)

## Acceptance Criteria

- [ ] All 6 harness methods delegate to `_run_analysis()`
- [ ] Each method is reduced to ~10-15 lines (hash + format + call)
- [ ] All existing tests still pass
- [ ] Empty response guard added in _run_analysis

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from Phase 3 code review | |
