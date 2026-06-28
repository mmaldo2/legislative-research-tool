---
title: Bill-text corpus backfill (GovInfo BILLS bulkdata, 119th HR+S introduced)
type: feat
status: active
date: 2026-06-28
revision: 2 (5-lens panel folded — authoritative; supersedes the body where rev 1 conflicts)
origin: docs/scopes/2026-06-28-bill-text-corpus-backfill-scope.md
---

# ✨ Bill-text corpus backfill (GovInfo BILLS bulkdata)

## Overview
Build a deterministic, **complete-stratum** federal bill-text corpus: the **introduced text of every HR + S bill in the 119th Congress** (~11.9k bills), ingested from the **GovInfo bulkdata BILLS ZIPs** as **USLM XML**. Frame is defined by chamber+congress+version — independent of the quote task — so the eval claim "scoped to the corpus" carries no selection bias. Unblocks `family10.quote_in_bill_text` (Slice B) and lights up product features (`analyze_version_diff`, search, text-tab).

This is **Slice A** (the corpus). The quote template is **Slice B** (next slice) — *no `lab/` changes here*.

> **Rev 2 (panel-folded):** transport pivoted from ~11k per-package htm API calls → **~5 bulkdata ZIP downloads of USLM XML** (perf-oracle C1, verified). The 68 pre-existing rows are a degraded format and are **deleted then rebuilt** from one clean path (data-integrity S1 + user decision). The dead `fetch_bill_text`/`_strip_html` are **deleted, not deprecated**. Full disposition table in the appendix.

## Problem Statement / Motivation
`bill_texts` holds **68 / 144,088 rows (0.05%)**, all Congress 119, and they are **degraded**: whitespace-collapsed, **un-unescaped** (`content_text` literally contains `&lt;DOC&gt;`), `content_html` set / `content_xml` NULL — i.e. produced by the broken `_strip_html` path. The one fetch method, `GovInfoIngester.fetch_bill_text` (`src/ingestion/govinfo.py:856`), has **zero callers** and is **mis-keyed** (uses the BILLSTATUS package id → would 404). We need a correct, fast, repeatable build that produces a **homogeneous** corpus.

## Proposed Solution
Mirror the blessed `ingest_from_bulk_zip` pattern (`src/ingestion/govinfo.py:361`): download the ~4 bulkdata BILLS ZIPs for the congress, parse each USLM XML entry, filter to introduced versions, extract clean body text, and bulk-upsert `BillText` — **after deleting all existing rows for the congress** so every row comes from one extraction path. Driven by a small resumable-by-reconstruction script.

### Probe findings (live, read-only, 2026-06-28)
- **Bulkdata transport (no API key, no rate limit):** `GET www.govinfo.gov/bulkdata/json/BILLS/119` → sessions `[1, 2]`. `…/bulkdata/BILLS/119/1/s/BILLS-119-1-s.zip` → **200, 29.5 MB, 3,887 XML entries, 3,526 introduced (`is.xml`)**. (perf-oracle verified hr: `BILLS-119-1-hr.zip` 45.7 MB / 8,042 entries / 6,909 `ih`.) Whole 119 HR+S corpus = **1 listing call + 4 ZIPs**, minutes.
- **Format = USLM XML** (`<bill bill-stage="Introduced-in-Senate">`, `<!DOCTYPE bill … bill.dtd>`). `defusedxml.SafeET.fromstring` parses it fine; **direct single-file access works too** (`…/119/1/s/BILLS-119s21is.xml` → 200) — used as the test fixture + straggler fallback.
- **Extraction:** remove the `<metadata>` subtree (dublinCore copyright boilerplate), then collect text → clean, newline-preserved bill text: `"II\n119th CONGRESS\n1st Session\nS. 21\nIN THE SENATE…\nA BILL\nTo require…"`. No boilerplate, no residual tags, no `&lt;`.
- **The existing 68:** `version_name` = 43 "Introduced in House" / 19 "Introduced in Senate" / 6 non-introduced; `content_text` newline-free **and** containing `&lt;DOC&gt;`. Degraded → delete-and-rebuild (do NOT skip).

### Flow
```
DELETE bill_texts for bills in us-{congress}           # one statement, homogeneous rebuild
sessions = GET bulkdata/json/BILLS/{congress}          # e.g. [1,2]
for session in sessions, doc_class in (hr, s):
  zip = GET bulkdata/BILLS/{congress}/{session}/{doc_class}/BILLS-{congress}-{session}-{doc_class}.zip
  for entry in zip (*.xml):
    parsed = _parse_bills_filename(entry)               # -> (congress,doc_class,number,version)|None
    if parsed is None or parsed.version not in {ih, is}: continue   # EXACT parsed match (not endswith)
    bill_id = generate_bill_id("us", f"us-{self.congress}", normalize_identifier(type+number))
    if bill_id not in bills_set: misses += 1; continue  # attach only to known bills
    text = _extract_bill_text_from_uslm(raw_xml)        # metadata removed, newlines kept
    accumulate BillText(content_text=text, content_xml=raw_xml, version_name=..., version_date=dc:date, source_url=zip#entry)
  bulk pg_insert(batch).on_conflict_do_nothing()  (begin_nested per batch); commit
report: enumerated / introduced / resolved / inserted / missed ; coverage = present/distinct-119-HR+S
```

## Technical Considerations
- **Home / layering:** all logic on `GovInfoIngester` (it already mixes HTTP+ORM legitimately). Two module-level **pure** helpers (hermetically testable, no I/O): `_parse_bills_filename(name) -> tuple|None` and `_extract_bill_text_from_uslm(raw_xml) -> str`. New constants `GOVINFO_BILLS_ZIP_URL` / `GOVINFO_BILLS_LISTING_URL` beside `GOVINFO_BULK_ZIP_URL`.
- **Parser totality (kieran I4, di N2):** anchor `^BILLS-`, case-insensitive, letters→digits→letters split; returns lowercased `(congress:int, doc_class:str, number:str, version:str)` or `None` for non-BILLS / malformed / missing-version. `number` stays `str` (no int-coerce). Reject `rih/ris/rfh/rfs/pcs/es/rs/eh/rh/enr/…` by **exact** `version in {"ih","is"}` — never `endswith` (di C1: `…rih` ends in `ih`).
- **Extractor (USLM):** `SafeET.fromstring(raw)` → locate the `<metadata>` element (local-name match, namespace-agnostic), detach it, then `"\n".join(s for s in (t.strip() for t in root.itertext()) if s)` and collapse intra-line `[ \t]+`. Newlines preserved (Slice B owns final canonicalization). Verified clean on the probe sample.
- **Resolution (kieran N7):** build `bill_id` from `self.congress` (not the parsed congress); assert `parsed.congress == self.congress` as a guard/log. `normalize_identifier("s21")="S21"` matches the congress-API ingest (`govinfo.py:261`) → aligns with existing `bills` rows. Prefetch the congress's `{bill_id}` set in one query.
- **Homogeneous rebuild (user decision):** `DELETE FROM bill_texts WHERE bill_id IN (SELECT id FROM bills WHERE session_id = 'us-{congress}')` at run start (drops all 68, incl. the 6 non-introduced — accepted; not re-ingested this slice). Then fresh insert. `on_conflict_do_nothing` is only a defensive backstop (cross-session dup filename). Re-running fully reconstructs (deterministic) → idempotent by reconstruction; no pre-skip machinery needed.
- **Writes (perf N4, di I4):** batched multi-row `pg_insert(BillText).values([...])` (~200/batch) under a per-batch `begin_nested` savepoint; commit per batch. Sequential — **no concurrency** (one ZIP at a time, in-memory `io.BytesIO`; ≤~46 MB resident). This retires the AsyncSession-race concern entirely.
- **Fields:** `content_text` = extracted text; `content_xml` = raw USLM XML (the purpose-built column, NULL today); `content_html` = NULL; `word_count(content_text)`; `content_hash(content_text)` (kieran N9); `version_date` = dublinCore `<dc:date>`; `version_name` from parsed version (`ih`→"Introduced in House", `is`→"Introduced in Senate"); `source_url = "{zip_url}#{entry}"` (no key — bulkdata needs none).
- **No API key (arch I3 moot):** bulkdata is public/static; the key-fallback question disappears. (`search_govinfo`'s narrower key rule is left untouched — not unified this slice.)
- **Run tracking (arch N1):** `start_run("text")` / `finish_run`; set `run.records_created` and stash the coverage dict in `run.metadata_`. `await ingester.close()` in a `finally` (kieran N11).
- **Dead-code deletion (arch I1, simplicity P2):** delete `fetch_bill_text`, `_strip_html`, `_RE_HTML_TAG`, `_RE_WHITESPACE` — zero callers, and keeping the whitespace-collapsing path alive is a footgun.

## System-Wide Impact
- **Interaction graph:** `BillText` insert fires nothing — no ORM event, no auto-embed/reindex (separate batch, out of scope); `BaseIngester._track_changes` tracks *bills*, not texts. Leaf write. (Phase-0 one-line check that `autoresearch/prepare.py` does not read `bill_texts` — arch N4; CLAUDE.md flags its hardcoded SQL.)
- **Error propagation:** per-entry `try/except` + per-batch `begin_nested` (like `ingest_from_bulk_zip`) → a bad XML/row is logged and skipped without aborting the batch. A whole-run failure leaves a partial corpus; re-run = delete + rebuild (clean). ZIP/listing download failure fails the run loudly.
- **State lifecycle:** delete→insert; on failure the corpus may be partial until re-run (acceptable: rebuild is minutes, deterministic). `BillText` has no dependents → no orphans.
- **API surface parity:** the new method is the canonical text path; the dead method is deleted. `get_bill_detail` / text-tab already read `bill_texts` → light up free. No new MCP/chat tool.

## Acceptance Criteria
- [x] `_parse_bills_filename` parses `BILLS-119hr1234ih.xml` / `BILLS-119s21is.xml`; returns `None` for non-`BILLS-`, `BILLSTATUS-…`, malformed, and version-less ids; case-insensitive; `number` is `str`.
- [x] Introduced predicate keeps **exactly** `ih`/`is`; rejects `rih`/`ris`/`rfh`/`rfs`/`pcs`/`es`/`rs`/`eh`/`rh`/`enr`.
- [x] `_extract_bill_text_from_uslm` (on the embedded probe XML) excludes dublinCore boilerplate (`"Pursuant to Title 17"`/copyright absent), includes bill-body markers (`"A BILL"`), preserves newlines (line-count > 1), leaves no `<…>` tag or `&lt;`/`&gt;`/`&amp;` entity.
- [ ] `backfill_bill_texts` deletes the congress's existing rows, downloads the bulkdata ZIPs, attaches text **only to bills in `bills`**, batch-upserts, and is deterministic on re-run (identical corpus).
- [x] `content_xml` populated (raw USLM), `content_text` newline-preserving, `version_name` "Introduced in House"/"Introduced in Senate", `version_date` from `<dc:date>` (asserted by the in-memory-zip row-fields test; live-confirmed Phase 3).
- [ ] Coverage measured as **rows-present / distinct-119-HR+S** (not rows-inserted), reported with distinct-bill counts (di I1/I2); persisted to `run.metadata_`.
- [ ] `python -m scripts.backfill_bill_text --congress 119` runs end-to-end and prints the coverage report. `source_url` contains no key; nothing logs a key.
- [x] Hermetic tests pass; `ruff check`/`format` clean (ASCII-only, line-length 100); frozen `lab/` untouched (`grading_contract_hash` + `content_hash` unmoved).
- [ ] **Execution (Phase 3):** corpus 68 → resolved introduced stratum (target ~10–11k); 5-row spot-check (resolution + readable text) + re-run-deterministic recorded in the PR.

## Success Metrics
- Distinct 119 HR+S bills with introduced text: **68 → ~10–11k**; coverage = present / distinct-119-HR+S (expected <100%, reported honestly).
- Corpus homogeneity: **0** rows with `&lt;` in `content_text`; **0** newline-free rows (all from the one extractor).
- Re-run determinism: identical row set (same `content_hash`es).

## Dependencies & Risks
- **Coverage <100%** (a bill may lack an `ih/is` package) — by design; frame = "the resolved corpus."
- **Bulkdata availability/schema drift** — Phase-1 fixture pins the USLM shape; the live download is Phase-3.
- **Partial-corpus window** on mid-run failure — mitigated by fast deterministic rebuild; noted, not engineered around.
- **USLM `itertext` fidelity** — uses element text+tail via `itertext`; verified complete on the probe sample.

## Implementation Phases (checkpoints — STOP after each)

### Phase 0 — Branch + carry-over docs
- [x] New branch `feat/lab-bill-text-corpus` off `main`.
- [x] First commit carries the uncommitted working-tree docs: the scope, this plan (rev 2), and the backlog-doc edit (`docs/condorcet/2026-06-28-task-suite-build-backlog.md`).
- [x] Confirm `autoresearch/prepare.py` does not read `bill_texts` (arch N4). **PASS** — zero refs to `bill_texts`/`content_*` anywhere in `autoresearch/`.

### Phase 1 — Pure helpers + hermetic tests  → STOP
- [x] `_parse_bills_filename`, `_extract_bill_text_from_uslm`, the introduced predicate (`_is_introduced`), bill_id resolution (`_resolve_bill_id`); new `GOVINFO_BILLS_LISTING_URL`/`GOVINFO_BILLS_ZIP_URL` constants + `INTRODUCED_VERSIONS`/`_VERSION_NAMES`; **deleted** `fetch_bill_text`/`_strip_html`/`_RE_HTML_TAG`/`_RE_WHITESPACE` (zero refs remaining repo-wide).
- [x] `tests/test_ingestion/test_bill_text_backfill.py` (hermetic, 17 tests): filename parse (hr/s/versions/`rih`/`ris`/non-bills/`BILLSTATUS`/malformed), USLM extraction on an embedded `BILLS-119s21is`-style fixture (boilerplate-out, body-in, newlines, no tags/entities, entity-unescaping), predicate, resolution, version_name mapping.
- [x] Tests green (17 new; full suite **868 passed, 30 skipped** — the documented async-pg skips); `ruff check`/`format` clean on changed files; frozen `lab/` untouched. Commit; **STOP**.

### Phase 2 — Ingest method + script  → STOP
- [x] `backfill_bill_texts(self, doc_classes=("hr","s"), limit=None)` on `GovInfoIngester`: delete-for-congress → enumerate sessions (`_fetch_bills_sessions`) → download ZIPs (`_download_bills_zip`, 404-skip / loud-otherwise) → `_bill_text_rows_from_zip` (pure) → `_insert_bill_text_rows` (batched, `begin_nested`) → `_bill_text_coverage` → `IngestionRun` tallies in `metadata_`. Entry-loop carved as the pure module-level `_bill_text_rows_from_zip` (kieran I6 — no live network).
- [x] `scripts/backfill_bill_text.py`: argparse **`--congress` (int, default 119), `--limit`** only (cut `--versions`/`--doc-class`/`--concurrency`/`--request-delay`/`--api-key` — simplicity P1/P3/P4/P5, all moot under bulkdata); `async_session_factory`; `await ingester.close()` in `finally`.
- [x] In-memory-zip tests for the filter/resolve/miss-count loop (+ sessions-listing + dc:date parsers). Full suite **876 passed, 30 skipped**; `ruff` clean on changed files; commit; **STOP**.

### Phase 3 — Execute + verify (user-triggered)  → STOP
- [ ] Run `python -m scripts.backfill_bill_text --congress 119`.
- [ ] Record coverage + 5-row spot-check + re-run-determinism; grep for key leakage. Open PR.

## Testing Strategy
- **Hermetic (CI):** all helpers + the entry-loop (in-memory `zipfile` fixture, embedded probe XML). No live network/DB in CI. The extraction test is the regression guard for boilerplate-exclusion + newline-preservation.
- **Phase-3 real run** is the integration proof (4 ZIPs, minutes). Per CLAUDE.md: `PYTHONPATH=. uv run python -m pytest tests/...`; conventional commits; footer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## Panel resolutions (rev 2 — folded, authoritative)
- **perf-oracle C1 → ADOPTED (headline):** bulkdata ZIP / USLM XML transport. Retires perf C2/I2/I3/N6/N7, arch C1, kieran C2, di I3 (rate-limit/concurrency/session-race/pre-skip all moot).
- **data-integrity S1 + user decision → DELETE-all-119-then-rebuild:** homogeneous corpus from one extractor; do_nothing backstop only.
- **data-integrity C1 → exact parsed-version match** (`rih`/`ris` excluded); version derived from parse, single source of truth (kieran I5).
- **data-integrity I1/I2 → coverage = rows-present, distinct-bill counts.**
- **arch I1 / simplicity P2 → DELETE dead `fetch_bill_text`+`_strip_html`** (not deprecate).
- **kieran C1 → USLM extractor contract** (remove `<metadata>`, itertext, newlines) replaces the htm contract; **kieran I4/N7/N9 →** total case-insensitive parser, resolve from `self.congress`, hash over `content_text`; **kieran I6 →** in-memory-zip-testable entry loop.
- **arch N1 → persist tallies to `run.metadata_`; arch N4 →** Phase-0 `prepare.py` check.
- **simplicity P1/P3/P4/P5 →** cut `--versions`/`--doc-class`/throttle flags; `--limit` smoke instead of HTTP mock; CLI = `--congress`,`--limit`.
- **arch I2/I3 →** bulkdata bypasses the search-module primitives and needs no key; left non-unified by design (noted).

## Sources & References
- **Origin scope:** [docs/scopes/2026-06-28-bill-text-corpus-backfill-scope.md](../scopes/2026-06-28-bill-text-corpus-backfill-scope.md).
- Pattern to mirror: `src/ingestion/govinfo.py:361` (`ingest_from_bulk_zip`), `:51` (`GOVINFO_BULK_ZIP_URL`), `:436` (`_parse_bill_status_xml` defusedxml usage), `:90` (`_parse_bill_type_number` module-level parser). Dead code to delete: `:856` (`fetch_bill_text`), `:893` (`_strip_html`). Helpers: `src/ingestion/normalizer.py` (`generate_bill_id:8`, `generate_text_id:14`, `normalize_identifier:62`, `word_count:69`, `content_hash:24`). Model: `src/models/bill_text.py:9` (note `content_xml` deferred-markup column). Run tracking: `src/ingestion/base.py:26`.
- Selection-bias precedent: `docs/scopes/2026-06-27-family10-integrity-provenance-scope.md`.
- Memory: `project_condorcet_build_backlog`, `project_research_tools_beyond_eval`.
- Next slice (out of scope): `family10.quote_in_bill_text` (Slice B) — negative-quote adversarial verification over this corpus.
