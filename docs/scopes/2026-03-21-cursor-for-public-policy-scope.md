---
date: 2026-03-21
topic: Cursor for Public Policy — Composer V1 + Strategic Direction
scope-mode: selective-expand
status: completed
---

# Scope: Cursor for Public Policy

## Problem
Policy analysts lack an integrated drafting environment grounded in real legislative data. The platform has strong read-side capabilities (search, analysis, prediction, chat) but no write-side surface. V1 composer closes this gap with precedent-driven model legislation drafting; the longer-term trajectory is an agentic policy IDE.

## In Scope
- Fix P1 blockers (#132 build error, #126 async lazy-load crash) and P2 data bugs (#130 position, #131 provenance)
- Commit and land composer Phases 1-2 (workspace CRUD, precedent management, outline generation)
- Build Phase 3: section-by-section drafting with compose/accept/reject loop and revision history
- Build Phase 4 polish items: home page copy, status badges, list filtering
- **Selective expansion 1:** Markdown/docx export endpoint — required for v1, not optional
- **Selective expansion 2:** Minimal "search precedent language" action from within composer — one action that queries existing search infrastructure and returns results inline

## Out of Scope
- Rich editor framework (TipTap/Lexical/ProseMirror) — v2, after section-textarea UX is validated
- Multi-model routing / OAuth for frontier models — v2, requires real auth infrastructure
- Full assistant side panel in composer — v2, current expansion is one search action only
- Collaboration / multi-user drafting — v2+, requires real user identity beyond X-Client-Id
- Plugin/extension architecture — v2+
- Autoresearch model changes — separate workstream, already has its own sandbox

## Key Constraints
- Everything on `feat/policy-workspace-composer-v1` is uncommitted — stabilize and commit before expanding
- Detail page fails `next build` — must fix before any frontend work continues
- Async lazy-load guards (#126) will crash mutation endpoints at runtime — fix before testing
- Section-based data model must remain compatible with eventual block-based document model
- LLM integration architecture should assume multi-model future without building it now

## Codebase Context
- Existing research platform (23 routes, 25 models, 12 prompts) is the substrate — do not disrupt
- Composer reuses ownership pattern (`X-Client-Id`), LLM harness, bill text extraction, and search infrastructure
- Chat assistant's 6 research tools are candidates for future composer integration but not v1
- Autoresearch prediction model is a unique differentiator — surface prediction data in composer context long-term

## Open Questions
- What export format do policy analysts actually need? (Markdown is minimum; Word/PDF may be required)
- Should the "search from composer" action return results in a drawer, inline popover, or toast?
- What's the right trigger for v2 editor upgrade? Usage threshold, user feedback, or feature ceiling?
