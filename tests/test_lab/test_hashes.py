"""Anti-cheat hash tests (no DB). The two hashes are split on purpose:

  - grading_contract_hash: graders + scoring + resolved vocab VALUES. A change is a
    review RED FLAG (someone touched how answers are scored).
  - content_hash: templates + sampler + precompute. Grows legitimately as templates are added.

These tests prove the split holds: a contract change must not masquerade as content growth,
and vice versa.
"""

import shutil

from lab import trace

_CONTRACT = ("scoring.py", "graders.py")
_CONTENT = ("templates.py", "generate.py", "precompute.py")


def _copy_lab(dest):
    for name in _CONTRACT + _CONTENT:
        shutil.copy(trace._LAB_DIR / name, dest / name)
    return dest


class TestStability:
    def test_hashes_are_deterministic(self):
        assert trace.grading_contract_hash() == trace.grading_contract_hash()
        assert trace.content_hash() == trace.content_hash()

    def test_contract_and_content_differ(self):
        assert trace.grading_contract_hash() != trace.content_hash()


class TestVocabFlip:
    def test_vocab_change_flips_contract_only(self, monkeypatch):
        before_contract = trace.grading_contract_hash()
        before_content = trace.content_hash()
        monkeypatch.setattr(
            trace, "OPTION_BUCKETS", ("yea", "nay", "present", "not_voting", "EXTRA")
        )
        assert trace.grading_contract_hash() != before_contract  # red flag fires
        assert trace.content_hash() == before_content  # content untouched


class TestSourceFlip:
    def test_contract_file_change_flips_contract_only(self, tmp_path, monkeypatch):
        _copy_lab(tmp_path)
        monkeypatch.setattr(trace, "_LAB_DIR", tmp_path)
        base_contract = trace.grading_contract_hash()
        base_content = trace.content_hash()
        path = tmp_path / "graders.py"
        path.write_text(path.read_text(encoding="utf-8") + "\n# tweak\n", encoding="utf-8")
        assert trace.grading_contract_hash() != base_contract
        assert trace.content_hash() == base_content

    def test_content_file_change_flips_content_only(self, tmp_path, monkeypatch):
        _copy_lab(tmp_path)
        monkeypatch.setattr(trace, "_LAB_DIR", tmp_path)
        base_contract = trace.grading_contract_hash()
        base_content = trace.content_hash()
        path = tmp_path / "templates.py"
        path.write_text(path.read_text(encoding="utf-8") + "\n# tweak\n", encoding="utf-8")
        assert trace.content_hash() != base_content
        assert trace.grading_contract_hash() == base_contract  # contract NOT touched
