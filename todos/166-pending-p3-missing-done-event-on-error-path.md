---
status: pending
priority: p3
issue_id: 166
tags: [code-review, frontend, ux]
dependencies: []
---

# Missing Done Event on Error Path Leaves Frontend in Loading State

## Problem

If `stream_compose_section` receives an error event from the harness but no done event, the persist phase is skipped and no done event is ever yielded. The frontend stream ends without a done event, leaving the UI in a stuck "loading" state.

## Fix

Ensure the compose streaming function always yields a done event (even with an error flag) so the frontend can transition out of loading state.
