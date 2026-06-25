"""Precompute scaffolding for Family 1 (runs ONCE per run, before generation).

In-memory, no temp tables. The reconciliation/overcount + completed-congress LOGIC and its
hermetic DuckDB fixtures land in sub-phase 1e; this module currently provides the frozen
SHAPE + a callable that returns empty sets, so the harness run-loop signature
(`harness.run` -> `template.generate(conn, n, seed, precomputed)`) is final as of 1b — the
frozen core breaks exactly once.

Phase 1 Template #1 (vote_lookup) does NOT consume these sets: a single member's recorded
option is unambiguous even on an overcounted event. They are scaffolding for Phase 2
aggregate templates + a data-quality artifact (excluded_events) and Family 10 seed material.
"""

from dataclasses import dataclass, field
from typing import Literal

# Extensible classification of why an event is excluded from aggregate gold (filled in 1e).
ExclusionReason = Literal["overcount", "missing_official_count"]


@dataclass(frozen=True)
class Precomputed:
    # NOTE: `frozen=True` blocks reassignment, not mutation of these collections.
    excluded_events: dict[str, ExclusionReason] = field(default_factory=dict)
    completed_congresses: frozenset[str] = frozenset()
    # event_to_congress: reserved for Phase 2 (built once here, never per-instance).
    # party_majority: reserved — a registry DEFINITION (denominator/ties/absences), blessed
    #   with its consumer (#4/#5/#6) in a later phase, not frozen on spec.


def precompute(conn) -> Precomputed:
    """1e fills overcount reconciliation + completed-congress here. The shell returns empties
    so the frozen run-loop signature is final now."""
    return Precomputed()
