"""Phase-1 shape generalization: the grader-dispatched `coerce`, the uniform `_map_answer` order,
the leak-safe submit schemas, and the key-set cross-consistency vs the FROZEN template gold.

All hermetic except the one `requires_pg` cross-consistency test (regenerates real instances to
prove SUBMIT_SCHEMAS/GOLD_KEYS still match the frozen gold key-sets).
"""

import pytest

from lab.graders import REFUSAL, grade
from lab.solvers import (
    GOLD_KEYS,
    NO_ANSWER,
    SUBMIT_SCHEMAS,
    _map_answer,
    _to_int,
    coerce,
)

VL = "family1.vote_lookup"
TALLY = "family1.tally"
BREAKDOWN = "family1.party_breakdown"
DEFECTION = "family1.party_defection"
CROSSED = "family1.crossed_party"


def _submit(args: dict) -> list[dict]:
    return [{"tool_name": "submit_answer", "arguments": args}]


def _ma(args: dict, grader: str, tid: str):
    return _map_answer(_submit(args), grader=grader, template_id=tid)


class TestToInt:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (5, 5),
            (12.0, 12),  # integral float
            ("12", 12),  # digit str
            (" 7 ", 7),
            (True, None),  # bool excluded
            (3.7, None),  # non-integral -> reject (never round)
            ("5.0", None),  # not a digit str
            ("abc", None),
            (None, None),
            (float("nan"), None),
            (float("inf"), None),
        ],
    )
    def test_to_int(self, value, expected):
        assert _to_int(value) == expected if expected is not None else _to_int(value) is None


class TestCoerceExactInt:
    def test_int_and_coercible(self):
        assert coerce("exact_int", DEFECTION, {"count": 5}) == 5
        assert coerce("exact_int", DEFECTION, {"count": 12.0}) == 12
        assert coerce("exact_int", DEFECTION, {"count": "12"}) == 12

    @pytest.mark.parametrize("payload", [{"count": 3.7}, {"count": "5.0"}, {"count": None}, {}])
    def test_malformed_to_no_answer(self, payload):
        assert coerce("exact_int", DEFECTION, payload) == NO_ANSWER


class TestCoerceFields:
    def test_exact_keys_and_types(self):
        out = coerce("fields", TALLY, {"yea": 12, "nay": 3, "margin": 9, "result": "Passed"})
        assert out == {"yea": 12, "nay": 3, "margin": 9, "result": "Passed"}
        assert set(out) == set(GOLD_KEYS[TALLY])  # exact gold key-set

    def test_numeric_coercion_matches_exact_int(self):
        # a correct "12"/12.0 must NOT false-fail (same _to_int as exact_int)
        out = coerce("fields", BREAKDOWN, {"yea": "12", "nay": 3.0})
        assert out == {"yea": 12, "nay": 3}

    def test_missing_field_keeps_key_as_none(self):
        out = coerce("fields", TALLY, {"yea": 1, "nay": 0, "result": "Passed"})  # margin missing
        assert set(out) == set(GOLD_KEYS[TALLY]) and out["margin"] is None

    def test_non_coercible_numeric_kept_raw_attempted_but_wrong(self):
        out = coerce("fields", BREAKDOWN, {"yea": "lots", "nay": 3})
        assert out["yea"] == "lots" and out["nay"] == 3  # dict shape valid -> wrong, not malformed
        v = grade("fields", {"yea": 5, "nay": 3}, out, is_refusal=False)
        assert v.subscores["format_valid"] == 1.0 and not v.passed


class TestCoerceSetMatch:
    def test_list_and_empty(self):
        assert coerce("set_match", CROSSED, {"member_ids": ["p1", "p2"]}) == ["p1", "p2"]
        assert coerce("set_match", CROSSED, {"member_ids": []}) == []  # ∅ is a valid answer
        assert coerce("set_match", CROSSED, {"member_ids": [1, 2]}) == ["1", "2"]

    @pytest.mark.parametrize("payload", [{"member_ids": "p1"}, {"member_ids": {"a": 1}}, {}])
    def test_non_list_to_no_answer(self, payload):
        assert coerce("set_match", CROSSED, payload) == NO_ANSWER  # str/dict iterable -> guarded


class TestCoerceExact:
    def test_string_passthrough_and_non_string(self):
        assert coerce("exact", VL, {"answer": "yea"}) == "yea"
        assert coerce("exact", VL, {"answer": 123}) == NO_ANSWER
        assert coerce("exact", VL, {}) == NO_ANSWER


class TestMapAnswerOrder:
    def test_exact_int(self):
        assert _ma({"count": 5}, "exact_int", DEFECTION) == 5
        assert _ma({"refused": True}, "exact_int", DEFECTION) == REFUSAL
        assert _ma({"count": 0, "refused": True}, "exact_int", DEFECTION) == NO_ANSWER  # both
        assert _ma({}, "exact_int", DEFECTION) == NO_ANSWER  # neither
        assert _map_answer([], grader="exact_int", template_id=DEFECTION) == NO_ANSWER  # no submit

    def test_set_match_empty_is_an_answer_not_refusal(self):
        # an explicit empty crossers set IS a substantive answer, not a refusal
        assert _ma({"member_ids": []}, "set_match", CROSSED) == []
        assert _ma({"refused": True}, "set_match", CROSSED) == REFUSAL
        assert _ma({"member_ids": ["p1"], "refused": True}, "set_match", CROSSED) == NO_ANSWER

    def test_fields(self):
        full = {"yea": 1, "nay": 0, "margin": 1, "result": "Passed"}
        assert _ma(full, "fields", TALLY) == full
        assert _ma({"refused": True}, "fields", TALLY) == REFUSAL


class TestNoMethodLeakInSchemas:
    def test_descriptions_state_quantity_not_method(self):
        for tid, props in SUBMIT_SCHEMAS.items():
            for field, spec in props.items():
                desc = spec.get("description", "").lower()
                assert "min(" not in desc, f"{tid}.{field} leaks the computation"
                assert "minority" not in desc, f"{tid}.{field} leaks the computation"


@pytest.mark.requires_pg
class TestKeySetConsistency:
    """The frozen-spec coupling guard: GOLD_KEYS / the coerce-built dict must equal the ACTUAL
    frozen template gold key-set, or every `fields` instance silently false-fails."""

    @pytest.mark.parametrize("name,tid", [("tally", TALLY), ("party_breakdown", BREAKDOWN)])
    def test_gold_keys_match_real_gold(self, name, tid):
        from lab import templates
        from lab.harness import get_connection
        from lab.precompute import precompute

        try:
            conn = get_connection()
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"Postgres unreachable: {exc}")
        try:
            instances = templates.TEMPLATE_REGISTRY[name].generate(conn, 5, 42, precompute(conn))
        finally:
            conn.close()
        answerable = [i for i in instances if not i.is_refusal]
        if not answerable:
            pytest.skip(f"no answerable {name} instances generated")
        gold = answerable[0].gold
        assert set(gold) == set(GOLD_KEYS[tid]), "GOLD_KEYS drifted from the frozen template gold"
        built = coerce("fields", tid, {k: gold[k] for k in gold})
        assert set(built) == set(gold)  # coerce emits exactly the gold key-set
