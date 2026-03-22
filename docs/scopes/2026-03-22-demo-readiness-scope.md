---
date: 2026-03-22
topic: Demo Readiness — Streaming, Hardening, and Narrative
scope-mode: selective-expand
status: approved
---

# Scope: Demo Readiness

## Problem
The platform has strong capabilities (research, drafting, prediction, chat) but presents them in a way that undercuts demo impact: LLM calls block for 15-30s with no feedback, known bugs surface under live conditions, and the entry point tells a "research tool" story rather than "policy IDE." These gaps are the difference between a stakeholder saying "interesting" and "I want in."

## In Scope
- **Streaming responses**: SSE streaming for all LLM interactions (chat, compose, analyze, summarize) — Anthropic SDK → FastAPI SSE → frontend incremental rendering
- **Demo hardening**: fix ChatPanel state loss (#149), pre-warm BM25 index on boot, fix prediction feature parity regex (#119), add retry/graceful-degradation UI for LLM failures
- **P1 security closure**: prompt injection sanitization (#103), model artifact integrity checksums (#120) — clean answers for due diligence
- **Demo narrative**: restructure landing page to lead with composer/IDE story; design a repeatable 10-minute demo flow that starts in the composer, not search
- **Selective expansion**: visual revision diff in composer — show what changed between section revisions (data exists in `policy_section_revisions`, just needs a UI diff view)

## Out of Scope
- Base model fine-tuning — no training data yet, Claude performs well, post-traction
- Multi-model routing / OAuth — "we use Claude" is a strength at this stage
- Rich editor framework (TipTap/Lexical) — textarea + compose/accept proves the concept
- Real authentication / user accounts — X-Client-Id sufficient for controlled demos
- Collaboration / multi-user — single-user demo is sufficient
- Word/PDF export — markdown demonstrates capability, format conversion trivial later
- Plugin/extension architecture — premature
- Remaining P2/P3 backlog — quality-of-life, not demo-blocking

## Key Constraints
- Anthropic SDK already supports `stream=True` — extend, don't abstract
- FastAPI SSE via `StreamingResponse` + `sse-starlette` — proven pattern
- Frontend chat panel already renders message-by-message — add token-level streaming
- Composer compose/analyze endpoints need parallel streaming variants (don't break existing sync endpoints)
- BM25 pre-warm must not block app startup — background task on first request or lifespan event
- v1.5 branch should be merged to main before starting this work

## Codebase Context
- `src/llm/harness.py` — all LLM calls route through here; add streaming variants alongside existing methods
- `src/api/chat.py` + `src/services/chat_service.py` — agentic loop already structured as message iterations; stream the final response
- `src/api/policy_workspaces.py` — compose/analyze endpoints; add SSE variants
- `frontend/src/components/chat-panel.tsx` — already handles incremental message display
- `src/search/bm25.py` — lazy-built singleton; add startup pre-warm hook
- `src/prediction/service.py` — fix `congress_number` extraction to use regex per #119

## Open Questions
- Should streaming compose results replace the existing sync endpoints, or coexist as `/compose/stream`?
- What's the right BM25 pre-warm strategy — lifespan startup event, or lazy with progress indicator?
- Should the demo landing page be a separate route (`/demo`) or replace the existing dashboard?
