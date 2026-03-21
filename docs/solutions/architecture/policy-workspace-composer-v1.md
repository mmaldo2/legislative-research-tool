---
title: "Policy Workspace Composer v1 — Write-Side Drafting Surface"
date: 2026-03-21
category: architecture
tags:
  - policy-workspace
  - composer
  - write-path
  - llm-structured-output
  - multi-phase-feature
  - fastapi
  - next-js
  - async-sqlalchemy
  - anthropic-sdk
components_affected:
  - src/api/policy_workspaces.py
  - src/models/policy_workspace.py
  - src/schemas/policy_workspace.py
  - src/services/policy_workspace_service.py
  - src/services/policy_composer_service.py
  - src/llm/prompts/policy_outline_v1.py
  - src/llm/harness.py
  - migrations/versions/010_add_policy_workspace_tables.py
  - frontend/src/app/composer/
  - frontend/src/lib/composer.ts
severity: feature
---

# Policy Workspace Composer v1

## Problem

The platform's entire surface area was read-side — search, analysis, and display of existing legislation — and needed its first write-side capability: a structured drafting workspace where users define policy goals, receive an LLM-generated outline grounded in legislative precedents, iteratively compose section prose via an accept/reject loop, and export the result as a formatted document.

The core architectural challenge was grafting a stateful, multi-step authoring workflow (workspace -> outline -> sections -> draft -> export) onto infrastructure built around stateless read queries, which required new ORM models with deep parent-child cascades, a two-service split between CRUD orchestration and LLM composition, and careful transaction management across async SQLAlchemy sessions.

## Solution

### 1. Platform Reuse Over Greenfield

The composer is a thin write-side layer on the existing 23-route, 25-model research platform. Every major subsystem is reused:

- **Ownership**: Same `X-Client-Id` header pattern from chat/collections. No new auth mechanism.
- **LLM Harness**: Three new methods (`generate_policy_outline`, `draft_policy_section`, `rewrite_policy_section`) added to the existing `LLMHarness` class, plugging into `_run_analysis` for caching, cost tracking, and structured output parsing. Uses `skip_store=True` since generations go to `policy_generations` instead of `ai_analyses`.
- **Bill Data**: Precedent context assembly reuses `Bill` model relationships, `extract_bill_text()`, and `texts_without_markup()`.
- **Prompt Versioning**: Each prompt follows the existing convention — module in `src/llm/prompts/` exporting `PROMPT_VERSION`, `SYSTEM_PROMPT`, `USER_PROMPT_TEMPLATE`.
- **API Layer**: Thin endpoints delegating to services, translating domain exceptions to HTTP codes. Rate limiting via existing `limiter`.

### 2. Structured Data Model (5 Tables)

The data model uses structured sections + append-only generations + revisions instead of a single document blob:

- **`policy_workspaces`**: Root entity with metadata (title, jurisdiction, template, status).
- **`policy_workspace_precedents`**: Join table to `bills` with explicit position ordering and unique constraint.
- **`policy_sections`**: Individual sections from outline generation with `section_key`, `position`, `content_markdown`, and workflow `status`.
- **`policy_generations`**: Append-only audit log of every LLM operation with `output_payload` (JSONB), `provenance`, and `accepted_revision_id`.
- **`policy_section_revisions`**: Accepted-content history with `change_source` (ai/user) and content snapshot.

**Why not a blob?** A single document would make it impossible to compose sections independently, track provenance per section, offer accept/reject per generation, or migrate to a block-based editor in v2.

**Cascade strategy**: Workspace children use `cascade="all, delete-orphan"`. `PolicySection.generations` uses `cascade="save-update, merge"` with `passive_deletes=True` and `ondelete="SET NULL"`, so deleting a section preserves the generation audit trail.

### 3. Approval Semantics — Compose, Pending, Accept

AI never directly mutates section content. The flow:

1. **Compose**: User triggers an action (draft, rewrite, tighten, harmonize). Service calls LLM, persists a `PolicyGeneration` with output in `output_payload`. Section `content_markdown` is NOT updated.
2. **Review**: Frontend displays pending generation alongside current content with provenance.
3. **Accept**: Atomically creates a `PolicySectionRevision`, links `accepted_revision_id`, copies content to section, advances status. Double-accept is blocked by checking `accepted_revision_id is not None`.

Rejected generations remain in the audit log. Users can trigger multiple compose actions and accept only the best result.

### 4. Scope Control

The scope document used "selective-expand" mode with exactly two controlled additions:
- **Markdown export** — promoted from optional to required (analysts need to get text out)
- **Search from composer** — one search action reusing existing search API (minimal assistant bridge)

Explicitly excluded: rich editor framework, multi-model routing, full assistant panel, collaboration, plugin architecture. These are acknowledged as v2 concerns.

## Code Review Findings

Two rounds of automated review (5 agents, then 3 agents) caught issues before merge:

| Finding | Severity | Root Cause |
|---------|----------|------------|
| CORS missing PATCH method | P1 | Middleware config not updated when new HTTP methods added |
| Dual delete-orphan cascade | P1 | ORM cascade contradicted DB-level SET NULL intent |
| Missing FK on accepted_revision_id | P1 | Cross-table reference stored as plain string |
| Export `<a href>` skipping auth headers | P1 | Browser navigation doesn't send custom headers |
| DB connection held during LLM calls | P2 | Session held across 5-15s API call (pool starvation) |
| Unbounded generations eager load | P2 | selectinload grows with usage |

## Prevention & Lessons Learned

### Anti-Pattern Table

| Anti-Pattern | Pattern |
|---|---|
| Adding new HTTP methods without updating CORS `allow_methods` | Maintain a shared constant or use `allow_methods=["*"]` behind auth |
| `cascade="all, delete-orphan"` on ORM when DB has `ON DELETE SET NULL` | Decide cascade ownership at one level. Use `passive_deletes=True` to defer to DB |
| Cross-table ID stored as plain string without FK | Every `_id` column referencing another table gets a `ForeignKey` constraint |
| `<a href>` for authenticated file downloads | Use `fetch()` + blob URL for downloads requiring custom auth headers |
| `async with session:` wrapping external API calls | Split into load-call-persist phases; don't hold connections during LLM latency |
| `selectinload` on unbounded one-to-many | Default to lazy loading for growing collections; provide paginated endpoint |

### Pre-Merge Checklist Additions

1. If new HTTP methods are used, confirm they're in CORS `allow_methods`
2. For every new relationship, confirm ORM cascade and DDL `ON DELETE` agree
3. Every new `_id` column must have a `ForeignKey` constraint
4. File downloads must use `fetch()` with auth headers, not `<a href>`
5. External API calls must not be nested inside a session scope
6. `selectinload` on one-to-many relationships — ask: "can this grow without bound?"

### Testing Gaps

These integration tests would have caught the issues earlier:

- **CORS preflight test**: Iterate all registered routes, send OPTIONS, assert method in response
- **Cascade behavior test**: Delete parent via ORM, query DB directly, verify child state matches intent
- **FK integrity test**: Insert row with nonexistent reference ID, assert constraint violation
- **Authenticated download test**: Browser test clicking export button, assert request includes auth header
- **Pool saturation test**: N concurrent requests (N = pool size) with mocked slow LLM, assert no timeouts

## Related Documentation

### Plans & Scopes
- `docs/plans/2026-03-20-001-feat-policy-workspace-composer-v1-plan.md` — Implementation plan (completed)
- `docs/scopes/2026-03-21-cursor-for-public-policy-scope.md` — Scope document (completed)
- `docs/brainstorms/2026-03-20-policy-workspace-composer-requirements.md` — Requirements brainstorm

### Pending P2 Todos
- `todos/136-pending-p2-db-connection-held-during-llm-calls.md` — Pool starvation
- `todos/137-pending-p2-unbounded-generations-load.md` — Eager loading
- `todos/138-pending-p2-redundant-workspace-refetches.md` — Extra DB round-trips
- `todos/139-pending-p2-prompt-injection-defenses.md` — Structural delimiters
- `todos/140-pending-p2-toctou-race-on-double-accept.md` — Concurrent accept race
- `todos/141-pending-p2-missing-type-annotations.md` — Convention compliance

### Related Architecture
- `docs/solutions/architecture/p2-refactor-findings-resolution.md` — Prior architecture refactor findings
