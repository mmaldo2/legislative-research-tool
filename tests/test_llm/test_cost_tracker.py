"""Tests for the LLM cost tracker."""

from src.llm.cost_tracker import CostTracker


class TestCostTracker:
    def test_record_cost(self):
        tracker = CostTracker()
        record = tracker.record("claude-sonnet-4-6", 1000, 500, "summarize")

        assert record.model == "claude-sonnet-4-6"
        assert record.tokens_input == 1000
        assert record.tokens_output == 500
        assert record.cost_usd > 0

    def test_sonnet_pricing(self):
        tracker = CostTracker()
        # 1M input tokens at $3/MTok + 1M output tokens at $15/MTok = $18
        record = tracker.record("claude-sonnet-4-6", 1_000_000, 1_000_000, "summarize")
        assert abs(record.cost_usd - 18.0) < 0.01

    def test_haiku_pricing(self):
        tracker = CostTracker()
        # 1M input at $1/MTok + 1M output at $5/MTok = $6
        record = tracker.record("claude-haiku-4-5", 1_000_000, 1_000_000, "classify")
        assert abs(record.cost_usd - 6.0) < 0.01

    def test_batch_discount(self):
        tracker = CostTracker()
        normal = tracker.record("claude-sonnet-4-6", 1_000_000, 1_000_000, "summarize")
        batch = tracker.record("claude-sonnet-4-6", 1_000_000, 1_000_000, "summarize", batch=True)
        assert abs(batch.cost_usd - normal.cost_usd * 0.5) < 0.01

    def test_total_cost(self):
        tracker = CostTracker()
        tracker.record("claude-sonnet-4-6", 1000, 500, "summarize")
        tracker.record("claude-haiku-4-5", 2000, 300, "classify")
        assert tracker.total_cost > 0
        assert len(tracker.records) == 2

    def test_total_tokens(self):
        tracker = CostTracker()
        tracker.record("claude-sonnet-4-6", 1000, 500, "summarize")
        tracker.record("claude-haiku-4-5", 2000, 300, "classify")
        total_in, total_out = tracker.total_tokens
        assert total_in == 3000
        assert total_out == 800

    def test_summary_string(self):
        tracker = CostTracker()
        tracker.record("claude-sonnet-4-6", 1000, 500, "summarize")
        summary = tracker.summary()
        assert "1 calls" in summary
        assert "$" in summary


class TestContentHash:
    def test_harness_content_hash_deterministic(self):
        from src.llm.harness import LLMHarness

        h1 = LLMHarness.content_hash("bill text here", "summarize-v1")
        h2 = LLMHarness.content_hash("bill text here", "summarize-v1")
        assert h1 == h2

    def test_harness_content_hash_changes_with_version(self):
        from src.llm.harness import LLMHarness

        h1 = LLMHarness.content_hash("bill text here", "summarize-v1")
        h2 = LLMHarness.content_hash("bill text here", "summarize-v2")
        assert h1 != h2
