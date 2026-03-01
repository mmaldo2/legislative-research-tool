---
status: pending
priority: p1
issue_id: "067"
tags: [code-review, bug, python]
dependencies: []
---

# version_name May Be None, Renders as "None" in Prompt

## Problem Statement

`BillText.version_name` is nullable. When passed into the version-diff prompt template, a `None` value renders as the string `"None"`, producing confusing LLM output like "Version A (None) vs Version B (None)".

## Findings

- **Source**: Python Reviewer
- **Location**: `src/api/analysis.py` — version-diff endpoint, `src/llm/prompts/version_diff_v1.py`
- **Evidence**: `BillText.version_name` is `Optional[str]` in the ORM model

## Proposed Solutions

### Option A: Default to fallback label
- Use `text.version_name or f"Version {index+1}"` or `text.version_name or "Untitled Version"` when formatting prompt
- **Pros**: Simple, prevents "None" in prompts
- **Cons**: None
- **Effort**: Small
- **Risk**: None

## Recommended Action

Option A.

## Technical Details

- **Affected files**: `src/api/analysis.py`

## Acceptance Criteria

- [ ] Null version_name renders as a meaningful fallback (not "None")
- [ ] Prompt text is clean and readable for the LLM

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from Phase 3 code review | |
