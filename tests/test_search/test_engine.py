"""Tests for search engine — RRF fusion, BM25 index, and schema validation."""

from src.schemas.common import MetaResponse
from src.schemas.search import SearchResponse, SearchResult
from src.search.engine import rrf_fuse


class TestRRFFusion:
    """Test Reciprocal Rank Fusion logic (pure function, no DB)."""

    def test_single_list_passthrough(self):
        """Single ranked list should be returned as-is."""
        ranked = [("bill-a", 10.0), ("bill-b", 5.0)]
        fused = rrf_fuse([ranked], top_k=10)
        assert fused[0][0] == "bill-a"
        assert fused[1][0] == "bill-b"

    def test_two_lists_identical_ranking(self):
        """Same ranking in both lists should boost top result."""
        list1 = [("bill-a", 10.0), ("bill-b", 5.0), ("bill-c", 1.0)]
        list2 = [("bill-a", 0.9), ("bill-b", 0.5), ("bill-c", 0.1)]
        fused = rrf_fuse([list1, list2], top_k=3)
        assert fused[0][0] == "bill-a"
        assert fused[1][0] == "bill-b"
        assert fused[2][0] == "bill-c"

    def test_disjoint_lists(self):
        """Disjoint lists should return all items."""
        list1 = [("bill-a", 10.0)]
        list2 = [("bill-b", 10.0)]
        fused = rrf_fuse([list1, list2], top_k=10)
        ids = {f[0] for f in fused}
        assert "bill-a" in ids
        assert "bill-b" in ids

    def test_overlapping_lists_boost(self):
        """Items appearing in both lists should rank higher than unique items."""
        list1 = [("bill-overlap", 10.0), ("bill-only-bm25", 9.0)]
        list2 = [("bill-overlap", 0.9), ("bill-only-vec", 0.8)]
        fused = rrf_fuse([list1, list2], top_k=10)
        # bill-overlap should be first since it appears in both
        assert fused[0][0] == "bill-overlap"

    def test_top_k_truncation(self):
        """Results should be truncated to top_k."""
        ranked = [(f"bill-{i}", float(100 - i)) for i in range(50)]
        fused = rrf_fuse([ranked], top_k=5)
        assert len(fused) == 5

    def test_empty_lists(self):
        """Empty input should return empty output."""
        fused = rrf_fuse([], top_k=10)
        assert fused == []

    def test_rrf_scores_are_positive(self):
        """All RRF scores should be positive."""
        ranked = [("a", 1.0), ("b", 0.5)]
        fused = rrf_fuse([ranked])
        for _, score in fused:
            assert score > 0


class TestSearchSchemas:
    """Test search request/response schemas."""

    def test_search_result(self):
        result = SearchResult(
            bill_id="abc123",
            identifier="HR 1234",
            title="Test Bill",
            jurisdiction_id="us",
            status="introduced",
            score=0.85,
            snippet="...data privacy...",
        )
        assert result.score == 0.85

    def test_search_response(self):
        resp = SearchResponse(
            data=[
                SearchResult(
                    bill_id="abc",
                    identifier="HR 1",
                    title="Test",
                    jurisdiction_id="us",
                    score=0.9,
                ),
            ],
            meta=MetaResponse(total_count=1, page=1, per_page=20),
        )
        assert len(resp.data) == 1
        assert resp.meta.total_count == 1
