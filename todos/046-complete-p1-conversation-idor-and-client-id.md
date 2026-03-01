---
status: complete
priority: p1
issue_id: "046"
tags: [code-review, security, architecture]
dependencies: []
---

# Conversation IDOR: No Ownership Enforcement + Client ID Inconsistency

## Problem Statement

The conversation endpoints have no ownership enforcement — any authenticated API user can read, hijack, or list all conversations. Additionally, the chat endpoint uses `request.client.host` (IP address) for `client_id` while collections use the `X-Client-Id` header, creating an inconsistent identity model.

## Findings

1. **GET /conversations/{id}** has zero ownership check — any user can read any conversation by ID (`src/api/chat.py` ~line 455)
2. **POST /chat** allows appending messages to any conversation by supplying a known `conversation_id` — no ownership verification (`src/api/chat.py` ~line 254)
3. **GET /conversations** without `client_id` parameter returns ALL conversations system-wide (`src/api/chat.py` ~line 420)
4. **client_id inconsistency**: Chat uses `request.client.host` (IP) while collections use `X-Client-Id` header, meaning the same user's chat and collections have different identities
5. Agents: Security Sentinel (C1, H3), Python Reviewer (#3), Architecture Strategist (M), Agent-Native Reviewer (#2)

## Proposed Solutions

### Option A: Unify on X-Client-Id header (Recommended)
- Add `get_client_id` dependency to chat endpoints matching collections pattern
- Add ownership checks: `if conversation.client_id != client_id: raise 403`
- Make `client_id` mandatory on GET /conversations (not optional query param)
- **Pros**: Consistent identity model, simple to implement
- **Cons**: Still spoofable (no real auth)
- **Effort**: Small
- **Risk**: Low

### Option B: Shared dependency + middleware
- Create shared `get_client_id` in deps.py used by both modules
- **Pros**: DRY, single source of truth
- **Cons**: Slightly more refactoring
- **Effort**: Small-Medium
- **Risk**: Low

## Technical Details

- **Files**: `src/api/chat.py`, `src/api/collections.py` (reference pattern)
- **Components**: Chat API, conversation persistence

## Acceptance Criteria

- [ ] GET /conversations/{id} returns 403 for non-owner
- [ ] POST /chat with another user's conversation_id returns 403
- [ ] GET /conversations requires client_id and only returns owned conversations
- [ ] Chat and collections use the same X-Client-Id identity mechanism
- [ ] Tests verify ownership enforcement

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from PR #8 review | Multiple agents flagged this independently |

## Resources

- PR: #8
- Related: todos/001-complete-p1-no-authentication-on-api.md
