"""Determinism + portability guard over the gold-producing SQL (no DB).

Two layers, non-redundant with the behavioral DuckDB fixtures:
  - DETERMINISM: random()/now()/current_date/current_timestamp/TABLESAMPLE execute fine on
    DuckDB but break reproducibility — execution can NEVER catch these, only a static scan can.
  - PORTABILITY tripwire: Postgres-only structural tokens (@>, = ANY(array)).

We AST-extract every SQL string literal from the gold-producing modules and scan each.
"""

import ast
import re
from pathlib import Path

import pytest

import lab.precompute
import lab.templates

_DETERMINISM = [
    (r"\brandom\s*\(", "random()"),
    (r"\bnow\s*\(", "now()"),
    (r"\bcurrent_date\b", "current_date"),
    (r"\bcurrent_timestamp\b", "current_timestamp"),
    (r"\btablesample\b", "tablesample"),
]
_PORTABILITY = [
    (r"@>", "@> (array containment)"),
    (r"=\s*any\s*\(", "= ANY(array)"),
]


def scan_sql(sql: str) -> list[str]:
    low = sql.lower()
    return [label for pat, label in _DETERMINISM + _PORTABILITY if re.search(pat, low)]


def _sql_literals(module) -> list[str]:
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value
            if "select" in value.lower() and "from" in value.lower():
                out.append(value)
    return out


GOLD_MODULES = [lab.templates, lab.precompute]


@pytest.mark.parametrize("module", GOLD_MODULES, ids=lambda m: m.__name__)
def test_gold_sql_is_portable_and_deterministic(module):
    literals = _sql_literals(module)
    assert literals, f"no SQL literals found in {module.__name__}"
    for sql in literals:
        assert scan_sql(sql) == [], f"banned construct in {module.__name__}: {sql!r}"


def test_scanner_catches_violations():
    assert "random()" in scan_sql("SELECT * FROM t ORDER BY random()")
    assert "now()" in scan_sql("SELECT now() FROM t")
    assert "current_date" in scan_sql("SELECT current_date FROM t")
    assert "@> (array containment)" in scan_sql("SELECT 1 FROM t WHERE tags @> ARRAY['x']")
    assert scan_sql("SELECT id FROM vote_events WHERE end_date IS NOT NULL") == []
