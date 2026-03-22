---
status: pending
priority: p2
issue_id: 156
tags: [code-review, architecture, streaming]
dependencies: []
---

# Fragile SSE Event String Parsing in API Closures

## Problem

Event generator closures parse SSE strings with `'event: done' in event_str` (substring match) and `event_str.split("data: ", 1)`. If LLM output contains literal "event: done", parsing breaks. JSON parsing errors are uncaught, silently terminating the stream and skipping persistence.

## Fix

Change generators to yield structured tuples/dicts instead of pre-formatted SSE strings. Format SSE at the HTTP boundary only.
