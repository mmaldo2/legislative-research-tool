---
title: "feat: Composer v1.5 — IDE Integration (Research + Drafting Convergence)"
type: feat
status: active
date: 2026-03-21
origin: docs/scopes/2026-03-21-composer-v1.5-ide-integration-scope.md
---

# feat: Composer v1.5 — IDE Integration

## Overview

Connect the existing 10-tool research assistant into the policy workspace composer, add draft-aware analysis, and surface ML prediction data for precedent bills. This transforms the composer from a standalone drafting tool into an integrated drafting environment — the core "Cursor for public policy" differentiator.

## Problem Statement

The platform has strong research capabilities (10-tool agentic assistant, 7 LLM analyses, ML prediction at 0.9969 AUROC) and a functional composer (workspace → outline → section drafting → export), but they exist on separate pages. A policy analyst must leave the workspace to research, then manually bring findings back. This gap is what separates "AI text editor" from "integrated drafting environment."

## Proposed Solution

Four phases: stability fixes, workspace chat backend, frontend assistant panel, and draft analysis + insight cards.

## Technical Approach

### Architecture

The integration reuses existing infrastructure with minimal new code:

- **Chat backend** (`src/api/chat.py`): The 753-line agentic loop with 10 tools and conversation persistence is reused entirely. A new workspace-scoped endpoint injects workspace context into the system prompt.
- **LLM harness** (`src/llm/harness.py`): Existing analysis methods already accept raw text (`bill_text: str`). The chat tool handlers do the bill_id → text lookup. New draft-analysis methods follow the same pattern but accept workspace section text instead.
- **Composer service** (`src/services/policy_composer_service.py`): `_format_precedent_context()` and `_other_sections_summary()` already format workspace state for LLM consumption. These are reused for system prompt assembly.
- **Frontend**: The assistant page (`assistant/page.tsx`, 147 lines) provides the chat UI pattern. The composer detail page (`composer/[id]/page.tsx`, ~920 lines) has a prototype "research panel" at lines 658-728 to replace.

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Conversation → workspace link | Nullable FK `workspace_id` on `Conversation` | Simplest; follows existing ownership pattern; lets workspaces have resumable conversations |
| Chat endpoint placement | `POST /policy-workspaces/{id}/chat` in `policy_workspaces.py` | Workspace-scoped; shares auth/ownership checks; avoids muddling general assistant |
| Context injection timing | Rebuild system prompt every turn | Workspace state changes between turns (accept generation, edit section); stale context would confuse the assistant |
| Context budget | ~8K tokens for workspace context | Goal + jurisdiction + precedent summaries (not full text) + section headings + active section draft; leaves room for 100K history budget |
| "Apply suggestion" UX | Prefill compose form, don't auto-create generation | User stays in control (R7 from brainstorm); no extra LLM call; one-click to trigger compose with the suggested text |
| Draft analysis storage | `PolicyGeneration` with `action_type="analyze_constitutional"` etc. | Reuses existing audit trail; consistent review/accept flow |
| Pending generation model | Per-section `Map<sectionId, PolicyGenerationResponse[]>` | Supports concurrent compose + assistant suggestions without collision |
| Precedent locking | Keep locked post-outline (Flow E deferred) | Assistant can reference any bill via search tools; formal precedent changes would invalidate provenance |
| Streaming | Defer to v2 | Request-response with 120s timeout + "thinking..." indicator is acceptable for demo |

### Implementation Phases

#### Phase 0: Stability Fixes [prerequisite]

Fix P2 #136 (connection pool starvation) across all LLM-calling code paths. Without this, concurrent compose + chat + analyze will crash demos.

**Tasks:**

- [x] **0.1** Refactor `policy_composer_service.py` — split `compose_section()` and `generate_outline_for_workspace()` into load → call → persist phases. Release the DB session before calling the LLM harness. Reacquire to persist results. (`src/services/policy_composer_service.py`)
- [x] **0.2** Refactor chat endpoint — the agentic loop in `src/api/chat.py:548-631` holds a session across all tool-use rounds. Split: load conversation + history → release session → run agentic loop (tools get fresh sessions per tool call) → reacquire session → persist messages. (`src/api/chat.py`)
- [x] **0.3** Change frontend pending generation state from singleton `useState<PolicyGenerationResponse | null>` to per-section map `useState<Record<string, PolicyGenerationResponse[]>>({})`. Update all handlers: `handleComposeSection`, `handleAcceptGeneration`, `handleRejectGeneration`. (`frontend/src/app/composer/[id]/page.tsx`)
- [x] **0.4** Run existing test suite to verify no regressions from session management changes. (`tests/test_api/test_policy_workspaces.py`)

**Acceptance criteria:**
- [ ] No DB session is held during any LLM API call (harness or Anthropic SDK)
- [ ] Multiple sections can have independent pending generations simultaneously
- [ ] All 18 existing composer tests pass

---

#### Phase 1: Workspace Chat Backend

Wire the existing chat agentic loop into workspace-scoped conversations.

**Tasks:**

- [x] **1.1** Add `workspace_id` column to `Conversation` model — nullable FK to `policy_workspaces.id`, `ondelete="SET NULL"`, indexed. Add `workspace` relationship with `back_populates`. (`src/models/conversation.py`)
- [x] **1.2** Create Alembic migration `011_add_conversation_workspace_id.py` — `ADD COLUMN workspace_id VARCHAR REFERENCES policy_workspaces(id) ON DELETE SET NULL`, `CREATE INDEX ix_conversations_workspace_id`. (`migrations/versions/011_add_conversation_workspace_id.py`)
- [x] **1.3** Create workspace assistant prompt — `src/llm/prompts/workspace_assistant_v1.py` exporting `PROMPT_VERSION`, `SYSTEM_PROMPT_TEMPLATE` (a string with `{workspace_context}` placeholder), and `format_workspace_context(workspace, sections, precedent_summaries)` helper that produces the context block. Context includes: title, target jurisdiction, drafting template, goal prompt, precedent bill summaries (identifier + title + AI summary, ~200 chars each), section outline (heading + status + first 500 chars of draft per section), and instructions for the assistant to reference sections by heading. Cap at 8K tokens total.
- [x] **1.4** Create workspace chat endpoint — `POST /api/v1/policy-workspaces/{workspace_id}/chat` in `src/api/policy_workspaces.py`. Steps: (a) verify workspace ownership via client_id, (b) load workspace with sections and precedents, (c) format workspace context via prompt helper, (d) load or create conversation scoped to workspace_id, (e) run the existing agentic loop from chat.py (extract into a shared function `run_agentic_chat()` in a new `src/services/chat_service.py`), (f) persist messages, (g) return `ChatResponse`.
- [x] **1.5** Extract shared chat logic — move the agentic loop, tool dispatch, and history trimming from `src/api/chat.py` into `src/services/chat_service.py` as `run_agentic_chat(system_prompt, messages, tools, db_factory)`. Both the general `/chat` endpoint and the workspace `/chat` endpoint call this. The general endpoint passes `research_assistant_v1.SYSTEM_PROMPT`; the workspace endpoint passes the formatted workspace prompt.
- [x] **1.6** Add workspace conversation list endpoint — `GET /api/v1/policy-workspaces/{workspace_id}/conversations` returns conversations scoped to this workspace. Reuse `ConversationResponse` schema. (`src/api/policy_workspaces.py`)
- [x] **1.7** Add Pydantic schemas — `WorkspaceChatRequest(message: str, conversation_id: str | None)` in `src/schemas/policy_workspace.py`. Reuse existing `ChatResponse` from `src/schemas/chat.py`.
- [ ] **1.8** Write tests — workspace chat creation, conversation scoped to workspace, conversation resumption, tool use within workspace context, workspace ownership enforcement. (`tests/test_api/test_policy_workspaces.py`)

**Acceptance criteria:**
- [ ] Sending a chat message with a workspace_id creates a conversation linked to that workspace
- [ ] The assistant's system prompt includes workspace title, jurisdiction, precedent summaries, and section headings
- [ ] All 10 research tools work within the workspace chat
- [ ] Conversation persists and can be resumed across page reloads
- [ ] Different workspaces have separate conversations
- [ ] Workspace owner cannot access another client's workspace conversations

---

#### Phase 2: Frontend — Assistant Panel

Embed the chat interface in the composer detail page as a collapsible side panel.

**Tasks:**

- [ ] **2.1** Extract reusable `ChatPanel` component — from the existing assistant page pattern (`frontend/src/app/assistant/page.tsx`). Props: `workspaceId?: string`, `className?: string`. Manages its own state: messages, input, loading, conversationId. Calls workspace chat endpoint when `workspaceId` is provided, general chat endpoint otherwise. Displays tool calls as collapsible badges. Auto-scrolls. (`frontend/src/components/chat-panel.tsx`)
- [ ] **2.2** Add workspace chat API functions — `sendWorkspaceChatMessage(workspaceId, message, conversationId?)`, `listWorkspaceConversations(workspaceId)` in `frontend/src/lib/api.ts`. Follow existing patterns with `clientHeaders()`.
- [ ] **2.3** Add TypeScript types — `WorkspaceChatRequest` in `frontend/src/types/api.ts`. Reuse existing `ChatResponse`, `ChatMessageResponse` types.
- [ ] **2.4** Integrate `ChatPanel` into composer detail page — replace the collapsible "Research" card (lines 658-728) with a collapsible assistant panel. Use a two-column layout when panel is open: main content (sections editor) takes `col-span-2`, assistant panel takes `col-span-1`. When collapsed, main content takes full width. Toggle button in the composer toolbar with a `MessageSquare` icon. (`frontend/src/app/composer/[id]/page.tsx`)
- [ ] **2.5** Add "Apply to compose" action — when the assistant's response contains a suggestion (detected by a `> Suggested language:` markdown blockquote pattern or similar convention), show an "Apply to Section" button below the message. Clicking it: (a) opens a dropdown to select which section to target, (b) prefills the compose form with `action_type: "rewrite_selection"`, `instruction_text: "<suggestion text>"`, `selected_text: "<current section content>"`. The user reviews and clicks "Compose" to trigger the normal compose flow. (`frontend/src/components/chat-panel.tsx`, `frontend/src/app/composer/[id]/page.tsx`)
- [ ] **2.6** Load existing conversation on page mount — if the workspace has an existing conversation, load it into the chat panel so the user can continue where they left off. (`frontend/src/app/composer/[id]/page.tsx`)

**Acceptance criteria:**
- [ ] Chat panel opens/closes without disrupting the section editor layout
- [ ] Messages persist across page navigation (conversation is resumable)
- [ ] All 10 research tools display their results inline in the chat
- [ ] "Apply to Section" prefills the compose form with assistant-suggested text
- [ ] Panel is responsive — collapses to full-width on mobile

---

#### Phase 3: Draft-Aware Analysis

Add "analyze my draft" actions that run existing analysis prompts against user-authored section text.

**Tasks:**

- [ ] **3.1** Add new compose action types — expand `COMPOSE_ACTION_TYPES` in `src/schemas/policy_workspace.py` to include `"analyze_constitutional"` and `"analyze_patterns"`. These are analysis actions, not drafting actions, but they use the same compose → review → accept flow.
- [ ] **3.2** Add draft analysis prompt — `src/llm/prompts/draft_analysis_v1.py` with two variants: constitutional analysis of draft text, and pattern detection (comparing draft against precedent bills). Follow existing prompt convention: `PROMPT_VERSION`, `SYSTEM_PROMPT`, `USER_PROMPT_TEMPLATE`.
- [ ] **3.3** Add harness methods — `analyze_draft_constitutional(draft_text, section_heading, workspace_goal, jurisdiction)` and `analyze_draft_patterns(draft_text, section_heading, precedent_context)` in `src/llm/harness.py`. Use `skip_store=True`. Cache key: `f"draft:{hash(draft_text)}:{analysis_type}"`. Return existing `ConstitutionalAnalysisOutput` and `PatternDetectionOutput` schemas.
- [ ] **3.4** Add service method — `analyze_draft_section(db, workspace, section_id, action_type)` in `src/services/policy_composer_service.py`. Loads section content, calls appropriate harness method, persists result as `PolicyGeneration` with `action_type="analyze_constitutional"` or `"analyze_patterns"`, `output_payload` containing the analysis JSON. Follows load → call → persist pattern (no session held during LLM call).
- [ ] **3.5** Wire into compose endpoint — the existing `POST /policy-workspaces/{id}/sections/{section_id}/compose` endpoint already dispatches by `action_type`. Add cases for `"analyze_constitutional"` and `"analyze_patterns"` that call the new service method. (`src/api/policy_workspaces.py`)
- [ ] **3.6** Frontend: "Analyze" dropdown per section — alongside the existing "Compose" dropdown, add an "Analyze" dropdown with options "Constitutional Analysis" and "Pattern Detection". Triggers the compose endpoint with the new action types. Results display in the pending generation panel with analysis-specific formatting (concerns list, risk level, etc. rendered from the structured output). (`frontend/src/app/composer/[id]/page.tsx`)
- [ ] **3.7** Write tests — analyze_constitutional action on draft text, analyze_patterns action, empty section text rejection, analysis result format validation. (`tests/test_api/test_policy_workspaces.py`)

**Acceptance criteria:**
- [ ] User can run constitutional analysis on any section with content
- [ ] User can run pattern detection on any section with content
- [ ] Analysis results display with structured formatting (concerns list, severity, risk level)
- [ ] Analysis is stored as a PolicyGeneration for audit trail
- [ ] Empty sections return a clear error ("No content to analyze")

---

#### Phase 4: Precedent Insight Cards + Polish

Surface ML prediction and AI summary data for each precedent bill in the workspace.

**Tasks:**

- [ ] **4.1** Add precedent insights endpoint — `GET /api/v1/policy-workspaces/{workspace_id}/precedent-insights` returns prediction probability + AI summary for each precedent bill. Calls `predict_bill()` from `src/prediction/service.py` and queries `ai_analyses` for existing summaries. Returns gracefully if prediction model isn't loaded or summary doesn't exist. (`src/api/policy_workspaces.py`)
- [ ] **4.2** Add response schema — `PrecedentInsightResponse(bill_id, identifier, title, jurisdiction, prediction_probability: float | None, prediction_factors: list | None, ai_summary: str | None)` in `src/schemas/policy_workspace.py`.
- [ ] **4.3** Frontend: insight cards — in the precedent list section of the composer, show expanded cards for each precedent with: (a) prediction probability as a colored bar (green > 0.7, yellow 0.3-0.7, red < 0.3), (b) top 3 prediction factors, (c) AI summary excerpt (truncated to 200 chars with expand). Lazy-load via the batch endpoint on workspace detail mount. (`frontend/src/app/composer/[id]/page.tsx`)
- [ ] **4.4** Add API function — `getPrecedentInsights(workspaceId)` in `frontend/src/lib/api.ts`.
- [ ] **4.5** Add TypeScript type — `PrecedentInsightResponse` in `frontend/src/types/api.ts`.
- [ ] **4.6** Polish: loading states — skeleton loaders for: chat panel message streaming, insight cards loading, draft analysis in progress. (`frontend/src/app/composer/[id]/page.tsx`)
- [ ] **4.7** Polish: error handling — assistant panel shows error banners for rate limits and API failures without crashing the composer. Analysis failures show inline error per section. Insight card failures show "Prediction unavailable" gracefully.
- [ ] **4.8** Write tests — precedent insights endpoint, missing prediction graceful fallback, missing summary graceful fallback. (`tests/test_api/test_policy_workspaces.py`)

**Acceptance criteria:**
- [ ] Each precedent bill shows its committee passage probability when available
- [ ] Prediction factors are displayed as a concise list
- [ ] AI summary is shown with expand/collapse
- [ ] Missing predictions or summaries degrade gracefully (no errors)
- [ ] Loading states are visible for all async operations

## System-Wide Impact

### Interaction Graph

- Chat message → workspace context load → agentic loop (up to 10 tool rounds, each may query DB) → message persistence
- Compose action → load workspace/section → LLM harness call → persist generation
- Accept generation → load generation → create revision → update section → link accepted_revision_id
- **New interaction**: Chat message can reference compose actions via "Apply to Section" — this crosses the chat → compose boundary but the user manually bridges it (prefill + click), so no automated cascade

### Error & Failure Propagation

- LLM API timeout in workspace chat → caught in agentic loop → return partial response with "I encountered an error" message → no state corruption (messages up to that point already persisted per-round)
- Prediction service failure for insight cards → `predict_bill()` returns None → frontend shows "Prediction unavailable" → no blocking effect on other features
- DB session acquisition failure after load-call-persist split → retry with fresh session → if still failing, return 503

### State Lifecycle Risks

- **Conversation messages during agentic loop**: Currently messages are only persisted after the full loop completes. If the loop crashes mid-way, all messages (including successful tool results) are lost. Consider persisting after each tool round. (P3 — acceptable for demo)
- **Draft analysis generation with stale section content**: User could edit a section while analysis is in-flight. The generation records the content at analysis time, so accepting it would be a no-op (analysis text, not draft text). This is correct behavior — the analysis reflects the content at the time it was run.

### API Surface Parity

- The workspace chat endpoint reuses the same tool dispatch as the general chat. No parity gap.
- Draft analysis actions flow through the same compose endpoint. No new endpoint surface for analysis actions specifically.
- Precedent insights is the only genuinely new endpoint shape.

## Acceptance Criteria

### Functional Requirements

- [ ] Assistant panel in composer with workspace-aware research conversation
- [ ] All 10 existing research tools functional within workspace chat
- [ ] Conversations persist per-workspace and resume across sessions
- [ ] "Apply to Section" flow from assistant suggestions to compose form
- [ ] "Analyze my draft" for constitutional and pattern-detection analysis
- [ ] Analysis results displayed inline with structured formatting
- [ ] Precedent insight cards with ML prediction + AI summary
- [ ] Graceful degradation when prediction/summary data unavailable

### Non-Functional Requirements

- [ ] No DB session held during LLM API calls (Phase 0 fix verified)
- [ ] Workspace context injection stays under 8K tokens
- [ ] Chat panel responsive — works on mobile as full-width
- [ ] All new endpoints enforce workspace ownership via client_id

### Quality Gates

- [ ] All existing 18 composer tests pass after Phase 0
- [ ] New tests for workspace chat, draft analysis, precedent insights
- [ ] `ruff check` and `ruff format` pass
- [ ] `next build` succeeds with no TypeScript errors

## Dependencies & Prerequisites

- **P2 #136 (connection pool starvation)**: Must be fixed in Phase 0 before any other phase begins
- **Prediction service**: Must be loaded and functional for Phase 4 insight cards; graceful fallback if not
- **Existing chat infrastructure**: The `run_agentic_chat` extraction in Phase 1 is the riskiest refactor — it touches the 753-line chat.py which also serves the standalone assistant

## Risk Analysis & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Chat service extraction breaks existing assistant | Medium | High | Write tests for existing assistant before refactoring; both endpoints call the same extracted function |
| Workspace context exceeds token budget with many precedents/sections | Low | Medium | Cap at 5 precedent summaries + 10 section headings in system prompt; truncate draft content |
| "Apply to Section" UX feels clunky (manual compose form) | Medium | Low | This is the minimal viable version; v2 can auto-create generations directly |
| Concurrent chat + compose causes race on pending generations | Low | Medium | Per-section generation map (Phase 0.3) isolates state; no shared mutation |

## Future Considerations

These are explicitly deferred but inform current decisions:

- **Streaming (v2)**: The workspace chat endpoint should return `ChatResponse` now but the service function signature should accept an optional `on_chunk` callback for future SSE/WebSocket support
- **Rich editor (v2)**: The per-section generation map is compatible with a block-based editor where each block can have independent pending state
- **Multi-model (v2)**: The workspace prompt template should not hardcode Claude-specific instructions; keep the system prompt model-agnostic
- **Full assistant panel (v2)**: Current "Apply to Section" is a lightweight bridge; v2 could have the assistant directly create generations via tool_use

## Sources & References

### Origin

- **Scope document**: [docs/scopes/2026-03-21-composer-v1.5-ide-integration-scope.md](docs/scopes/2026-03-21-composer-v1.5-ide-integration-scope.md) — approved selective-expand scope
- **v1 brainstorm**: [docs/brainstorms/2026-03-20-policy-workspace-composer-requirements.md](docs/brainstorms/2026-03-20-policy-workspace-composer-requirements.md) — R7 (bounded agent actions) is the requirement this plan fulfills

### Internal References

- Chat agentic loop: `src/api/chat.py:548-631`
- Tool definitions: `src/llm/tools.py:1-246`
- Research assistant prompt: `src/llm/prompts/research_assistant_v1.py`
- Composer service context formatting: `src/services/policy_composer_service.py:97-119`
- Prediction service: `src/prediction/service.py:150-230`
- Frontend composer research panel: `frontend/src/app/composer/[id]/page.tsx:658-728`
- Frontend assistant page pattern: `frontend/src/app/assistant/page.tsx`

### Architecture Learnings (from v1)

- **Connection pool starvation**: `docs/solutions/architecture/policy-workspace-composer-v1.md` lines 91, 104 — split load-call-persist; never hold session during LLM calls
- **Cascade ownership**: Same doc lines 61, 88-89 — decide ORM vs DB cascade at one level, not both
- **FK constraints**: Same doc lines 89-90 — every `_id` column gets a ForeignKey
- **Thin endpoints**: `docs/solutions/architecture/p2-refactor-findings-resolution.md` — endpoints < 15 lines, business logic in services

### Pending Todos Addressed

- `todos/136-pending-p2-db-connection-held-during-llm-calls.md` — Fixed in Phase 0
- `todos/137-pending-p2-unbounded-generations-load.md` — Mitigated by per-section map; full fix deferred
- `todos/140-pending-p2-toctou-race-on-double-accept.md` — Risk increases with concurrent sources; noted for v2
