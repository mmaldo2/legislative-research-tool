---
status: pending
priority: p2
issue_id: 161
tags: [code-review, architecture, dry]
dependencies: []
---

# _sse_event Duplicated 3x and Sync/Stream Load/Persist Logic Duplicated

## Problem

`_sse_event()` is defined identically in harness.py, chat_service.py, and policy_composer_service.py. Additionally, the sync and stream chat endpoints duplicate conversation load/create and persist logic entirely (~50 lines each).

## Fix

Extract `_sse_event` to `src/utils/sse.py`. Extract `_load_or_create_conversation()` and `_persist_assistant_message()` helpers shared by sync and stream endpoints.
