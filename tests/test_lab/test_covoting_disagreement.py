"""family6.covoting_disagreement -- the integrity properties with no analog elsewhere.

Phase 1 (this file, hermetic): the `_same_party_pair_keys` pair builder (party/floor filter,
canonical same-chamber-same-party dedup, no self-pair, input-order-independent determinism). The
`requires_pg` gold/twin/invariant/drift-guard tests are Phase 2.
"""

from lab.templates import _COVOTING_ACTIVE_FLOOR, _same_party_pair_keys


class TestSamePartyPairKeys:
    def test_filters_party_and_floor_pairs_within_chamber_party(self):
        floor = _COVOTING_ACTIVE_FLOOR
        rows = [
            ("A", "D", "house", floor),  # active D house
            ("B", "D", "house", floor + 5),  # active D house -> pairs with A
            ("C", "R", "house", floor),  # active R house (lone R -> no same-party partner)
            ("D", "D", "house", floor - 1),  # below the floor -> excluded
            ("E", "I", "house", floor + 10),  # not D/R -> excluded
            ("F", "D", "senate", floor),  # D senate
            (
                "G",
                "D",
                "senate",
                floor + 1,
            ),  # D senate -> pairs with F (different chamber from A/B)
        ]
        # only A-B (house D) and F-G (senate D); cross-party (C) and cross-chamber pairs never form.
        assert _same_party_pair_keys(rows) == ["house|A|B", "senate|F|G"]

    def test_canonical_sorted_no_self_pair(self):
        floor = _COVOTING_ACTIVE_FLOOR
        rows = [
            ("A", "D", "house", floor),
            ("B", "D", "house", floor),
            ("C", "D", "house", floor),
        ]
        keys = _same_party_pair_keys(rows)
        assert keys == [
            "house|A|B",
            "house|A|C",
            "house|B|C",
        ]  # canonical a<b, sorted, no self-pair
        assert all(len(k.split("|")) == 3 for k in keys)

    def test_input_order_independent(self):
        floor = _COVOTING_ACTIVE_FLOOR
        rows = [
            ("B", "D", "house", floor),
            ("A", "D", "house", floor),
            ("C", "D", "senate", floor),
            ("D", "D", "senate", floor),
        ]
        assert _same_party_pair_keys(rows) == _same_party_pair_keys(list(reversed(rows)))
        assert _same_party_pair_keys(rows) == ["house|A|B", "senate|C|D"]

    def test_empty_and_singletons(self):
        floor = _COVOTING_ACTIVE_FLOOR
        assert _same_party_pair_keys([]) == []
        # a single member per (chamber, party) group yields no pair
        assert _same_party_pair_keys([("A", "D", "house", floor), ("B", "R", "house", floor)]) == []
