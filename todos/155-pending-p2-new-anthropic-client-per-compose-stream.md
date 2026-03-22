---
status: pending
priority: p2
issue_id: 155
tags: [code-review, architecture, streaming, performance]
dependencies: []
---

# New Anthropic Client Per Compose Stream Bypasses DI Singleton

## Problem

`stream_compose_section()` creates `anthropic.AsyncAnthropic()` on every call instead of using the shared singleton from `get_anthropic_client()`. Creates fresh HTTP connection pools, ~200ms latency penalty, potential file descriptor exhaustion under load, and bypasses `settings.anthropic_api_key`.

## Fix

Accept the client as a parameter, inject from the API layer.
