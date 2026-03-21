---
status: pending
priority: p1
issue_id: "066"
tags: [code-review, agent-parity, python, chat]
dependencies: []
---

# Missing version_diff Chat Tool + System Prompt Not Updated

## Problem Statement

Two agent-parity issues:
1. No `analyze_version_diff` tool is defined in `src/llm/tools.py` or handled in `src/api/chat.py`. Users can access version diff via API but not via the research assistant chat.
2. The research assistant system prompt (`src/llm/prompts/research_assistant_v1.py`) does not mention the two new tools (`analyze_constitutional`, `analyze_patterns`), reducing the model's ability to select them.

## Findings

- **Source**: Agent-Native Reviewer, Architecture Strategist
- **Location**: `src/llm/tools.py`, `src/api/chat.py`, `src/llm/prompts/research_assistant_v1.py`
- **Evidence**: Only 2 of 3 new analysis types have chat tools; system prompt lists only original 4 tools

## Proposed Solutions

### Option A: Add version_diff tool + update system prompt
- Define `analyze_version_diff` tool schema in `tools.py`
- Add `_tool_analyze_version_diff` handler in `chat.py`
- Update system prompt to document all 6 available tools
- **Pros**: Complete agent parity, better tool selection
- **Cons**: Adds more code to chat.py (but consistent with existing pattern)
- **Effort**: Medium
- **Risk**: Low

## Recommended Action

Option A.

## Technical Details

- **Affected files**: `src/llm/tools.py`, `src/api/chat.py`, `src/llm/prompts/research_assistant_v1.py`

## Acceptance Criteria

- [ ] `analyze_version_diff` tool defined in tools.py
- [ ] Chat handler for version_diff exists and works
- [ ] System prompt lists all 6 tools with descriptions
- [ ] Chat assistant can invoke all 3 new analysis types

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from Phase 3 code review | |
