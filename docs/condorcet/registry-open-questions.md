# Condorcet registry — open definitions

Definitions a task needs but that are **not yet blessed**. Per the hard rule, a task that
requires one of these must STOP and surface it; the definition is resolved *with its first
consumer*, never invented on spec. Each entry is reserved in code as a `NotImplementedError`
slot so it cannot be silently half-implemented.

## `vote_time_party` — "the party a member belonged to *at the time of a given vote*"

**Surfaced 2026-06-25** during Family 1 Phase 2 planning (adversarial review). `people.party`
is a single **current** party value; the schema holds no vote-time/historical party. Attributing
a member's historical vote to their current party mis-assigns party-switchers (e.g. Specter,
Jeffords) and reads **post-dated** party onto an earlier vote — a point-in-time-discipline
violation the schema cannot currently satisfy. Per the hard rule, this is filed, not invented.

**DATA LAYER SHIPPED 2026-06-26 (Phase 3a, branch `feat/vote-time-party`).** Built as
`person_party_spans` (4 cols: `person_id`, `party` D/R/I/L, `start_date`, `end_date` **EXCLUSIVE**),
populated by `congress_legislators.py::ingest_term_history()` (one row per contiguous party-span;
mid-term switches split via `party_affiliations`). Resolution is **half-open**
`start_date <= vote_date < end_date` with `end_date = min(next_span.start, inclusive_end + 1 day)` —
disjoint whether the source shares or abuts boundary days (verified: source uses **shared**
boundaries, e.g. Specter 2009-04-30). Live validation: 7,636 spans / 1,260 members; **99.60%** of
1,050,514 (voter,date) pairs resolve to exactly one span, **0 overlaps**; Specter golden check
passes (R pre-2009-04-30, D after). The legacy `theunitedstates.io` JSON host (410 Gone) was
migrated to GitHub-raw YAML. *Full registry resolution (the lab consumer + production join) lands
with **3b**.* Refinements vs the original sketch: 4 columns (caucus/congress/chamber **deferred** to
3c); the table is **voter-scoped** (only bioguides in `people`); `Libertarian→L` added (Amash).

Consumers: **all** party-keyed Family 1 templates — `party_breakdown`, `party_defection`,
`crossed_party` (all Phase 3b/3c). Decision (2026-06-25): **defer** rather than ship
current-party as a leaky approximation into the factual trust floor.

**Resolution path (identified 2026-06-25, not yet built — a Phase 3 prerequisite):** the
authoritative per-term party data is **already fetched and discarded**. `src/ingestion/congress_legislators.py:77-79`
pulls each legislator's full `terms` array (each term carries `party` + `start`/`end` + chamber)
from the canonical *unitedstates/congress-legislators* dataset, then persists only
`terms[-1].party` into the single `people.party` column. Resolve `vote_time_party` by **persisting
the per-term history** — a `person_terms` table `(bioguide, start_date, end_date, congress, party,
chamber)` populated from the same ingest — and joining party **as-of `vote_events.vote_date`**
(within term date-range). Point-in-time-correct and fully sourced (NOT a hand-authored switcher
list — that would be hard-rule-adjacent and silently miss cases). **Edge:** true mid-term switchers
(e.g. Specter, 111th) are represented by the dataset's `party_affiliations` date-ranged sub-array;
read it when present, else the term `party`. A handful of cases; the data supports them.

## `party_majority` — "the majority position of a party on a roll-call event"

**RESOLVED 2026-06-26 (Phase 3c).** Implemented in `lab/templates._party_majority_side(yea, nay)`;
consumers `party_defection` (`gold = min(yea, nay)`) and `crossed_party` (the minority-side member
set). The three questions resolved as one blessed package:

1. **Denominator = yea+nay voters only** (option (a)); absences/`present` are excluded.
2. **Ties → `null`** (a strict majority is required); a null-majority (party, event) is **excluded**
   from defection/crossed gold (never a guessed or tie-broken side).
3. **Absences excluded** (falls out of #1 — `not_voting`/`present` do not count toward the denominator).

So `_party_majority_side` = `"yea"` if `yea > nay`, `"nay"` if `nay > yea`, else `None`. Both
consumers additionally require **≥2 yea/nay voters** (a 1-member party's "defection" is meaningless).
(`party_breakdown` is COUNTS-ONLY and does NOT consume `party_majority`.) All three party templates
also consume [[vote_time_party]]. *(Historical: this was a reserved `NotImplementedError` slot in
`lab/precompute.py`, retired in 3c.)*

> Related future work: the Family 8 "leverage" definitions follow the same discipline —
> bless-with-consumer, never freeze on spec.
