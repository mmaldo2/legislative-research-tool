---
status: pending
priority: p2
issue_id: "073"
tags: [code-review, architecture, python, testability]
dependencies: []
---

# Chat Tool Handlers Bypass DI Pattern

## Problem Statement

The new chat tool handlers (`_tool_analyze_constitutional`, `_tool_analyze_patterns`) construct `LLMHarness` directly instead of receiving it via `Depends(get_llm_harness)`. This breaks the established DI pattern used by all API endpoints, reducing testability and creating maintenance risk.

## Findings

- **Source**: Architecture Strategist, Performance Oracle, Python Reviewer
- **Location**: `src/api/chat.py:268`, `src/api/chat.py:347`
- **Evidence**: `harness = LLMHarness(db_session=db, client=get_anthropic_client())` — direct construction

## Proposed Solutions

### Option A: Pass harness through execute_tool
- Construct harness once in the `chat()` endpoint via `Depends(get_llm_harness)`
- Pass it as an optional parameter to `execute_tool()` and through to handlers
- **Pros**: Follows DI pattern, testable, single construction site
- **Effort**: Medium
- **Risk**: Low

## Recommended Action

Option A.

## Technical Details

- **Affected files**: `src/api/chat.py`
- **Reference pattern**: `src/api/deps.py:50-53`

## Acceptance Criteria

- [ ] Chat tool handlers receive harness via DI, not direct construction
- [ ] `execute_tool()` signature updated to accept optional harness
- [ ] All existing chat tests still pass

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from Phase 3 code review | |
