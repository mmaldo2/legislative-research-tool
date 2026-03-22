---
status: resolved
priority: p2
issue_id: 157
tags: [code-review, bug, frontend]
dependencies: []
---

# Frontend Uses Two Different localStorage Keys for Client ID

## Problem

`api.ts` uses `"legis-client-id"` (hyphenated), `sse.ts` uses `"legis_client_id"` (underscored). A user making sync API calls gets one client ID, streaming calls get a different one. Conversations created via sync are invisible to the streaming UI and vice versa.

## Fix

Export `getClientId` from a single shared location with one consistent localStorage key.
