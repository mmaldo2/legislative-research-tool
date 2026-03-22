"""Tests for model artifact integrity verification."""

from pathlib import Path

from src.prediction.service import _verify_hash


class TestModelIntegrity:
    """Verify SHA-256 hash checking works correctly."""

    def test_verify_hash_correct(self, tmp_path: Path):
        """A file with matching hash passes verification."""
        import hashlib

        test_file = tmp_path / "test.pkl"
        test_file.write_bytes(b"model data here")
        expected = hashlib.sha256(b"model data here").hexdigest()
        assert _verify_hash(test_file, expected) is True

    def test_verify_hash_mismatch(self, tmp_path: Path):
        """A file with wrong hash fails verification."""
        test_file = tmp_path / "test.pkl"
        test_file.write_bytes(b"model data here")
        assert _verify_hash(test_file, "0000deadbeef") is False

    def test_verify_hash_missing_file(self, tmp_path: Path):
        """A missing file raises FileNotFoundError."""
        import pytest

        missing = tmp_path / "missing.pkl"
        with pytest.raises(FileNotFoundError):
            _verify_hash(missing, "anything")
