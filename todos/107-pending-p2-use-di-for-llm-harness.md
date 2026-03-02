---
status: pending
priority: p2
issue_id: "107"
tags: [code-review, architecture, patterns]
dependencies: []
---

# Use Depends(get_llm_harness) Instead of Lazy Import

## Problem Statement

The `/trends/summary` endpoint manually constructs `LLMHarness` via lazy imports inside the function body, bypassing the established `Depends(get_llm_harness)` dependency injection pattern used by every other LLM endpoint. This makes the endpoint harder to test and breaks DI consistency.

## Findings

- **Architecture Strategist (VIOLATION)**: Only endpoint that bypasses DI for LLMHarness.
- **Pattern Recognition (P1)**: Every other LLM endpoint uses `Depends(get_llm_harness)`.
- **Python Reviewer (MEDIUM)**: Deferred imports unnecessary — no circular import to break.

**Affected file:** `src/api/trends.py` lines 183-184, 219

## Proposed Solutions

### Option A: Use standard DI pattern (Recommended)
Replace lazy imports with `harness: LLMHarness = Depends(get_llm_harness)` in the function signature. Also release the DB session before the LLM call since `skip_store=True` means no DB access is needed.
- Effort: Small | Risk: Low

## Acceptance Criteria

- [ ] Summary endpoint uses `Depends(get_llm_harness)` in function signature
- [ ] Lazy imports of `get_anthropic_client` and `LLMHarness` removed
- [ ] DB session released before LLM call to prevent connection pool exhaustion
- [ ] Tests updated to use dependency override instead of patching module imports
