---
date: 2026-06-27
topic: Tool-surface ablation pass 2 — point-in-time party (the moat-revealing arena)
scope-mode: reduce
status: approved
---

# Scope: Ablation pass 2 — point-in-time party probe

## Problem
Pass 1 (the control) validated the metric + harness, and found web is **honest** on a simple lookup
(`halluc=0` — it refuses, never fabricates). So the moat thesis ("our data layer beats the open web
on *trustworthy* answers") is **not yet tested**: a lookup can't elicit fabrication. Pass 2 hunts for
where web flips to **confident-wrong** (`halluc>0`) — and the sharpest arena is **point-in-time
party**: our DB preserves a member's *vote-time* party; the web returns their *current/famous* party.
For a party-switcher, those differ — so web is confidently wrong *unless* it reasons about the
timeline. (Decisions: design-chat 2026-06-27.)

## In Scope (pass 2 — a MINIMAL answerable-only probe)
- **Template `family9.member_party_at_vote`** (a real Family 9 / temporal-reconstruction template;
  advances the roadmap while serving the ablation, as pass 1 reused `vote_lookup`). Prompt: *"What
  party was {name} representing when they voted on roll call {eid}?"* — names member + the internal
  eid (parallel to vote_lookup; no explicit year → web must decode/reason).
- **Gold = the VOTE-TIME party** via the existing validated half-open `person_party_spans` as-of join
  (the same one `get_vote_event` already returns). **Answerable-only** (no refusal twins — deferred).
- **Two instance kinds, marked:** (a) **switcher** — (switcher, roll-call) pairs where vote-time
  party ≠ current party (the DISCRIMINATING set; ~7,664 pairs across 10 famous switchers: Sinema/
  Manchin/Van Drew/Lieberman/Griffith); (b) **control** — non-switcher votes (vote-time = current)
  where web *should* match ours, isolating the point-in-time effect.
- **Grader = `set_match` singleton** (`gold={party}`; party isn't a vote OPTION so `exact`'s gate
  rejects it — the established cite_record_id path) + a **party-alias-fold** ("Democrat"→"D", parallel
  to the pass-1 vote-vocab-fold) in `coerce`, non-frozen. **No new grader.**
- **Run the ablation matrix** (`surface{ours,web} × model{haiku,sonnet}`) on it, **split switcher vs
  control** in the report/analysis (web ≈ ours on controls, diverges on switchers = the moat).
  - `ours` path: `get_vote_event(eid)` → reads vote-time party → correct (incl. switchers).
  - `web` path: WebSearch + fetch_url → current party → confidently wrong on switchers if it doesn't
    reason temporally.

## Out of Scope (deferred)
- Refusal twins / the full frozen Family 9 treatment (promote later if we build Family 9 properly).
- Other moat arenas (exact aggregation, no-link over-claim); `both`/`neither` surfaces; opus.
- Any frozen-core change (graders/scoring/vocab) — STOP-and-surface if one seems needed.

## Key Constraints
- Reuses the ablation harness wholesale (surface knob, trust-weighted report, fetch_url, the matrix).
- Frozen core untouched: `grading_contract_hash` UNMOVED; `content_hash` moves (new template — legit).
  set_match reused; the party-fold lives in `solvers.py` (non-frozen, like the vote-fold).
- The moat is in the **switcher** subset's `halluc` rate — the report must NOT average it away with
  the controls.

## Codebase Context
- `lab/templates.py` (the `generate` pattern; `cite_record_id` for the set_match-singleton shape);
  `lab/solvers.py` (`coerce`/`_fold_option`/`SET_MATCH_FIELD`/`SUBMIT_SCHEMAS`/`TEMPLATE_TOOLS`, the
  party-fold goes beside `_fold_option`); `src/api/chat.py::_tool_get_vote_event` (returns vote-time
  party already); `lab/ablation.py` (the matrix + report — add the switcher/control split).
- Data (verified 2026-06-27): 7,664 discriminating (switcher, roll-call) pairs, 10 switchers; party
  vocab `{D,I,L,R}` (spans) / `{D,I,ID,R}` (current). Memory: [[project_condorcet_eval_philosophy]].

## Open Questions (for /ce:plan)
1. The switcher/control split in the run: two template entries (switcher-only, control-only) vs one
   template + an `is_switcher` param + a post-hoc/report split? (Lean: one template, marked, split in
   the report.)
2. The exact party-alias-fold map (D/Democrat/Dem; R/Republican/GOP; I/Independent; L; ID) + whether
   the `set_match` singleton field is named `party`.
3. The eligibility gate: which switcher votes count (all vote-time≠current pairs?), the
   completed-congress / complete-event discipline, and the deterministic sampling.
