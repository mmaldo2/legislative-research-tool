---
status: pending
priority: p2
issue_id: "124"
tags: [code-review, prediction, agent-native, chat]
dependencies: []
---

# Agent-Native Parity: Add predict_bill_passage Chat Tool

## Problem Statement

The chat agent has no tool to access bill predictions. Users can get predictions via REST API but not through the conversational interface. Agent-native reviewer scored 9/10 capabilities agent-accessible — prediction is the gap.

## Findings

- No `predict_bill_passage` tool in `src/llm/tools.py`
- No handler in `src/api/chat.py` `_TOOL_HANDLERS` dict
- System prompt (`src/llm/prompts/research_assistant_v1.py`) doesn't mention prediction
- Both prediction and chat are pro+ tier — no access mismatch
- Existing `predict_outcome` in `src/llm/harness.py` is LLM-based (qualitative); ML prediction is quantitative — both should be accessible with clear differentiation
- Agent reviewer suggests including bill `identifier` and `title` in predict_bill() return for richer agent responses

## Proposed Solutions

### Add tool in 3 files:
1. Tool schema in `src/llm/tools.py` — `predict_bill_passage` with `bill_id` input
2. Handler in `src/api/chat.py` — call `predict_bill()`, handle model-not-loaded gracefully
3. System prompt entry — describe tool, differentiate from qualitative predict_outcome

**NOTE:** This is already planned as work item #2 in the handoff prompt.

## Acceptance Criteria

- [ ] `predict_bill_passage` tool defined in tools.py
- [ ] Handler registered in chat.py `_TOOL_HANDLERS`
- [ ] System prompt describes the prediction tool and when to use it
- [ ] Agent can answer "what's the probability this bill passes?"

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-18 | Created | Agent-native reviewer — planned as next work item |
