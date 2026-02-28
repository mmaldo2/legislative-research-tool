"""Shared normalization utilities for converting upstream data to canonical schema."""

import hashlib
import re
import uuid


def generate_bill_id(jurisdiction_id: str, session_id: str, identifier: str) -> str:
    """Generate a stable internal bill ID from jurisdiction + session + identifier."""
    key = f"{jurisdiction_id}:{session_id}:{identifier}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def generate_text_id(bill_id: str, version_name: str) -> str:
    """Generate a stable text version ID."""
    key = f"{bill_id}:{version_name}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def generate_uuid() -> str:
    return str(uuid.uuid4())


def content_hash(text: str) -> str:
    """SHA-256 hash of text content for dedup/change detection."""
    return hashlib.sha256(text.encode()).hexdigest()


def normalize_bill_status(raw_status: str) -> str:
    """Normalize various status strings to a canonical set."""
    status_lower = raw_status.lower().strip()
    # Order matters — more specific patterns first, then general ones.
    # "failed" must come before "committee" so "failed in committee" → "failed".
    status_map = [
        ("introduced", "introduced"),
        ("passed house", "passed_lower"),
        ("passed senate", "passed_upper"),
        ("passed lower", "passed_lower"),
        ("passed upper", "passed_upper"),
        ("enrolled", "enrolled"),
        ("enacted", "enacted"),
        ("signed", "enacted"),
        ("became law", "enacted"),
        ("vetoed", "vetoed"),
        ("failed", "failed"),
        ("dead", "failed"),
        ("withdrawn", "withdrawn"),
        ("referred to", "in_committee"),
        ("committee", "in_committee"),
    ]
    for pattern, normalized in status_map:
        if pattern in status_lower:
            return normalized
    return "other"


def normalize_identifier(raw_id: str) -> str:
    """Normalize bill identifier format (e.g., 'H.R. 1234' → 'HR 1234')."""
    cleaned = re.sub(r"\.", "", raw_id)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.upper()


def word_count(text: str | None) -> int | None:
    if not text:
        return None
    return len(text.split())
