"""The RunManifest contract (the writer side of the ablation -> lift_analysis provenance chain)."""

from dataclasses import dataclass

import pytest

from lab.manifest import RunManifest


@dataclass
class _Ctx:
    grading_contract_hash: str
    content_hash: str
    dataset_fingerprint: dict


def test_manifest_roundtrip_and_crash_safe_append(tmp_path):
    m = RunManifest(run_id="r1", params={"n": 6}, rollout_seed=42)
    m.save(tmp_path)  # param block persisted BEFORE any cell (crash-safe)
    # a crash here still leaves an analyzable (empty-cell) manifest
    reloaded = RunManifest.load("r1", tmp_path)
    assert reloaded.cell_files == [] and reloaded.rollout_seed == 42

    m.stamp_hashes(_Ctx("CH", "COH", {"vote_events": 7}), tmp_path)
    (tmp_path / "ablation_r1_a.jsonl").write_text("{}\n")
    m.add_cell(tmp_path / "ablation_r1_a.jsonl", tmp_path)

    final = RunManifest.load("r1", tmp_path)
    assert final.grading_contract_hash == "CH" and final.content_hash == "COH"
    assert final.dataset_fingerprint == {"vote_events": 7}
    assert final.cell_files == ["ablation_r1_a.jsonl"]  # basename only


def test_manifest_load_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="no manifest"):
        RunManifest.load("absent", tmp_path)


def test_usage_tokens_dict_object_and_none():
    from lab.solvers import _usage_tokens

    assert _usage_tokens(None) == (None, None)
    assert _usage_tokens({"input_tokens": 10, "output_tokens": 3}) == (10, 3)

    class _U:
        input_tokens = 5
        output_tokens = 7

    assert _usage_tokens(_U()) == (5, 7)
    # non-int / partial -> None for the bad field, never raises
    assert _usage_tokens({"input_tokens": "x"}) == (None, None)
