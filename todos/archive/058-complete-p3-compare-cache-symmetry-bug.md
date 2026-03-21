---
status: complete
priority: p3
issue_id: "058"
tags: [code-review, performance, quality]
dependencies: []
---

# Compare Cache Symmetry Bug + Content Hash Truncation Mismatch

## Problem Statement

`harness.compare()` caches by `bill_id_a` only, so `compare(A,B)` and `compare(B,A)` don't share cache. Also, the content hash is computed over full text but the prompt truncates to 25K chars, causing unnecessary cache misses for bills that differ only beyond the truncation point.

## Findings

1. Cache stores under `bill_id=bill_id_a` — reversed comparison misses cache (`src/llm/harness.py` ~line 289)
2. Content hash: `f"{bill_a_text}:{bill_b_text}"` is order-dependent (~line 245)
3. Hash computed on full text but prompt truncates each to 25K chars (~line 254) — same issue exists in `summarize()` with 50K truncation
4. Agents: Simplicity Reviewer (#10), Performance Oracle (OPT-3, OPT-4)

## Proposed Solutions

### Option A: Canonicalize + truncate before hash
- Sort bill IDs to create canonical order before hashing
- Truncate texts before hashing to match prompt truncation
- Store under canonical_bill_id_a (the sorted-first one)
- **Effort**: Small

## Technical Details

- **Files**: `src/llm/harness.py`

## Acceptance Criteria

- [ ] compare(A,B) and compare(B,A) share the same cache entry
- [ ] Content hash matches the actual text sent to the LLM

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from PR #8 review | |

## Resources

- PR: #8
