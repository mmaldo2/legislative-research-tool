---
status: pending
priority: p2
issue_id: 143
tags: [security, code-review]
---

# Conversation Enumeration Oracle via Differentiated HTTP Status Codes

## Problem Statement

Workspace chat validation returns distinct HTTP status codes (404, 403, 400) depending on
why a conversation_id is rejected. An attacker can probe conversation IDs and distinguish
"exists but forbidden" from "does not exist," enabling enumeration of valid conversation
IDs across workspaces.

## Findings

- A missing conversation returns 404.
- A conversation belonging to another workspace returns 403.
- A malformed conversation_id returns 400.
- This three-way distinction leaks information about which IDs are valid.

## Technical Details

**Files:**
- `src/api/policy_workspaces.py` — conversation_id validation logic
- `src/schemas/chat.py` — request schema for conversation_id

**Recommended fix:**
1. Collapse all inaccessible-conversation cases to a uniform 404 response with a generic
   message like `"Conversation not found"`.
2. Add UUID format validation to `conversation_id` in the request schema so malformed
   values are rejected at the Pydantic layer before hitting the database.
3. Log the actual reason (forbidden vs missing) at DEBUG level for internal diagnostics.

## Acceptance Criteria

- [ ] All conversation access failures return HTTP 404 with identical response body.
- [ ] `conversation_id` field has UUID format validation in the Pydantic schema.
- [ ] Internal logs still distinguish the failure reason at DEBUG level.
- [ ] Existing conversation tests updated to expect uniform 404.
