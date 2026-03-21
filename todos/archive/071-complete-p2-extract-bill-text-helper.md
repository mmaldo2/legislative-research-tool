---
status: pending
priority: p2
issue_id: "071"
tags: [code-review, refactor, python, duplication]
dependencies: []
---

# Extract _extract_bill_text to Shared Utility (6 Copies)

## Problem Statement

The pattern of "get best text for a bill, falling back to title" is inlined in 6 locations. `compare.py` already has an `_extract_bill_text()` helper — promote it to a shared utility.

## Findings

- **Source**: Architecture Strategist, Code Simplicity Reviewer, Python Reviewer
- **Locations**:
  1. `src/api/compare.py:174-180` — extracted helper (reference)
  2. `src/api/analysis.py:51-56` — inline
  3. `src/api/analysis.py:177-182` — inline
  4. `src/api/analysis.py:210-215` — inline
  5. `src/api/chat.py:261-266` — inline
  6. `src/api/chat.py:296-302` — inline

## Proposed Solutions

### Option A: Move to shared utility
- Move `_extract_bill_text(bill)` to `src/services/bill_utils.py` or as a method on the Bill model
- Replace all 6 inline copies with the shared function
- **Pros**: ~15 LOC saved per copy, consistent behavior
- **Effort**: Small
- **Risk**: None

## Recommended Action

Option A.

## Technical Details

- **Affected files**: `src/api/compare.py`, `src/api/analysis.py`, `src/api/chat.py`

## Acceptance Criteria

- [ ] Single shared `extract_bill_text()` function
- [ ] All callers use the shared function
- [ ] Behavior identical to existing `compare.py` helper

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from Phase 3 code review | |
