---
date: 2026-06-28
topic: Bill-text corpus backfill (GovInfo BILLS) — prereq for family10.quote_in_bill_text
scope-mode: hold
status: approved
---

# Scope: Bill-text corpus backfill (Slice A)

## Problem
`bill_texts` holds 68/144,088 rows (0.05%) — the quote-in-text flagship (Family 10 slice 2) is blocked, and product features that read bill text (`analyze_version_diff`, search, the text-tab) are starved. Build a deterministic, **complete-stratum** federal bill-text corpus so the eval frame is defined by chamber/congress/version (independent of the quote task) — not cherry-picked by outcome.

## In Scope
- New `scripts/backfill_bill_text.py` orchestrator (mirrors `scripts/backfill_historical.py`: argparse, per-congress `IngestionRun`, resumable). **Parameterized by `--congress`**; this slice **runs 119 only**.
- A clean ingest method on `GovInfoIngester` over the existing `src/search/govinfo.py` primitives: `search_govinfo(collection="BILLS", congress, docClass)` → enumerate `packageId` → fetch `download.txtLink` → upsert `BillText`. Reuses `_rate_limited_get` 429-backoff + bounded concurrency.
- **Universe:** every HR + S bill in the 119th (~11.9k), **introduced version only** (BILLS `packageId` suffix `ih`/`is`). Bill-type only; introduced version only.
- `packageId` → `bill_id` resolution: parse `BILLS-119hr1234ih` → `generate_bill_id("us","us-119","HR1234")`; **attach text only to bills already in `bills`** (left-join, report misses). Idempotent: `generate_text_id` PK + `on_conflict_do_nothing`; skip bills that already have introduced text (resumable).
- **Verification surface (the deliverable's proof):** coverage report (resolved / fetched / attached of the 11.9k), `word_count`/dedup/`version_name` sanity, packageId-resolution accuracy spot-check.

## Out of Scope
- **`family10.quote_in_bill_text` template** → Slice B (the next slice; no `lab/` changes here).
- **Multi-congress run** — code is `--congress`-parameterized, but we run only 119 now (multi-congress 110–119 is the noted future product extension, a later sweep — not new code).
- **Non-introduced versions** (reported/engrossed/enrolled/amendments) — introduced-only keeps a clean single stratum; multi-version is a later enrichment.
- Resolutions (HRES/SRES/…); embeddings/search reindex of the new text (separate concern).
- The dead/mis-keyed `GovInfoIngester.fetch_bill_text` (keys off the wrong `govinfo_package_id`) — **replace with the new method; deprecate-note the old one**, don't reuse.

## Key Constraints
- `settings.govinfo_api_key` required — the search/package fns short-circuit to `{"error": ...}` without it; the backfill must fail loudly if unset.
- ~11.9k rate-limited GovInfo fetches; resumable so partial runs are safe. Coverage <100% is expected/honest (some bills have no published introduced text) → the eval frame is "the resolved corpus," still unbiased w.r.t. the quote task.
- Frozen core untouched (this slice is `src/` + `scripts/` + tests only; no `lab/`). ASCII-only, ruff line-length 100, conventional commits.

## Codebase Context
- Primitives: `src/search/govinfo.py::search_govinfo` / `get_govinfo_package` (sound; return `packageId` + `download.txtLink`). Orchestrator pattern: `scripts/backfill_historical.py`. Helpers: `src/ingestion/normalizer.py` (`generate_text_id`, `generate_bill_id`, `normalize_identifier`, `word_count`, `content_hash`). Target: `src/models/bill_text.py`.
- Selection-bias principle pre-committed in `docs/scopes/2026-06-27-family10-integrity-provenance-scope.md`: "the eval claim scoped to the corpus, so no selection bias."

## Open Questions (for /ce:plan)
1. GovInfo BILLS version filtering: does `search` cleanly yield introduced-only via `docClass`, or do we enumerate all versions and keep `packageId` ending `ih`/`is`? Resolve by inspecting one live response.
2. `txtLink` (plain text) as the content source — store `content_text` (+ `content_xml` from `xmlLink` for provenance?) — recommend txt primary.
3. `packageId`→`bill_id` robustness (type casing, number padding) — verify against existing 119 `bills`.
4. Throttle/concurrency params + total-runtime estimate for ~11.9k packages.
