---
title: "feat: Demo Readiness — Streaming, Hardening, and Narrative"
type: feat
status: active
date: 2026-03-22
origin: docs/scopes/2026-03-22-demo-readiness-scope.md
---

# feat: Demo Readiness — Streaming, Hardening, and Narrative

## Overview

Transform the legislative research platform from a functional tool into a demo-ready
"Cursor for public policy" by adding real-time streaming to all LLM interactions,
hardening reliability for live presentations, closing P1 security items, restructuring
the narrative to lead with the composer/IDE story, and adding visual revision diffs.

## Problem Statement

The platform has strong capabilities (10-tool agentic chat, 7 LLM analyses, 0.9969 AUROC
prediction, precedent-driven drafting) but undercuts its demo impact in three ways:
1. Every LLM call blocks 15-30s with no incremental feedback — competitors stream tokens
2. Known bugs (ChatPanel state loss, BM25 cold start) surface under live conditions
3. The entry point tells a "research tool" story, not a "policy IDE" story

## Proposed Solution

Five workstreams executed in four phases:

1. **Streaming responses** — SSE for chat, compose, analyze, summarize
2. **Demo hardening** — ChatPanel fix, BM25 pre-warm, error recovery UI
3. **P1 security closure** — prompt injection sanitization, artifact integrity (verify/close)
4. **Demo narrative** — landing page redesign, demo seed data, demo script
5. **Visual revision diff** — inline diff component in composer

## Technical Approach

### Architecture Decisions

**AD1: SSE Event Schema** — Custom minimal format, consistent across all streaming endpoints:

```
event: token
data: {"text": "..."}

event: tool_status
data: {"tool": "search_bills", "status": "running", "description": "Searching for privacy bills..."}

event: error
data: {"message": "...", "retryable": true, "error_type": "rate_limit|server|timeout|content_policy"}

event: done
data: {"metadata": {...}}
```

Chat endpoints emit all four event types. Compose/analyze endpoints emit `token`, `error`,
and `done` (no tool_status). The `done` event carries the full structured response
(provenance, rationale, source_bill_ids) as JSON metadata.

**AD2: Structured Output Streaming** — For compose/analyze, the LLM produces structured
JSON (e.g., `PolicySectionDraftOutput`). Strategy: stream raw text tokens to the frontend
for real-time display. On `message_stop`, parse the accumulated text as JSON into the
Pydantic model. Emit the parsed structured result as the `done` event metadata. If parsing
fails, use the existing `fallback_fn`. The frontend shows streamed text during generation,
then swaps to the structured display on `done`.

**AD3: Cache Behavior During Streaming** — Check content-hash cache before streaming. On
cache hit, emit the result as a single `done` event with all content (no fake streaming).
Cache hits are instant — stakeholders will see some responses appear immediately and others
stream, which is natural and expected.

**AD4: BM25 Pre-warm Strategy** — Use FastAPI `lifespan` context manager. The index builds
during startup before the server accepts requests. Log progress so the demo presenter knows
when the app is ready. Startup delay is ~5-10s with 119K bills, acceptable for demo.

**AD5: Chat Panel State Preservation** — CSS display toggle (`display: none` vs `block`)
instead of conditional rendering. Component stays mounted, preserving all state. Also add
message history reload from `GET /conversations/{id}` for page refresh resilience.

**AD6: Revision Diff Strategy** — Client-side word-level diff using `diff-match-patch`
library. Compare revision N against revision N-1. Inline rendering with green highlights
for additions, red strikethrough for deletions.

### Implementation Phases

#### Phase 0: Merge and Housekeeping [3 tasks]

Prerequisite: land v1.5 and close stale todos before starting new work.

- [x] **0.1** Merge `feat/composer-v1.5-ide-integration` to `main`
- [x] **0.2** Close todos #119 and #120 (code already fixed, verify and update status)
- [x] **0.3** Create new feature branch `feat/demo-readiness` from `main`

**Files:**
- `todos/119-pending-p1-feature-parity-risk.md` — update status to resolved
- `todos/120-pending-p1-pickle-integrity-verification.md` — update status to resolved
- `todos/_active.md` — update counts

**Acceptance criteria:**
- v1.5 merged to main, branch deleted
- Both todos verified fixed and marked resolved
- New branch created from clean main

---

#### Phase 1: Streaming Infrastructure [6 tasks]

Build the SSE plumbing bottom-up: harness -> services -> API -> frontend.

- [x] **1.1** Add `sse-starlette` to `pyproject.toml` dependencies

- [x] **1.2** Add `_run_analysis_stream()` to `LLMHarness` (`src/llm/harness.py`)
  - Parallel method to `_run_analysis()` that yields SSE-formatted events
  - Uses `client.messages.stream()` (Anthropic SDK native streaming)
  - Yields `token` events as `RawContentBlockDelta` arrives
  - On `message_stop`, parses accumulated text into Pydantic `output_type`
  - Yields `done` event with full structured result as metadata
  - On parse failure, calls `fallback_fn` and yields `done` with fallback
  - Extracts usage data from final event for cost tracking
  - Does NOT check content-hash cache (caller decides whether to stream or return cached)
  - Async generator: `async def _run_analysis_stream(...) -> AsyncGenerator[str, None]`

- [x] **1.3** Add streaming variants to harness public methods
  - `stream_draft_policy_section()`, `stream_rewrite_policy_section()`
  - `stream_analyze_draft_constitutional()`, `stream_analyze_draft_patterns()`
  - `stream_summarize()`, `stream_classify()`
  - Each checks cache first — on hit, yields single `done` event; on miss, delegates to `_run_analysis_stream()`
  - Same load-call-persist pattern: caller provides pre-loaded data, no DB during stream

- [x] **1.4** Add `stream_agentic_chat()` to `ChatService` (`src/services/chat_service.py`)
  - Async generator variant of `run_agentic_chat()`
  - Tool-use rounds remain non-streaming (internal, fast)
  - Yields `tool_status` events when entering/exiting each tool call
  - Final response round uses `client.messages.stream()` and yields `token` events
  - Yields `done` event with final message text and conversation metadata
  - load-call-persist: load conversation + history before entering generator; persist after generator exhausted (caller responsibility)

- [x] **1.5** Add SSE endpoints to API layer
  - `POST /chat/stream` in `src/api/chat.py`
    - Returns `EventSourceResponse` (from sse-starlette)
    - Load conversation -> yield from `stream_agentic_chat()` -> persist on completion
    - Same auth, rate limiting, org scoping as `/chat`
  - `POST /policy-workspaces/{id}/chat/stream` in `src/api/policy_workspaces.py`
    - Workspace-scoped variant, same pattern
  - `POST /policy-workspaces/{id}/sections/{sid}/compose/stream` in `src/api/policy_workspaces.py`
    - Streaming compose for draft/rewrite/analyze actions
    - Load section + precedents -> yield from streaming harness -> persist generation on completion
  - Keep all existing sync endpoints unchanged

- [x] **1.6** Build frontend SSE client and update components
  - Create `frontend/src/lib/sse.ts` — SSE event parser for `fetch()` with `ReadableStream`
    - `streamFetch(url, options)` -> async generator yielding typed events
    - Event types: `StreamTokenEvent`, `StreamToolStatusEvent`, `StreamErrorEvent`, `StreamDoneEvent`
    - Handle connection errors, timeouts, and partial reads
  - Update `ChatPanel` (`frontend/src/components/chat-panel.tsx`)
    - Add `useStreaming` mode that calls `/chat/stream` instead of `/chat`
    - Incrementally append tokens to current assistant message
    - Show tool-status events as ephemeral status indicators ("Searching bills...")
    - On `done` event, finalize message and update conversation state
  - Update composer compose/analyze UI (`frontend/src/app/composer/[id]/page.tsx`)
    - Add streaming mode for compose actions
    - Show streamed text in a preview area during generation
    - On `done`, switch to structured display with accept/reject controls

**Files (Phase 1):**
- `pyproject.toml` — add `sse-starlette` dependency
- `src/llm/harness.py` — add `_run_analysis_stream()`, streaming public methods
- `src/services/chat_service.py` — add `stream_agentic_chat()`
- `src/api/chat.py` — add `POST /chat/stream`
- `src/api/policy_workspaces.py` — add streaming compose and chat endpoints
- `frontend/src/lib/sse.ts` — new SSE client module
- `frontend/src/lib/api.ts` — add streaming API functions
- `frontend/src/components/chat-panel.tsx` — streaming message rendering
- `frontend/src/app/composer/[id]/page.tsx` — streaming compose UI

**Acceptance criteria:**
- Chat messages stream token-by-token in real-time
- Tool-use activity shows status indicators during agentic rounds
- Compose/analyze results stream, then display structured accept/reject on completion
- Cached results return instantly via single `done` event
- Existing sync endpoints continue to work unchanged
- Load-call-persist pattern maintained (no DB held during streaming)

---

#### Phase 2: Demo Hardening [5 tasks]

Fix reliability issues that would surface during a live presentation.

- [x] **2.1** Fix ChatPanel state loss on toggle (#149)
  - Change conditional rendering to CSS display toggle at `composer/[id]/page.tsx:712`
  - Before: `{researchOpen && (<ChatPanel .../>)}`
  - After: `<div style={{display: researchOpen ? 'block' : 'none'}}><ChatPanel .../></div>`
  - Add message history reload: on mount, if `conversationId` exists, fetch messages from `GET /conversations/{id}` and populate `messages` state

- [x] **2.2** Add BM25 pre-warm via FastAPI lifespan event
  - Add `lifespan` async context manager to `src/api/app.py`
  - On startup: create a DB session, call `rebuild_bm25_index(session)`, log completion time
  - Use `asyncio.create_task()` so the server starts accepting requests after index is built
  - Add startup log: `"BM25 index built: {count} bills in {elapsed:.1f}s"`
  - Fallback: if build fails (no bills, DB down), log warning and continue — search degrades to semantic-only
  - Make pre-warm conditional on `PREWARM_BM25` env var (skip in CI/test)

- [x] **2.3** Add error recovery UI to frontend
  - Add retry button to `ChatPanel` error state
    - On error, show message with "Retry" button that re-sends the last user message
    - Distinguish retryable vs. non-retryable errors using `error_type` from SSE `error` event
  - Add retry to compose/analyze error states in composer
    - On failure, show error inline with "Retry" button
    - Preserve the compose instruction so user doesn't need to retype
  - Add toast notifications for transient errors (rate limit with auto-retry countdown)

- [x] **2.4** Add error type propagation to backend
  - Catch specific Anthropic SDK exceptions in harness streaming methods:
    - `anthropic.RateLimitError` -> `error_type: "rate_limit"`, retryable
    - `anthropic.APIStatusError` (5xx) -> `error_type: "server"`, retryable
    - `anthropic.APIConnectionError` -> `error_type: "timeout"`, retryable
    - `anthropic.BadRequestError` (content policy) -> `error_type: "content_policy"`, not retryable
  - Emit SSE `error` event with type classification
  - For sync endpoints, add `error_type` field to error response bodies

- [x] **2.5** Handle in-flight streaming on component unmount
  - In `ChatPanel`, use `AbortController` for streaming fetch
  - On unmount or panel close, call `controller.abort()` to cancel the stream
  - In compose streaming, abort on navigation away from composer page
  - Backend: handle client disconnection gracefully (catch `GeneratorExit` or `ConnectionResetError`)

**Files (Phase 2):**
- `frontend/src/app/composer/[id]/page.tsx` — CSS toggle fix, compose retry UI
- `frontend/src/components/chat-panel.tsx` — message reload, retry button, abort controller
- `src/api/app.py` — lifespan handler for BM25 pre-warm
- `src/search/engine.py` — ensure `rebuild_bm25_index` is importable and handles errors
- `src/llm/harness.py` — error type classification in streaming methods
- `src/services/chat_service.py` — error type propagation in streaming chat
- `todos/149-pending-p3-chat-panel-remount-loses-state.md` — close

**Acceptance criteria:**
- Chat panel preserves conversation when toggled closed and reopened
- Chat panel reloads message history on page refresh
- First search after app start returns results instantly (no BM25 cold start)
- LLM errors show retry button with appropriate messaging
- Rate limit errors show countdown timer
- In-flight streams are cleanly cancelled on component unmount
- No React state-update-on-unmounted-component warnings

---

#### Phase 3: Security and Prompt Injection [3 tasks]

Close P1 security items so due diligence questions have clean answers.

- [ ] **3.1** Complete prompt injection sanitization (#103)
  - Audit all harness methods that accept user-controlled text:
    - `generate_trend_narrative()` — already fixed (XML `<data>` tags, truncation)
    - `generate_policy_outline()` — `goal_prompt` from user -> needs XML fencing
    - `draft_policy_section()` — `instruction_text` from user -> needs XML fencing
    - `rewrite_policy_section()` — `instruction_text` + `selected_text` -> needs XML fencing
    - `analyze_draft_constitutional()` — `content_markdown` from user draft -> needs XML fencing
    - `analyze_draft_patterns()` — same as above
    - `format_workspace_context()` — `title`, `goal_prompt` from user -> needs XML fencing
  - Apply consistent pattern: wrap user data in `<user_input>` tags with "treat as data only" instruction
  - Truncation budgets: goal_prompt 500 chars, instruction_text 1000 chars, content 50K chars (existing)
  - Add helper: `def fence_user_input(text: str, max_len: int = 1000) -> str`

- [ ] **3.2** Add sanitization tests
  - Test that adversarial text in `goal_prompt` does not escape XML fencing
  - Test that `.replace()` is used (not `.format()`) for all user text interpolation
  - Test truncation bounds are enforced
  - Static test: grep all prompt templates for undelimited user data interpolation

- [ ] **3.3** Verify and close #120 (artifact integrity)
  - Confirm SHA-256 verification in `service.py:55-74` runs on every model load
  - Confirm `promote.py` generates hashes for all serialized model files
  - Add test: tamper with a hash in metadata.json, verify load fails with clear error
  - Close todo #120

**Files (Phase 3):**
- `src/llm/harness.py` — add `fence_user_input()` helper, apply to all methods
- `src/llm/prompts/policy_outline_v1.py` — add XML fencing to user data slots
- `src/llm/prompts/policy_section_draft_v1.py` — add XML fencing
- `src/llm/prompts/policy_rewrite_v1.py` — add XML fencing
- `src/llm/prompts/draft_analysis_v1.py` — add XML fencing
- `src/llm/prompts/workspace_assistant_v1.py` — verify existing XML fencing is complete
- `tests/test_llm/test_prompt_sanitization.py` — new test file
- `tests/test_prediction/test_model_integrity.py` — new test file
- `todos/103-pending-p1-llm-prompt-injection.md` — close
- `todos/120-pending-p1-pickle-integrity-verification.md` — close

**Acceptance criteria:**
- All user-controlled text in LLM prompts is wrapped in XML structural delimiters
- Truncation enforced on all user inputs
- No `.format()` calls with user text in any prompt template
- Tests verify sanitization and truncation
- Model loading fails with clear error on hash mismatch
- Both P1 todos closed

---

#### Phase 4: Demo Narrative and Polish [5 tasks]

Reshape the user-facing story and add the revision diff feature.

- [ ] **4.1** Redesign landing page (`frontend/src/app/page.tsx`)
  - Change headline from "Legislative Research Tool" to emphasize IDE/drafting identity
  - Subtitle: "Draft model legislation grounded in real legislative data, AI analysis, and ML-powered predictions across 50 states and Congress"
  - Reorder feature cards: lead with Composer, then Research Assistant, then Prediction, then Search
  - Primary CTA: "Start Drafting" -> `/composer`
  - Secondary CTA: "Explore Research" -> `/search`
  - Add a visual element showing the composer workflow

- [ ] **4.2** Add visual revision diff to composer
  - Install `diff-match-patch` package in frontend
  - Create `frontend/src/components/revision-diff.tsx` component
    - Props: `oldText: string`, `newText: string`, `oldLabel: string`, `newLabel: string`
    - Renders inline word-level diff with green highlight for additions, red strikethrough for deletions
    - Show change source badges (AI vs. manual)
  - Integrate into composer section history display (`composer/[id]/page.tsx:960-998`)
    - When expanding history, show diff between adjacent revisions
    - First revision shows full content (nothing to diff against)
    - Add toggle: "Show changes" / "Show full text"

- [ ] **4.3** Create demo seed data script
  - Create `scripts/seed_demo.py`
  - Seeds a workspace with:
    - Title: "Model Data Privacy Act" (or similar compelling topic)
    - Target jurisdiction: a specific state
    - 3-4 precedent bills (real bills from the database — pick well-known privacy bills)
    - A generated outline (pre-computed, stored directly)
    - 2-3 drafted sections with 2+ revisions each (showing AI iteration)
    - A workspace conversation with a few research exchanges
  - Idempotent: skip if demo workspace already exists
  - Run with: `python scripts/seed_demo.py`

- [ ] **4.4** Write demo walkthrough script
  - Create `docs/demo-walkthrough.md`
  - 10-minute structured flow:
    1. Landing page -> "This is the policy IDE" (30s)
    2. Open demo workspace -> show precedent insights with ML predictions (1m)
    3. Generate outline from precedents -> watch outline stream in (1m)
    4. Compose a section -> watch draft stream with real-time tokens (2m)
    5. Analyze draft constitutionally -> show concerns stream in (1m)
    6. Open research assistant -> ask a cross-jurisdictional question -> see tool activity (2m)
    7. Apply suggestion from assistant to compose form (30s)
    8. Show revision diff -> "see what the AI changed" (1m)
    9. Search bills -> show hybrid search + bill detail with prediction (1m)
  - Include fallback talking points for each step if something fails
  - Note which demo data must exist (references seed script)

- [ ] **4.5** Final integration testing and cleanup
  - Run full demo walkthrough 3 times end-to-end
  - Fix any issues discovered during dry runs
  - Verify all streaming endpoints work with cold start
  - Verify error recovery works (intentionally cause failures)
  - Clean up any dead code from the streaming refactor

**Files (Phase 4):**
- `frontend/src/app/page.tsx` — landing page redesign
- `frontend/src/components/revision-diff.tsx` — new diff component
- `frontend/src/app/composer/[id]/page.tsx` — integrate diff into history
- `frontend/package.json` — add `diff-match-patch` dependency
- `scripts/seed_demo.py` — new demo data script
- `docs/demo-walkthrough.md` — new demo script

**Acceptance criteria:**
- Landing page communicates "policy IDE" in first 5 seconds
- Revision diffs show visual additions/deletions between versions
- Demo seed script creates a complete, compelling workspace in one command
- Demo walkthrough is executable end-to-end in 10 minutes
- All streaming interactions work without failures in 3 consecutive dry runs

## System-Wide Impact

### Interaction Graph

Streaming changes touch the full vertical stack:

```
Frontend (ChatPanel, Composer) -> SSE client (new) -> fetch ReadableStream
    |
FastAPI SSE endpoints (new) -> EventSourceResponse
    |
Service layer (chat_service, composer_service) -> async generators
    |
LLM Harness -> Anthropic SDK client.messages.stream()
    |
Anthropic API -> RawMessageStreamEvent deltas
```

Each layer yields events upward. DB sessions are acquired only in load and persist phases,
never held during the streaming phase.

### Error Propagation

```
Anthropic SDK -> RateLimitError / APIStatusError / APIConnectionError / BadRequestError
    | caught in harness._run_analysis_stream()
SSE error event -> {"error_type": "rate_limit|server|timeout|content_policy", "retryable": bool}
    | emitted via EventSourceResponse
Frontend SSE parser -> StreamErrorEvent
    | handled in ChatPanel / Composer
UI -> retry button (retryable) or error message (non-retryable)
```

Client disconnection propagates backward: `AbortController.abort()` -> fetch cancelled ->
FastAPI detects client disconnect -> generator cleanup via `GeneratorExit`.

### State Lifecycle Risks

- **Partial generation on stream failure**: If the LLM connection drops mid-stream, the
  harness yields an `error` event but no `done`. The compose endpoint must NOT persist a
  `PolicyGeneration` record for incomplete content. Only persist on successful `done`.
- **Conversation message on stream failure**: The user message is persisted before streaming
  starts (load phase). If streaming fails, the assistant message is never persisted. This
  leaves an orphaned user message without a response. Acceptable — the conversation shows
  the user's question, and retry creates the response.
- **BM25 pre-warm failure**: If the index fails to build on startup, search degrades to
  semantic-only (vector search). The app still starts and functions.

### API Surface Parity

New streaming endpoints mirror existing sync endpoints:

| Sync Endpoint | Streaming Endpoint | Notes |
|---|---|---|
| `POST /chat` | `POST /chat/stream` | Same auth, rate limits |
| `POST /policy-workspaces/{id}/chat` | `POST /policy-workspaces/{id}/chat/stream` | Same auth, workspace scoping |
| `POST .../sections/{sid}/compose` | `POST .../sections/{sid}/compose/stream` | Same auth, action types |

All sync endpoints remain unchanged. Frontend switches to streaming endpoints.

## Acceptance Criteria

### Functional Requirements

- [ ] All LLM interactions (chat, compose, analyze) stream tokens in real-time
- [ ] Tool-use activity visible during agentic chat rounds
- [ ] Cached results return instantly without streaming delay
- [ ] Chat panel preserves state across toggle and page refresh
- [ ] First search after cold start returns results instantly
- [ ] LLM errors show typed recovery UI (retry for retryable, message for non-retryable)
- [ ] All user-controlled text in LLM prompts has XML structural delimiters
- [ ] Model artifact loading verifies SHA-256 integrity
- [ ] Landing page communicates "policy IDE" identity
- [ ] Revision diffs show visual additions/deletions
- [ ] Demo seed script creates a compelling workspace in one command
- [ ] Demo walkthrough executes end-to-end in 10 minutes

### Non-Functional Requirements

- [ ] No DB connections held during streaming (load-call-persist maintained)
- [ ] Streaming adds <50ms latency to time-to-first-token vs. direct SDK streaming
- [ ] Client disconnection cleans up server resources (no leaked generators)
- [ ] BM25 pre-warm completes in <15s for 119K bills

### Quality Gates

- [ ] All existing tests pass (no regressions from streaming additions)
- [ ] New tests for: SSE event format, error type classification, prompt sanitization, model integrity
- [ ] `ruff check` and `ruff format` pass
- [ ] `next build` succeeds with no TypeScript errors
- [ ] Demo walkthrough succeeds 3 consecutive times

## Dependencies & Prerequisites

- v1.5 branch merged to main (Phase 0)
- `sse-starlette` Python package
- `diff-match-patch` npm package
- Anthropic SDK >=0.43.0 (already satisfied per pyproject.toml)
- Demo requires bills in database (backfill must have run)

## Risk Analysis & Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| Streaming adds complexity to test/debug | Medium | Keep sync endpoints as fallback; streaming is additive |
| Anthropic SDK streaming API changes | Low | Pin SDK version; streaming API is stable |
| BM25 pre-warm slows startup in CI/test | Medium | Make pre-warm conditional on `PREWARM_BM25=true` env var |
| Demo seed data depends on specific bills | Medium | Script queries for real bills by topic; fallback to any bills if specific ones missing |
| Partial streaming on connection issues | Medium | Never persist incomplete generations; UI shows partial text with error indicator |

## Sources & References

### Origin

- **Scope document:** [docs/scopes/2026-03-22-demo-readiness-scope.md](../scopes/2026-03-22-demo-readiness-scope.md)
- Key decisions carried forward: streaming strategy, selective expand on revision diff, defer base model/OAuth/rich editor

### Internal References

- v1.5 architecture patterns: `docs/solutions/architecture/composer-v1.5-ide-integration.md`
- Load-call-persist pattern: `docs/solutions/architecture/composer-v1.5-ide-integration.md:45-54`
- Anti-patterns table: `docs/solutions/architecture/composer-v1.5-ide-integration.md:76-120`
- LLM harness entry point: `src/llm/harness.py:140` (`_run_analysis`)
- Agentic chat loop: `src/services/chat_service.py:84-186` (`run_agentic_chat`)
- Chat endpoint: `src/api/chat.py:437-535`
- Compose endpoint: `src/api/policy_workspaces.py:475-506`
- ChatPanel conditional render: `frontend/src/app/composer/[id]/page.tsx:712`
- BM25 lazy init: `src/search/engine.py:44-51`
- Revision model: `src/models/policy_workspace.py:144-163`
- Landing page: `frontend/src/app/page.tsx`

### Related Work

- Todo #103: prompt injection sanitization
- Todo #119: feature parity (already fixed in code)
- Todo #120: artifact integrity (already fixed in code)
- Todo #149: ChatPanel state loss
