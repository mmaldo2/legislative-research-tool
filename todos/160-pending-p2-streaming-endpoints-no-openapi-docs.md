---
status: pending
priority: p2
issue_id: 160
tags: [code-review, api-docs, streaming]
dependencies: []
---

# Streaming Endpoints Lack OpenAPI Response Documentation

## Problem

All three streaming endpoints have no `response_model` or `responses` parameter. FastAPI documents them as 200 OK with no body. Agents discovering the API via /openapi.json have zero info about SSE event types/shapes.

## Fix

Add `responses={200: {"description": "...", "content": {"text/event-stream": {}}}}` with event type documentation.
