---
title: Co-voting disagreement-set task (Family 6, set_match twin of pairwise_agreement)
type: feat
status: active
date: 2026-06-28
revision: 2 (5-lens panel folded — authoritative; supersedes the body where rev 1 conflicts)
origin: docs/scopes/2026-06-28-covoting-disagreement-set-scope.md
---

# ✨ Co-voting disagreement-set task (Family 6)

## Overview
A new frozen template `family6.covoting_disagreement`: "Across the 119th {chamber} roll calls, on which
did member X and member Y cast OPPOSING recorded votes (one yea, one nay)?" gold = the SET of
`vote_event_id`s where both cast yea/nay and differ; grader **`set_match`**. It is the **`set_match`
(exact-evidence) twin of the existing `generate_pairwise_agreement` (Template #7)** — same two-member
self-join + window, but produce the exact disagreement EVIDENCE (citation-style, the lab's
anti-hallucination theme) instead of a count. Built for **discrimination + RLVR**; moat LOW/public.

> **Rev 2 (panel-folded):** the nearest sibling is `generate_pairwise_agreement` (`lab/templates.py:418`,
> the COUNT version, grader `fields`, already discriminates haiku~0-4→sonnet~9-10). Rev 2 **mirrors it**
> (names + `find_people`, NOT the person_id — reverting rev 1's over-simplification), which also makes the
> refusal-twin proof correct via `find_people`'s any-option window filter. Adds same-party selection + set
> gold. Phase-3 discrimination split OUT (rate-limited). Full disposition table in the appendix.

## Problem Statement / Motivation
The discrimination principle (sharpened by the quote no-go): a task discriminates only when the agent
must COMPUTE over a large set the tool does not pre-join, and be exactly precise. `pairwise_agreement`
already proves this pattern discriminates as a COUNT. The disagreement-SET is the harder, distinct
grader — exact ids (all-or-nothing `set_match`), inherently high-cardinality (same-party pairs disagree
a median ~15 times among ~500 shared votes → precision-at-scale on every instance).

## Proposed Solution
Structural fork of `generate_pairwise_agreement`: same self-join + `{congress, chamber}` window + the
`(vote_event_id, person_id)` uniqueness reliance; swap the count accumulation for a differing-event SET +
`set_match`; restrict to same-party pairs; add the two refusal twins. **No new tool** — reuse pairwise's
member tool set (`find_people` + `get_member_voting_record`).

### Data (verified at scope, 119th)
Same-party |disagree| median ~18 House (15-23, max 123) / ~14 Senate (12-15) — a gradeable precision
band. Cross-party = 200-350 (set_match lottery; **excluded**; its agreement set is also large, so
cross-party is out entirely). Pair selection is answer-INDEPENDENT (party+chamber+per-member activeness
floor), so |gold| falls out without bias.

### Answer shape + tools (mirror pairwise)
- Prompt gives both members' **names** (pairwise's shape) + chamber; `TEMPLATE_TOOLS` = pairwise's
  `_MEMBER_TOOLS` = `[find_people, get_member_voting_record]`. The agent resolves names→ids
  (`find_people`), fetches both records, filters each to yea/nay, returns the differ-set. (Rev 1 gave the
  id + dropped `find_people` — reverted for sibling consistency AND because `find_people`'s window filter
  is what makes Twin-A airtight.)
- `SUBMIT_SCHEMAS["family6.covoting_disagreement"] = {"vote_event_ids": {array of string, "...empty list
  if none"}}` (the `crossed_party` "empty list" phrasing, NOT cite's singleton); `SET_MATCH_FIELD =
  "vote_event_ids"`.

### Gold SQL (mirrors pairwise's option-pair join; SELECT the differing ids)
```sql
SELECT DISTINCT ra.vote_event_id
FROM vote_records ra JOIN vote_records rb ON ra.vote_event_id = rb.vote_event_id
JOIN vote_events ve ON ve.id = ra.vote_event_id
JOIN bills b ON b.id = ve.bill_id JOIN sessions s ON s.id = b.session_id
WHERE ra.person_id = %s AND rb.person_id = %s
  AND s.identifier = %s AND ve.chamber = %s         -- congress passed as the string '119'
  AND ra."option" IN ('yea','nay') AND rb."option" IN ('yea','nay')
  AND ra."option" <> rb."option"
```
`gold = {r[0] for r in rows}` (set-collect; DISTINCT defensive). Assert `X != Y`. Pair pool = active
(≥ `_ACTIVE_FLOOR` yea/nay, a literal module constant) same-party members per chamber; deterministic
seeded sample of canonical pair-keys (below).

### Pair sampling (inline, reuse `sample` — no big helper)
One tiny pure helper `_same_party_pair_keys(roster_rows) -> list[str]`: filter to `party IN ('D','R')` +
the floor, **sort** each (chamber, party) roster, build canonical `f"{chamber}|{min(a,b)}|{max(a,b)}"`
keys (so `(a,b)`/`(b,a)` dedup and no self-pair), union across chambers. Then `sample(sorted(keys), n,
seed)` (the project's tested determinism primitive — `crossed_party`'s precedent). Instances are
independent, so light member-reuse across pairs is fine (no anti-clustering needed). Hermetic-testable.

### Refusal twins (`refusal_correct`, identical prompt shape)
- **Twin A — never-co-voted (structural):** a real House-119 member + a real Senate member, prompt framed
  `chamber=house`. `find_people(senator, 119, house)` returns **empty** (its filter requires ≥1 record of
  ANY option in the window; the senator has 0 house records) → the agent cannot resolve the senator →
  REFUSE. **Per-emit proof = the senator has 0 `(119, house)` records of ANY option** (matches
  `find_people` + `get_member_voting_record`'s `if not rows` gate exactly — NOT "0 yea/nay", which a
  chamber-switcher/present-only member would falsely pass).
- **Twin B — nonexistent member:** a synthetic name absent from `people` → `find_people` empty → REFUSE
  (pairwise's existing twin). Proven absent.
- Both distinct from the answerable empty set (co-voted, never disagreed → return ∅, do NOT refuse).

## Technical Considerations
- **No precompute / `complete_events` gate** — and the precise reason (panel-validated): covoting reads
  only X's and Y's OWN records and asserts NO count/size invariant over the roster (unlike `crossed_party`,
  whose `len(crossers)==min(yea,nay)` cross-checks a set against a roster count → needs complete events).
  An overcount/undercount/missing event touches only OTHER members' rows; X's and Y's disagreement is read
  identically by the gold SQL and the tool. `precomputed` accepted-but-unused (the cosponsor precedent).
- **Uniqueness linchpin (STOP-and-surface → Phase 2 assert):** the "no-gate" + drift-guard equality both
  rest on `(vote_event_id, person_id)` uniqueness. It is model-declared (`vote.py:30`) + ingestion-proven
  (`votes.py` ON CONFLICT) but **not migration-verified** (Alembic drift). Phase 2 adds a `requires_pg`
  assert: `SELECT vote_event_id, person_id, COUNT(*) FROM vote_records GROUP BY 1,2 HAVING COUNT(*)>1
  LIMIT 1` returns ZERO rows. Plus `DISTINCT` + set-collect as defense-in-depth.
- **Sidesteps the open `person_party_spans` bug** — gold is party-INDEPENDENT (party is only the
  answer-independent pair filter; uses `people.party`).
- **Hashes (corrected):** `solvers.py` (where SUBMIT_SCHEMAS/SET_MATCH_FIELD/TEMPLATE_TOOLS live) is in
  NEITHER hash; the `templates.py` change ALONE moves `content_hash`. `grading_contract_hash` UNMOVED
  (no graders/scoring/vocab change). `test_hashes` split holds.
- Leak-safety: prompt carries names + chamber, never a gold `vote_event_id`.

## System-Wide Impact
- **Interaction graph:** generation reads PG at build; the live agent routes `find_people` /
  `get_member_voting_record` through the same `lab_execute_tool` seam as pairwise. No new handler/wiring.
  Deterministic solvers already handle set + REFUSAL gold (`WrongBaselineSolver` adds `NX-wrong`;
  `OverRefuseSolver` REFUSAL; ∅ gold validated by `harness.validate_gold`).
- **Error propagation:** twins rely on `find_people` returning `{"people": [], "count": 0}` for an
  absent/out-of-window member → the agent maps "not found" → REFUSE.
- **State lifecycle:** none — read-only generation; no migration, no writes.
- **API surface parity:** none new — `find_people` + `get_member_voting_record` already product + MCP.
- **Integration scenarios (tests):** gold == differ-set from two REAL `get_member_voting_record` calls
  (drift guard, equality not subset — both read the same `vote_records`); uniqueness assert; Twin-A senator
  0 house-119 records of any option; Twin-B name absent; oracle/wrong/over-refuse over set + REFUSAL gold.

## Acceptance Criteria
- [ ] `generate_covoting_disagreement` emits same-party-same-chamber answerable instances (gold = the
  differing `vote_event_id` set) + Twin-A (cross-body) + Twin-B (nonexistent); `is_refusal == (gold ==
  REFUSAL)` and `X != Y` asserted per emit.
- [x] `_same_party_pair_keys` is a pure helper: filters party+floor, sorts, canonical dedup'd pair-keys,
  no self-pair (hermetic test — 4 cases).
- [x] Registered in `TEMPLATE_REGISTRY`; `SUBMIT_SCHEMAS`/`SET_MATCH_FIELD`/`TEMPLATE_TOOLS=_MEMBER_TOOLS`;
  grader `set_match`; submit description says "an empty list if none".
- [ ] `requires_pg`: each gold eid is a roll-call where both cast yea/nay and differ; no gold eid in the
  prompt; the uniqueness assert returns zero rows; **Twin-A senator proven 0 `(119,house)` records of ANY
  option**; Twin-B name absent.
- [ ] `requires_pg` drift guard: gold == the differ-set computed from two real `get_member_voting_record`
  outputs (yea/nay-both, differ); skip on DB-down, FAIL on tool-error for an active member.
- [ ] Deterministic invariants: oracle passes all; wrong fails all; over-refuse fails every answerable.
- [ ] `test_hashes` passes (grading_contract_hash UNMOVED, content_hash moved); full suite + `ruff` clean;
  one `EXPLAIN (ANALYZE)` spot-check confirms index scans on the self-join (no new index needed).

## Success Metrics
- Sampled |gold| lands in the gradeable band (median ~12-23); generator LOGS the distribution by chamber.
- Invariants 100% green; uniqueness assert green; gold==tool drift guard green.
- (Follow-up, out-of-slice) discrimination on **active same-party pairs**: expect a haiku<sonnet≤opus
  gradient (the pairwise-count precedent).

## Dependencies & Risks
- **Cardinality band:** same-party median ~15 is gradeable; tail to ~120 exists. Accept the natural
  (answer-independent) distribution; LOG |gold|; do NOT filter on |gold| (the never-cross-aisle trap).
- **Uniqueness assumption:** addressed by the Phase-2 assert (above).
- **Name ambiguity:** mirrors pairwise's accepted risk (give stored name + `find_people`); revisit only if
  the discrimination run shows resolution failures.

## Implementation Phases (checkpoints — STOP after each)

### Phase 0 — Branch + carry-over docs
- [x] New branch `feat/lab-covoting-disagreement` off `main`.
- [x] First commit carries the uncommitted working-tree docs: the quote-deprioritization record (backlog
  re-score, `2026-06-28-family10-quote-in-bill-text-scope.md` status=deprioritized,
  `lab/experiments/quote_discrimination_probe.py`) + this slice's scope + plan.

### Phase 1 — Generator + seam + hermetic test  → STOP
- [x] `TEMPLATE_COVOTING = "family6.covoting_disagreement"`, `_COVOTING_ACTIVE_FLOOR` constant,
  `_same_party_pair_keys` (pure), `generate_covoting_disagreement` (pool → pair-keys → `sample` → gold SQL
  → answerable + Twin-A/Twin-B via `_covoting_refusal`), registry entry.
- [x] `lab/solvers.py`: `SUBMIT_SCHEMAS` + `SET_MATCH_FIELD` + `TEMPLATE_TOOLS` entries.
- [x] Hermetic test: `_same_party_pair_keys` (determinism, canonical dedup, no self-pair).
- [x] `pytest` green (full suite **880 passed, 30 skipped**; `test_hashes` split holds — `content_hash`
  moved, `grading_contract_hash` UNMOVED) + `ruff` clean; commit; **STOP**.

### Phase 2 — requires_pg tests + invariants + hashes + PR  → STOP
- [ ] `tests/test_lab/test_covoting_disagreement.py`: gold predicate, the uniqueness assert, twin per-emit
  proofs (0-records-any-option), oracle/wrong/over-refuse invariants, the gold==two-tool drift guard
  (async, skip-on-DB-down / fail-on-tool-error-for-active-member).
- [ ] `test_hashes` split holds; full suite + `ruff` clean; `EXPLAIN` spot-check. Commit; open PR.

### (Follow-up, OUT of this slice) — Discrimination run
- Haiku/sonnet/opus over the suite, out-of-session / dedicated key (the OAuth rate-limit wall). Tracked
  like Family 1's "opus deferred"; the in-slice |gold| logging already gives the band evidence.

## Testing Strategy
- Hermetic (CI): `_same_party_pair_keys`. `requires_pg`: gold/uniqueness/twins/invariants/drift-guard. No
  live-model tests in CI. Per CLAUDE.md: `PYTHONPATH=. uv run python -m pytest tests/...`; conventional
  commits + the Opus footer.

## Panel resolutions (rev 2 — folded, authoritative)
- **arch I1 / kieran (nearest sibling) → MIRROR `generate_pairwise_agreement`** (names + `find_people` +
  the self-join), reverting rev 1's give-id/drop-find_people. Makes the family the count/set pair.
- **data-integrity #4 / kieran C1 → Twin-A proof = 0 records of ANY option** in the window (find_people's
  filter); a chamber-switcher/present-only member would otherwise poison the twin.
- **data-integrity #2 → uniqueness build-time assert + DISTINCT + set-collect** (the no-gate linchpin;
  not migration-verified).
- **simplicity P1/P2 →** inline `sample`-based pair-keys (one tiny pure helper, not a sampler class); DROP
  House/Senate stratification (log by chamber instead); DROP answerable-∅ sourcing; **SPLIT Phase-3
  discrimination OUT** of the slice.
- **arch N1 / kieran N3 →** hash wording fixed (solvers.py in neither hash); **kieran N1 →** "empty list if
  none" submit desc; **data-integrity #3 →** `X != Y` assert + congress as string `'119'`; **perf →** one
  `EXPLAIN` spot-check, no new index (the `(vote_event_id, person_id)` unique index + `person_id` index
  already make the self-join a ~500-probe loop).
- **arch/data-integrity (no-gate) → CONFIRMED correct** (covoting reads two members' own rows, no roster
  aggregate); reframed precisely vs `crossed_party`'s count-invariant.

## Sources & References
- **Origin scope:** [docs/scopes/2026-06-28-covoting-disagreement-set-scope.md](../scopes/2026-06-28-covoting-disagreement-set-scope.md).
- **Nearest sibling (mirror):** `lab/templates.py::generate_pairwise_agreement:418` (Template #7, the COUNT
  twin; self-join + `_MEMBER_TOOLS` + nonexistent-member twin). Others: `generate_cosponsored_and_voted_against:978`
  (emit-asserts, refusal twins, gold-vs-tool test), `generate_cite_record_id:798` (structural no-link refuse),
  `generate_crossed_party:713` (member-set `set_match`; the count-invariant that NEEDS the complete-events
  gate — the contrast). Tool: `src/api/chat.py::_tool_find_people:394` + `_tool_get_member_voting_record:445`.
  Seam/invariants: `lab/solvers.py` (`_MEMBER_TOOLS`, SUBMIT_SCHEMAS, the deterministic solvers). Graders
  (frozen): `lab/graders.py` (`set_match`). Uniqueness: `src/models/vote.py:30`. Registry: `lab/templates.py:1286`.
- Backlog (NEXT row) + Meta-update: `docs/condorcet/2026-06-28-task-suite-build-backlog.md`. Memory:
  `project_condorcet_build_backlog`, `project_condorcet_eval_philosophy`, `project_person_party_spans_gold_integrity` (sidestepped).
