---
title: "Remaining Work Bundles — Post Demo Readiness"
type: feat
status: active
date: 2026-03-22
---

# Remaining Work Bundles

Organized by impact priority. Each bundle is a logical unit of work
that can be executed in a single `/ce:work` session.

## Bundle 1: Composer UX Overhaul (highest user-facing impact)

Transform the composer from functional to impressive. This is where the
"Cursor for public policy" vision becomes tangible.

- [ ] **1.1** Structured compose output — replace raw JSON with cards showing
  revised text, revision notes, and accept/reject controls
- [ ] **1.2** Wire streaming compose in frontend — connect `streamCompose()`
  so tokens flow during drafting (backend endpoint exists)
- [ ] **1.3** Token render batching (#163) — `requestAnimationFrame` to prevent
  jank during streaming
- [ ] **1.4** Inline diff on compose — show what changed between current section
  and the compose result before accepting

**Files:** `frontend/src/app/composer/[id]/page.tsx`, `frontend/src/lib/sse.ts`,
`frontend/src/components/revision-diff.tsx`

## Bundle 2: Streaming Architecture Cleanup (maintainability)

DRY up the streaming infrastructure before it calcifies.

- [ ] **2.1** Extract `_sse_event` to `src/utils/sse.py` (#161)
- [ ] **2.2** Generators yield structured tuples, format SSE at HTTP boundary (#156)
- [ ] **2.3** Extract conversation load/persist helpers (#161) — dedup sync/stream
- [ ] **2.4** Reduce harness duplication (#162) — extract `_build_analysis_config()`
- [ ] **2.5** Remove `_cached_or_stream` YAGNI (#165)

**Files:** `src/llm/harness.py`, `src/services/chat_service.py`,
`src/services/policy_composer_service.py`, `src/api/chat.py`,
`src/api/policy_workspaces.py`

## Bundle 3: Reliability Hardening (demo stability)

Close gaps that could embarrass during a live presentation.

- [ ] **3.1** SSE connection timeouts (#153) — `ping=15`, `asyncio.timeout()`
- [ ] **3.2** Persistence in `finally` blocks (#158) — survive client disconnect
- [ ] **3.3** Streaming compose provenance (#159) — compute source attribution
- [ ] **3.4** Error-path done event (#166) — always exit loading state
- [ ] **3.5** Auth consistency (#167, #168) — shared `get_client_id`, uniform 404

**Files:** `src/api/chat.py`, `src/api/policy_workspaces.py`,
`src/services/policy_composer_service.py`, `src/api/deps.py`

## Bundle 4: Documentation & Testing (completeness)

Make the project presentable and verifiable.

- [ ] **4.1** Streaming endpoint tests (#164)
- [ ] **4.2** OpenAPI docs for streaming endpoints (#160)
- [ ] **4.3** Demo walkthrough dry-run (3 consecutive passes)
- [ ] **4.4** Update CLAUDE.md with Agent SDK adapter pattern

**Files:** `tests/`, `src/api/chat.py`, `src/api/policy_workspaces.py`,
`docs/demo-walkthrough.md`, `CLAUDE.md`
