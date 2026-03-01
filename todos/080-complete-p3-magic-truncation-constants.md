---
status: pending
priority: p3
issue_id: "080"
tags: [code-review, quality, python]
dependencies: []
---

# Magic Truncation Numbers Should Be Named Constants

## Problem Statement

Harness methods use magic numbers for text truncation (`25_000`, `50_000`, `4096` max_tokens) without named constants explaining what they represent or why those values were chosen.

## Findings

- **Source**: Python Reviewer
- **Location**: `src/llm/harness.py`

## Proposed Solutions

### Option A: Extract to module-level constants
```python
MAX_SINGLE_TEXT_CHARS = 50_000
MAX_PAIRED_TEXT_CHARS = 25_000
DEFAULT_ANALYSIS_MAX_TOKENS = 4096
```
- **Effort**: Small

## Acceptance Criteria

- [ ] Magic numbers replaced with named constants
- [ ] Constants have brief docstring/comment explaining rationale

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from Phase 3 code review | |
