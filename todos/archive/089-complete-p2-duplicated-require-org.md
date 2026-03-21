---
status: complete
priority: p2
issue_id: "089"
tags: [code-review, quality]
dependencies: []
---

# Duplicated _require_org() Helper

## Problem

`_require_org()` is copy-pasted identically in both webhooks.py and saved_searches.py. Should be in shared deps.

## Files

- src/api/webhooks.py:25-28
- src/api/saved_searches.py:26-30

## Solution

Move to src/api/deps.py alongside existing require_api_key and require_tier helpers. Import from there in both routers.
