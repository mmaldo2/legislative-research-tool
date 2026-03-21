---
date: 2026-03-20
topic: policy-workspace-composer
---

# Policy Workspace Composer

## Problem Frame
The current product is already becoming a credible legislative research platform: search, bill detail, comparison, reports, prediction, and an agentic research assistant all exist or are in flight. What it does not yet provide is a first-class place where policy analysts do the actual writing work.

That gap matters because the strongest long-term position is likely not "better legislative chat" in isolation. It is a product where the boring database platform becomes the substrate and the differentiated surface is a writing workspace: drafting model legislation, adapting precedent bills, producing redlines, and delegating bounded research or drafting tasks to an agent while preserving provenance and analyst control.

## Requirements
- R1. The product must introduce a first-class policy workspace where users create and edit model-legislation drafts rather than only query legislative data.
- R2. The default v1 drafting flow must begin with the user selecting precedent bills that will ground the draft.
- R3. Before generation begins, v1 must require the user to choose a target jurisdiction and drafting template so the draft is anchored to a concrete legislative context.
- R4. After precedent selection, v1 must generate a proposed bill outline before any full-text drafting begins.
- R5. The primary v1 interaction must be inline compose actions in the editor, not generic chat or passive autocomplete.
- R6. Full-text drafting in v1 must happen section by section on explicit user request rather than drafting the entire bill automatically by default.
- R7. The workspace must support bounded agent actions for legislative research and drafting tasks, and the user must review outputs before accepting them.
- R8. AI-generated drafting assistance must preserve provenance so an analyst can see which bills, documents, or analyses informed an outline or drafted section.
- R9. The workspace must support human-controlled revision flows such as draft history, comparisons, and approval before any generated content is treated as final.
- R10. The product must preserve the existing legislative database platform as a supporting layer for search, browsing, comparison, reporting, and analysis rather than replacing it.

## Success Criteria
- A policy analyst can start from selected precedent bills and produce a materially useful first draft inside the product.
- Users perceive the product as a writing and analysis environment, not only a legislative database with chat.
- The precedent-to-outline-to-section-drafting workflow is clearly faster and higher quality than the current combination of database research plus separate LLM chat.
- AI suggestions are auditable enough that analysts can trust and defend the resulting draft or memo.

## Scope Boundaries
- The first composer release will not attempt to be a full general-purpose IDE for every policy artifact at once.
- The first composer release will not allow unsupervised publication or external submission of AI-written legislative text.
- The initial scope will focus on policy analyst workflows, not constituent-facing explainers or campaign messaging.
- The existing research platform remains in scope as infrastructure and supporting UX, but it is not the differentiated primary surface.

## Key Decisions
- First-class direction: build a write-side policy workspace, not just a stronger chat tab.
- Product framing: keep the Quorum-like research platform as the data and retrieval substrate beneath the composer experience.
- Agent role: treat agents as collaborators inside a workspace with explicit user approval boundaries, not as autonomous actors with invisible side effects.
- Autoresearch role: treat `autoresearch/` as a specialized internal capability and product ingredient, not as the main product metaphor.
- Initial writing job: optimize the first composer release for drafting model legislation from precedent bills.
- Initial interaction model: make inline composer assistance the dominant v1 interaction, with explicit agent tasks secondary.
- Default session start: begin drafting from selected precedent bills rather than from a blank prompt or imported bill.
- Initial generation flow: after precedent selection, generate a proposed bill outline before drafting full sections.
- Jurisdiction anchoring: require a target jurisdiction and drafting template before generation starts.
- Drafting progression: draft sections one at a time on explicit user request rather than drafting the whole bill immediately.

## Dependencies / Assumptions
- Existing search, bill detail, comparison, reports, prediction, and chat capabilities are stable enough to act as the substrate for a composer layer.
- The platform can expose source provenance from existing bill and analysis records in a way that drafting features can reuse.
- Users will accept a narrower initial composer wedge if it produces clearly better work than a generic external LLM chat workflow.

## Outstanding Questions

### Resolve Before Planning
- None.

### Deferred to Planning
- [Affects R1][Technical] What artifact model best fits the workspace: standalone draft documents, draft trees tied to source bills, or a mixed document-plus-source graph?
- [Affects R5][Technical] Which editor actions should ship in v1 first, such as draft section, rewrite clause, tighten definitions, or harmonize with precedent language?
- [Affects R7][Technical] Which existing assistant tools can be reused directly inside the workspace, and which write-oriented tools must be added?
- [Affects R8][Needs research] What provenance UI is sufficient for analyst trust without making the editor unusably dense?
- [Affects R9][Technical] What document diff and approval model best matches legislative drafting workflows?

## Next Steps
-> `/ce:plan` for structured implementation planning.
