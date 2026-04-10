"""Tests for pgvector-backed search helpers."""

import pytest

from src.search.vector import find_similar_bill_ids, vector_search


class _RowsResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def all(self):
        return self._rows


class _Row:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.queries = []
        self.rollback_calls = 0

    async def execute(self, statement, params):
        sql = str(statement)
        self.queries.append((sql, dict(params)))
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def rollback(self):
        self.rollback_calls += 1


@pytest.mark.asyncio
async def test_find_similar_bill_ids_rolls_back_and_falls_back_to_legacy_column():
    session = _FakeSession(
        [
            Exception("column bill_embeddings.vector does not exist"),
            _RowsResult([_Row(bill_id="bill-2", score=0.91)]),
        ]
    )

    matches = await find_similar_bill_ids(session, "bill-1", min_score=0.5, top_k=5)

    assert [m.bill_id for m in matches] == ["bill-2"]
    assert matches[0].score == pytest.approx(0.91)
    assert session.rollback_calls == 1
    assert "be1.vector" in session.queries[0][0]
    assert "be1.embedding" in session.queries[1][0]


@pytest.mark.asyncio
async def test_find_similar_bill_ids_uses_similarity_table_after_vector_failures():
    session = _FakeSession(
        [
            Exception("missing vector column"),
            Exception("missing embedding column"),
            _RowsResult([_Row(bill_id="bill-9", score=0.77)]),
        ]
    )

    matches = await find_similar_bill_ids(session, "bill-1", top_k=3)

    assert [m.bill_id for m in matches] == ["bill-9"]
    assert session.rollback_calls == 2
    assert "FROM bill_similarities" in session.queries[-1][0]


@pytest.mark.asyncio
async def test_vector_search_falls_back_to_second_candidate_column():
    session = _FakeSession(
        [
            Exception("vector column missing"),
            _RowsResult([_Row(bill_id="bill-3", similarity=0.88)]),
        ]
    )

    matches = await vector_search(session, [0.1, 0.2, 0.3], top_k=2)

    assert matches == [("bill-3", pytest.approx(0.88))]
    assert session.rollback_calls == 1
    assert "be.vector" in session.queries[0][0]
    assert "be.embedding" in session.queries[1][0]
