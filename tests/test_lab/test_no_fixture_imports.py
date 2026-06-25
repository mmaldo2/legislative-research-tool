"""Structural guard: no lab/ runtime module imports the test package.

HONEST SCOPE: this prevents test<->production coupling (a hand-authored fixture literal
leaking into a gold path via import). It does NOT, by itself, enforce the hard rule
"gold only by trusted SQL" — a developer could still inline a literal directly into
templates.py/precompute.py. That rule is enforced by the gold-validation gate + code review.
"""

import ast
import pathlib

import lab


def test_lab_does_not_import_tests():
    lab_dir = pathlib.Path(lab.__file__).parent
    offenders = []
    for py in sorted(lab_dir.glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("test"):
                offenders.append(f"{py.name}: from {node.module}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("test"):
                        offenders.append(f"{py.name}: import {alias.name}")
    assert not offenders, f"lab/ must not import tests: {offenders}"
