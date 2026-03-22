---
status: pending
priority: p3
issue_id: 167
tags: [code-review, dry]
dependencies: []
---

# Backend get_client_id Dependency Duplicated Across 3 Route Modules

## Problem

The `get_client_id` function (returns X-Client-Id header or "anonymous") is defined identically in chat.py, policy_workspaces.py, and collections.py. Should be in `src/api/deps.py` alongside other FastAPI dependencies.

## Fix

Move to deps.py, import from all route modules.
