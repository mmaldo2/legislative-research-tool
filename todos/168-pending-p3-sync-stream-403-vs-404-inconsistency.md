---
status: pending
priority: p3
issue_id: 168
tags: [code-review, security, api-consistency]
dependencies: []
---

# 403 vs 404 Inconsistency Between Sync and Stream Chat Endpoints

## Problem

Sync `POST /chat` returns HTTP 403 when a client tries to access another client's conversation. Stream `POST /chat/stream` returns HTTP 404 for the same condition. An API consumer handling 403 for permission issues silently gets 404 from the streaming endpoint.

## Fix

Make the stream endpoint return the same error code as the sync endpoint. Previous learnings (v1.5 P2 finding) say to use uniform 404 for both "not found" and "not authorized" to prevent enumeration. Apply the established pattern.
