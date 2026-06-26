"""Seeded, engine-portable instance sampling.

Sampling is deterministic via a SHA-256 hash order over a candidate id LIST pulled
into Python (never an engine `random()`/`TABLESAMPLE`, never a 5.4M-row scan): we
fetch only the small candidate-id column (<=~13.8K events / <=~1.5K people), order
by `sha256(f"{seed}:{id}")`, and take the first N. Identical across Postgres/DuckDB.
"""

import hashlib


def _hkey(seed: int, value: str) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode()).hexdigest()


def hash_order(ids: list[str], seed: int) -> list[str]:
    return sorted(ids, key=lambda i: _hkey(seed, i))


def sample(ids: list[str], n: int, seed: int) -> list[str]:
    """Deterministically pick up to N ids by seeded hash order."""
    return hash_order(ids, seed)[:n]


def pick_one(values: list[str], seed: int) -> str:
    """Deterministically pick a single id from a small set (e.g. one voter per event)."""
    return min(values, key=lambda v: _hkey(seed, v))
