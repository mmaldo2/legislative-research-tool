---
status: complete
priority: p2
issue_id: "088"
tags: [code-review, api, performance]
dependencies: []
---

# Missing Pagination on List Endpoints

## Problem

GET /webhooks and GET /saved-searches return unbounded result sets with no pagination. Other list endpoints in the codebase use page/per_page params.

## Files

- src/api/webhooks.py:64-89
- src/api/saved_searches.py:65-91

## Solution

Add `page: int = 1` and `per_page: int = 50` query params with `.offset((page-1)*per_page).limit(per_page)`. Follow existing codebase pagination pattern.
