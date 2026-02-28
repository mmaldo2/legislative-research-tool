"""Tests for BM25 index (requires bm25s package)."""


from src.search.bm25 import BM25Index


class TestBM25Index:
    def test_not_built_initially(self):
        index = BM25Index()
        assert not index.is_built

    def test_search_empty_index_returns_empty(self):
        index = BM25Index()
        results = index.search("test query")
        assert results == []

    def test_manual_build_and_search(self):
        """Build index manually (without DB) and test search."""
        import bm25s

        index = BM25Index()
        index._corpus = [
            "Consumer Data Privacy Act establishes privacy rights",
            "Housing Affordability and Zoning Reform Act",
            "Clean Energy Transition and Carbon Tax Act",
            "Data privacy and consumer protection bill",
        ]
        index._bill_ids = ["bill-1", "bill-2", "bill-3", "bill-4"]

        corpus_tokens = bm25s.tokenize(index._corpus)
        retriever = bm25s.BM25()
        retriever.index(corpus_tokens)
        index._retriever = retriever

        assert index.is_built

        # Search for "data privacy" should return privacy-related bills
        results = index.search("data privacy", top_k=3)
        assert len(results) > 0
        result_ids = [r[0] for r in results]
        assert "bill-1" in result_ids or "bill-4" in result_ids

    def test_search_respects_top_k(self):
        """top_k should limit results."""
        import bm25s

        index = BM25Index()
        index._corpus = [f"Document about topic {i}" for i in range(20)]
        index._bill_ids = [f"bill-{i}" for i in range(20)]

        corpus_tokens = bm25s.tokenize(index._corpus)
        retriever = bm25s.BM25()
        retriever.index(corpus_tokens)
        index._retriever = retriever

        results = index.search("topic", top_k=5)
        assert len(results) <= 5
