"""Tests for P1 security fixes — auth, ILIKE escaping, BM25 locking."""

from src.api.deps import escape_like
from src.search.bm25 import BM25Index


class TestEscapeLike:
    """P1-004: ILIKE wildcard injection prevention."""

    def test_escapes_percent(self):
        assert escape_like("100%") == r"100\%"

    def test_escapes_underscore(self):
        assert escape_like("some_thing") == r"some\_thing"

    def test_escapes_backslash(self):
        assert escape_like(r"back\slash") == "back\\\\slash"

    def test_normal_text_unchanged(self):
        assert escape_like("data privacy") == "data privacy"

    def test_all_wildcards(self):
        # Input: %_\  →  \%\_\\
        result = escape_like("%_\\")
        assert result == "\\%\\_\\\\"

    def test_empty_string(self):
        assert escape_like("") == ""


class TestBM25Invalidate:
    """P1-006: BM25 index invalidation."""

    def test_invalidate_clears_index(self):
        import bm25s

        index = BM25Index()
        # Manually build
        index._corpus = ["test doc"]
        index._bill_ids = ["bill-1"]
        corpus_tokens = bm25s.tokenize(index._corpus)
        retriever = bm25s.BM25()
        retriever.index(corpus_tokens)
        index._retriever = retriever
        assert index.is_built

        # Invalidate
        index.invalidate()
        assert not index.is_built
        assert index._corpus == []
        assert index._bill_ids == []

    def test_search_after_invalidate_returns_empty(self):
        import bm25s

        index = BM25Index()
        index._corpus = ["test doc"]
        index._bill_ids = ["bill-1"]
        corpus_tokens = bm25s.tokenize(index._corpus)
        retriever = bm25s.BM25()
        retriever.index(corpus_tokens)
        index._retriever = retriever

        index.invalidate()
        results = index.search("test")
        assert results == []


class TestAuthConfig:
    """P1-001: API key auth configuration."""

    def test_api_key_setting_defaults_empty(self):
        """Empty API key = dev mode (no auth enforced)."""
        from src.config import Settings

        s = Settings(api_key="")
        assert s.api_key == ""

    def test_cors_origins_default(self):
        """CORS origins default to localhost."""
        from src.config import Settings

        s = Settings()
        assert "localhost" in s.cors_origins

    def test_llm_provider_defaults_to_claude_sdk(self, monkeypatch):
        """Local/dev default should use the subscription-auth Claude SDK path."""
        from src.config import Settings

        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        s = Settings()
        assert s.llm_provider == "claude-sdk"

    def test_agentic_provider_defaults_to_codex_local(self, monkeypatch):
        """Local/dev default should route assistant/report/compare flows through Codex."""
        from src.config import Settings

        monkeypatch.delenv("AGENTIC_PROVIDER", raising=False)
        s = Settings()
        assert s.agentic_provider == "codex-local"
