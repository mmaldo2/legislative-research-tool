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

Consumers: **all** party-keyed Family 1 templates — `party_breakdown`, `party_defection`,
`crossed_party` (all deferred to Phase 3). Decision (2026-06-25): **defer** rather than ship
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

Reserved in `lab/precompute.py::_party_majority`. First consumers: Family 1 templates
**`party_defection` (party-line vs defection) and `crossed_party` (members who crossed party)**
— both Phase 3, and both *also* gated on [[vote_time_party]]. (`party_breakdown` is COUNTS-ONLY
and does **not** consume `party_majority` — but it does consume `vote_time_party`.)
Resolve these three questions before either template can produce gold:

1. **Denominator** — is the majority computed over (a) party members who cast yea/nay only,
   (b) party members present (yea/nay/present), or (c) all party members including not_voting?
   Different denominators yield different majorities on close/absentee-heavy votes.
2. **Ties** — when a party splits evenly (e.g. 5–5), is the party majority `null`, *both*
   positions, or resolved by a tie-break rule? A null majority changes how #5/#6 count defection.
3. **Absences** — do `not_voting` / `present` count toward the denominator (depressing the
   majority threshold) or are they excluded entirely?

These interact: the denominator choice partly determines whether ties even arise. Resolve as a
set, with the #4/#5/#6 consumer, and record the decision here before implementing.

> Related future work: the Family 8 "leverage" definitions follow the same discipline —
> bless-with-consumer, never freeze on spec.
