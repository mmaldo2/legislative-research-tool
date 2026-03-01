---
status: complete
priority: p2
issue_id: "052"
tags: [code-review, performance, cost]
dependencies: []
---

# Chat Conversation History Unbounded + Tool Context Lost on Replay

## Problem Statement

No sliding window or token budget on conversation history. Long conversations send increasingly massive payloads to the Anthropic API. Additionally, tool_use/tool_result content blocks are not reconstructed on subsequent turns.

## Findings

1. All historical messages + tool results loaded and sent with every request — 10+ turns could be 1-2 MB of context
2. Cost per conversation could reach $1-5+ for active research sessions
3. Will eventually hit 200K token context limit, causing API errors
4. Message history reconstruction only includes plain text `content`, losing tool_use/tool_result blocks
5. Agents: Performance Oracle (CRITICAL-2), Architecture Strategist (L)

## Proposed Solutions

### Option A: Sliding window with token budget
- Cap total message history at ~100K characters
- Keep first message + most recent messages within budget
- Store raw API content blocks for faithful reconstruction
- **Effort**: Medium
- **Risk**: Low

## Technical Details

- **Files**: `src/api/chat.py`, `src/models/conversation.py`

## Acceptance Criteria

- [ ] Conversation history stays within a reasonable token budget
- [ ] Tool-use context is preserved across turns
- [ ] Long conversations don't cause API errors or cost explosions

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from PR #8 review | |

## Resources

- PR: #8
