---
status: pending
priority: p3
issue_id: "115"
tags: [code-review, agent-native, feature]
dependencies: []
---

# Add Trend Tools to Research Assistant Chat Agent

## Problem Statement

The research assistant chat (`/api/v1/chat`) has no trend tool definitions. An agent using the chat interface cannot query trends, get topic distributions, or request LLM-generated summaries. The entire trends feature is invisible to the primary agent interface.

## Findings

- **Agent-Native Reviewer (CRITICAL)**: No trend tools in `src/llm/tools.py`. `_TOOL_HANDLERS` in `src/api/chat.py` has no trend entries. System prompt in `research_assistant_v1.py` does not mention trend capabilities.

**Note:** This is classified as P3 because it is a follow-up feature addition, not a bug in the current implementation. The REST endpoints work correctly for programmatic access; the chat agent integration is additive scope.

**Affected files:**
- `src/llm/tools.py` — Add 4 tool definitions
- `src/api/chat.py` — Add handler functions and register in `_TOOL_HANDLERS`
- `src/llm/prompts/research_assistant_v1.py` — Document trend capabilities

## Acceptance Criteria

- [ ] 4 trend tool definitions added to `RESEARCH_TOOLS`
- [ ] Handler functions registered in `_TOOL_HANDLERS`
- [ ] System prompt documents trend capabilities
- [ ] Tests cover chat agent trend tool invocation
