---
date: 2026-04-08
topic: Cursor for Public Policy — MVP Product Spec
status: draft
scope-mode: refine-and-focus
---

# Cursor for Public Policy — MVP Product Spec

## Product framing

Build the first version of a policy-native research workbench where an analyst can go from a policy question to a saved, shareable research artifact inside one environment.

This MVP is not:
- a generic bill tracker
- a pure chat interface over legislative data
- a full drafting suite
- a full enterprise platform for government relations teams

This MVP is:
- an investigation-driven research copilot
- grounded in real legislative data
- optimized for policy analysts, think tanks, advocacy groups, and serious independent researchers
- designed to feel like working inside a live policy project, not jumping between search tabs and notes

## Core product promise

A user should be able to:
1. start with a policy question
2. search across a large legislative corpus
3. save relevant bills into a working set
4. compare and analyze those bills across jurisdictions
5. ask follow-up questions over that working set
6. produce a research memo / brief grounded in the underlying source material

If the MVP does this well, it earns the "Cursor for public policy" framing.

## Positioning

### Target user

Primary:
- policy researcher
- advocacy analyst
- think tank staffer
- legislative fellow / policy counsel doing issue-area research

Secondary:
- journalists / civic researchers
- public-interest litigators doing legislative background work
- policy entrepreneurs drafting model legislation

### User problem

Today, serious policy research requires stitching together:
- legislative databases
- keyword search
- spreadsheets
- side-by-side comparison docs
- copied bill text
- separate note-taking tools
- manual synthesis into briefs or memos

The user pain is not only discovery. It is working memory and synthesis.

The product should solve:
- finding the right bills
- understanding how they relate
- maintaining an investigation over time
- turning findings into a durable output

## Product thesis

The unit of value is not the bill.
The unit of value is the investigation.

Bills are the corpus atoms.
Investigations are the user's actual job.

The MVP should therefore be organized around:
- policy questions
- working sets
- comparisons
- evolving research threads
- saved outputs

## MVP user story

"I am researching a policy topic across states. I want to quickly find the relevant bills, understand which are substantively similar, identify important differences, ask iterative follow-up questions, and produce a memo I can use or share — without leaving the workspace."

## MVP success criteria

The MVP is successful if a target user can, in one session:
- search for a policy issue across jurisdictions
- save 5-20 relevant bills to a working set
- compare at least two bills and inspect meaningful differences
- ask at least three follow-up questions over the current working set
- generate a usable research memo / synthesis draft
- trust the results enough to continue the investigation later

## What exists already and should be used as scaffolding

The codebase already includes strong substrate capabilities:
- `/search/bills` hybrid search
- `/bills` and `/bills/{id}` detail pages
- `/bills/{id}/similar` similarity search
- AI summary, classification, version diff, constitutional analysis, pattern analysis
- report generation endpoint
- collections CRUD
- conversational assistant with tool use
- MCP server exposing research tools
- trend endpoints
- policy workspaces
- prediction endpoint
- organization/API-key scaffolding

These are valuable, but the MVP should refine and focus them rather than expose all of them equally.

## MVP product scope

### In scope

#### 1. Investigation-centered research workflow

The MVP should make "investigation" the visible working concept, even if the implementation initially reuses collections + conversations.

An investigation should support:
- a title / research question
- a saved bill working set
- analyst notes
- conversation history
- generated outputs

Implementation note:
- Do not build a brand-new heavyweight investigation domain model yet unless needed.
- First pass can likely layer this concept over existing collections + chat + report generation.

#### 2. Search and discovery

Must include:
- keyword + hybrid search across bills
- jurisdiction filters
- session filters where available
- relevance-ranked results
- quick-add to working set

Search result cards should prioritize:
- identifier
- title
- jurisdiction
- status
- why it matched / snippet
- add-to-investigation action

#### 3. Bill detail as a context node

Bill detail should support:
- full metadata
- bill text / version history
- latest AI summary
- action history
- sponsors
- similar bills

Bill detail should feel like a navigable context object inside the investigation, not a dead-end record page.

#### 4. Cross-jurisdiction comparison

Comparison is core to the MVP.

Must support:
- select two bills from search or working set
- structured AI comparison
- clear differences / shared provisions / overall assessment
- easy jump from comparison result back to underlying bills

Also include:
- version diff for a single bill with multiple text versions

#### 5. Working set / collection experience

The MVP needs a persistent working set.

Core behaviors:
- create investigation / collection
- add bills from search or bill detail
- annotate collection items
- reorder / remove as needed
- use the working set as chat context
- use the working set as report-generation context

This is one of the most important bridges to the Cursor analogy.

#### 6. Context-aware copilot

The chat assistant should be framed as a copilot for the current investigation, not a generic chatbot.

Must support:
- questions over the current working set
- ad hoc corpus questions when no working set is active
- visible tool-use activity
- clear grounding in retrieved bills
- follow-up questions that preserve investigation context

Supported MVP research actions:
- search_bills
- get_bill_detail
- find_similar_bills
- analyze_version_diff
- analyze_patterns
- search_govinfo
- get_govinfo_document

MVP rule:
- favor retrieval-backed questions over speculative analysis
- constitutional analysis can remain available, but should not be the centerpiece unless evidence/provenance is strong enough in the UI

#### 7. Memo / report generation

The user should be able to generate a research artifact from either:
- a search query
- or, preferably, the current working set

MVP output types:
- research memo
- comparative brief
- issue summary

The output must be:
- editable
- saveable
- exportable (Markdown minimum)
- clearly linked back to the bills and evidence used

### Selectively in scope

These may be present, but should be deprioritized in the MVP narrative:
- topic classification
- trend summaries
- prediction
- policy workspace drafting
- constitutional analysis

They can support the workflow, but they should not define the MVP story.

### Out of scope for MVP emphasis

Even if partial code exists, these should not be central to the first product story:
- full drafting IDE as the primary product
- multi-tenant enterprise collaboration
- plugin/extension architecture
- webhook-heavy alert platform
- broad regulatory/hearings/CRS unification as a core requirement
- custom taxonomy management
- polished external API platform narrative

## MVP information architecture

The product should feel investigation-first.

### Primary surfaces

#### 1. Home / Investigations
Purpose:
- re-enter active work quickly

Shows:
- recent investigations
- recently viewed bills
- saved collections
- suggested follow-up activity

#### 2. Search / Explorer
Purpose:
- discover candidates for an investigation

Contains:
- search box
- filters
- result list
- add-to-investigation action
- similarity-driven exploration hooks

#### 3. Investigation Workspace
Purpose:
- the main Cursor-like environment

Core layout:
- left rail: investigation outline / working set / notes / generated outputs
- center pane: selected bill, comparison, or memo
- right pane: copilot / tool activity / source trace

This is the canonical MVP surface.

#### 4. Bill Context View
Purpose:
- inspect a bill deeply without leaving the workspace model

Contains:
- summary
- text
- versions
- actions
- sponsors
- similar bills
- add-to-working-set and compare actions

#### 5. Output View
Purpose:
- work on the final artifact

Contains:
- generated memo/brief
- evidence used
- export controls
- links back to relevant bills and comparisons

## Canonical MVP workflow

### Workflow: from policy question to research memo

1. User creates an investigation
   - Example: "2026 state data privacy enforcement models"

2. User searches broadly
   - query-driven discovery using hybrid search

3. User saves a working set
   - 5-20 relevant bills across jurisdictions

4. System helps organize the set
   - highlight similar bills
   - surface outliers
   - suggest key comparisons

5. User opens bills and compares them
   - compare two or more relevant examples
   - inspect version changes when needed

6. User asks the copilot follow-up questions over the working set
   - "Which of these has the strongest private right of action?"
   - "How do enforcement provisions differ between CA, CO, and VA?"
   - "Which of these look like model-legislation variants?"

7. User generates a memo / brief
   - synthesized from the active investigation
   - grounded in retrieved material

8. User saves the investigation and returns later
   - continuity matters

## MVP differentiators

The MVP should differentiate on:

1. Cross-jurisdiction reasoning
- not just finding bills, but understanding legislative analogs across states

2. Working-set-based research
- not just search pages, but a durable project context

3. Retrieval-grounded copilot
- assistant works through real tools and current context

4. Integrated output creation
- memo generation is in the same environment as discovery and analysis

5. Research orientation
- optimized for analysts, not lobbyist alerting dashboards

## MVP quality bar

The MVP should feel trustworthy enough for serious use.

### Required trust properties

- search results are relevant enough that users don't feel lost
- bill detail is complete and navigable
- comparisons are meaningfully grounded
- chat clearly reflects tool-backed retrieval
- outputs preserve some evidence trail
- the user understands what came from source data vs AI synthesis

### Non-goals for MVP polish

- perfect nationwide coverage across all auxiliary sources
- perfect legal reasoning on constitutional analysis
- perfect drafting support
- enterprise admin completeness

## Product decisions

### Decision 1: Lead with investigations, not drafting

Recommendation:
- Make the research workbench the MVP headline
- Keep policy drafting as a secondary or adjacent capability

Why:
- It is closer to the strongest substrate already built
- It better matches the "Cursor" metaphor
- It avoids over-centering a narrower drafting use case too early

### Decision 2: Collections are the short-term implementation scaffold

Recommendation:
- Reuse collections as the backend basis for investigations in MVP
- Add UX and naming improvements before inventing a new domain object

Why:
- working functionality already exists
- faster path to a cohesive MVP
- avoids premature model sprawl

### Decision 3: Chat must be working-set-aware by default

Recommendation:
- when in an investigation, the assistant should prioritize the active working set
- global corpus chat remains available, but should feel secondary

Why:
- that is what makes the copilot feel project-aware rather than generic

### Decision 4: Report generation should key off the working set, not only raw search

Recommendation:
- add or prioritize a report path from saved investigation context

Why:
- reports generated from a stable working set are more explainable, more repeatable, and more Cursor-like

## MVP cuts / de-emphasis

To maintain focus, de-emphasize in the product story:
- organizations and enterprise gating
- webhooks and alert-delivery platform features
- full policy workspace drafting lifecycle as the main homepage story
- prediction as a central workflow driver
- broad trend dashboards as top-level navigation priorities

These can remain in the codebase and even ship, but they should not define the MVP experience.

## What to reuse from current codebase

Reuse directly:
- `src/api/search.py`
- `src/api/bills.py`
- `src/api/compare.py`
- `src/api/analysis.py`
- `src/api/chat.py`
- `src/api/collections.py`
- `src/api/reports.py`
- `src/mcp/server.py`
- `src/llm/harness.py`
- search + vector + bm25 infrastructure

Use selectively / tuck behind advanced workflows:
- `src/api/policy_workspaces.py`
- `src/api/prediction.py`
- `src/api/trends.py`
- webhooks / organizations / API management

## Open product questions

1. Should the visible MVP term be "Investigation", "Workspace", or "Collection"?
   - Recommendation: Investigation for product language; collections can remain implementation scaffold.

2. Should memo generation happen in the same investigation pane or in a separate output page?
   - Recommendation: same investigation pane first, separate page later if needed.

3. How explicit should source provenance be in early UI?
   - Recommendation: visible enough to establish trust, but not so verbose that it buries the workflow.

4. Does the first unforgettable workflow focus on one issue area (privacy, speech, education) for tighter demo/storytelling?
   - Recommendation: yes, if demo and go-to-market clarity benefit from it.

## Recommended MVP statement

"Cursor for Public Policy is an investigation-driven legislative research workspace. It helps policy analysts search across jurisdictions, build a working set of relevant bills, compare and interrogate them with an AI copilot grounded in real data, and turn that work into durable research outputs."

## Immediate follow-on document

After this product spec, the next planning artifact should be:
- a build plan for reshaping the current frontend around investigations + working sets + copilot + output
- explicitly identifying which existing pages/routes stay, which are renamed/reframed, and which are demoted from the MVP navigation
