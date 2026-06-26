"""Drift Layer 2 (validate-the-proxy, requires_pg): the columns lab/ gold SQL depends on must
exist in the LIVE federal DB. L1 proves the ORM has them; this proves the ORM is a faithful
proxy of the live schema FOR THE COLUMNS GOLD READS — sidestepping the compare_metadata
false-positive swamp (server-defaults, ARRAY/JSONB, index churn) on these tables."""

import pytest

from lab.harness import get_connection


@pytest.fixture
def pg_conn():
    try:
        conn = get_connection()
    except Exception as exc:  # noqa: BLE001 — any connection failure means skip, not fail
        pytest.skip(f"Postgres unreachable: {exc}")
    yield conn
    conn.close()


@pytest.mark.requires_pg
def test_live_schema_has_required_columns(required_columns, pg_conn):
    cur = pg_conn.cursor()
    for table, cols in required_columns.items():
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            (table,),
        )
        live = {row[0] for row in cur.fetchall()}
        assert live, f"table {table!r} not found in the live DB"
        missing = cols - live
        assert not missing, f"live DB table {table!r} is missing lab-required columns: {missing}"
