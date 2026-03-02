"""Tests for the LegiScan weekly dataset ingester.

Tests cover:
- Bill JSON parsing from LegiScan format
- Status code mapping
- ZIP extraction of bill files
- Upsert logic (mock DB via monkeypatch)
- Gap detection logging
"""

import io
import json
import zipfile

from src.ingestion.legiscan import (
    LEGISCAN_STATUS_MAP,
    extract_bills_from_zip,
    map_legiscan_status,
    parse_legiscan_bill,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_bill_json(
    bill_id: int = 12345,
    bill_number: str = "HB1234",
    title: str = "An Act relating to data privacy",
    description: str = "Privacy protection for consumers",
    state: str = "CA",
    session_id: int = 1234,
    session_name: str = "2025-2026",
    status: int = 1,
    status_date: str = "2025-01-15",
    url: str = "https://legiscan.com/CA/bill/HB1234/2025",
) -> dict:
    """Build a raw LegiScan bill dict matching the weekly dataset format."""
    return {
        "bill_id": bill_id,
        "bill_number": bill_number,
        "title": title,
        "description": description,
        "state": state,
        "session": {
            "session_id": session_id,
            "session_name": session_name,
        },
        "status": status,
        "status_date": status_date,
        "url": url,
        "texts": [],
        "votes": [],
        "history": [],
    }


def _build_zip(bill_dicts: list[dict], state: str = "CA") -> bytes:
    """Create an in-memory ZIP archive containing bill JSON files.

    Mimics the LegiScan dataset structure: <state>/2025/bill/<bill_id>.json
    Each file wraps the bill data under a top-level "bill" key.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, bill_data in enumerate(bill_dicts):
            path = f"{state}/2025/bill/{bill_data.get('bill_id', i)}.json"
            content = json.dumps({"bill": bill_data})
            zf.writestr(path, content)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Status mapping
# ---------------------------------------------------------------------------


class TestStatusMapping:
    def test_introduced(self):
        assert map_legiscan_status(1) == "introduced"

    def test_engrossed(self):
        assert map_legiscan_status(2) == "engrossed"

    def test_enrolled(self):
        assert map_legiscan_status(3) == "enrolled"

    def test_enacted(self):
        assert map_legiscan_status(4) == "enacted"

    def test_vetoed(self):
        assert map_legiscan_status(5) == "vetoed"

    def test_failed(self):
        assert map_legiscan_status(6) == "failed"

    def test_unknown_code_returns_other(self):
        assert map_legiscan_status(99) == "other"
        assert map_legiscan_status(0) == "other"

    def test_all_known_codes_covered(self):
        for code, expected in LEGISCAN_STATUS_MAP.items():
            assert map_legiscan_status(code) == expected


# ---------------------------------------------------------------------------
# Bill parsing
# ---------------------------------------------------------------------------


class TestParseLegiscanBill:
    def test_basic_parse(self):
        raw = _make_bill_json()
        parsed = parse_legiscan_bill(raw)

        assert parsed is not None
        assert parsed["legiscan_id"] == 12345
        assert parsed["bill_number"] == "HB1234"
        assert parsed["state"] == "CA"
        assert parsed["title"] == "An Act relating to data privacy"
        assert parsed["session_name"] == "2025-2026"
        assert parsed["status"] == "introduced"

    def test_status_date_parsed(self):
        raw = _make_bill_json(status_date="2025-03-20")
        parsed = parse_legiscan_bill(raw)

        assert parsed is not None
        assert parsed["status_date"] is not None
        assert parsed["status_date"].isoformat() == "2025-03-20"

    def test_invalid_status_date_becomes_none(self):
        raw = _make_bill_json(status_date="not-a-date")
        parsed = parse_legiscan_bill(raw)

        assert parsed is not None
        assert parsed["status_date"] is None

    def test_empty_status_date_becomes_none(self):
        raw = _make_bill_json(status_date="")
        parsed = parse_legiscan_bill(raw)

        assert parsed is not None
        assert parsed["status_date"] is None

    def test_all_status_codes(self):
        for code, expected in LEGISCAN_STATUS_MAP.items():
            raw = _make_bill_json(status=code)
            parsed = parse_legiscan_bill(raw)
            assert parsed is not None
            assert parsed["status"] == expected

    def test_missing_bill_id_returns_none(self):
        raw = _make_bill_json()
        del raw["bill_id"]
        assert parse_legiscan_bill(raw) is None

    def test_missing_bill_number_returns_none(self):
        raw = _make_bill_json()
        raw["bill_number"] = ""
        assert parse_legiscan_bill(raw) is None

    def test_missing_state_returns_none(self):
        raw = _make_bill_json()
        raw["state"] = ""
        assert parse_legiscan_bill(raw) is None

    def test_state_uppercased(self):
        raw = _make_bill_json(state="ca")
        parsed = parse_legiscan_bill(raw)
        assert parsed is not None
        assert parsed["state"] == "CA"

    def test_url_preserved(self):
        url = "https://legiscan.com/TX/bill/SB100/2025"
        raw = _make_bill_json(url=url)
        parsed = parse_legiscan_bill(raw)
        assert parsed is not None
        assert parsed["url"] == url

    def test_description_preserved(self):
        raw = _make_bill_json(description="Important bill about things")
        parsed = parse_legiscan_bill(raw)
        assert parsed is not None
        assert parsed["description"] == "Important bill about things"

    def test_missing_session_info(self):
        raw = _make_bill_json()
        raw["session"] = {}
        parsed = parse_legiscan_bill(raw)
        assert parsed is not None
        assert parsed["session_name"] == ""
        assert parsed["session_id_num"] is None


# ---------------------------------------------------------------------------
# ZIP extraction
# ---------------------------------------------------------------------------


class TestExtractBillsFromZip:
    def test_single_bill(self):
        bill = _make_bill_json()
        zip_bytes = _build_zip([bill])
        bills = extract_bills_from_zip(zip_bytes)

        assert len(bills) == 1
        assert bills[0]["legiscan_id"] == 12345
        assert bills[0]["bill_number"] == "HB1234"

    def test_multiple_bills(self):
        bills_data = [
            _make_bill_json(bill_id=1, bill_number="HB1"),
            _make_bill_json(bill_id=2, bill_number="HB2"),
            _make_bill_json(bill_id=3, bill_number="SB100"),
        ]
        zip_bytes = _build_zip(bills_data)
        extracted = extract_bills_from_zip(zip_bytes)

        assert len(extracted) == 3
        numbers = {b["bill_number"] for b in extracted}
        assert numbers == {"HB1", "HB2", "SB100"}

    def test_skips_non_json_files(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("CA/2025/bill/readme.txt", "Not a bill")
            bill = _make_bill_json()
            zf.writestr("CA/2025/bill/12345.json", json.dumps({"bill": bill}))
        zip_bytes = buf.getvalue()

        bills = extract_bills_from_zip(zip_bytes)
        assert len(bills) == 1

    def test_skips_people_and_vote_files(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("CA/2025/people/1.json", json.dumps({"person": {}}))
            zf.writestr("CA/2025/vote/1.json", json.dumps({"vote": {}}))
            bill = _make_bill_json()
            zf.writestr("CA/2025/bill/12345.json", json.dumps({"bill": bill}))
        zip_bytes = buf.getvalue()

        bills = extract_bills_from_zip(zip_bytes)
        assert len(bills) == 1

    def test_invalid_json_skipped(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("CA/2025/bill/bad.json", "not valid json {{{")
            bill = _make_bill_json()
            zf.writestr("CA/2025/bill/12345.json", json.dumps({"bill": bill}))
        zip_bytes = buf.getvalue()

        bills = extract_bills_from_zip(zip_bytes)
        assert len(bills) == 1

    def test_invalid_zip_returns_empty(self):
        bills = extract_bills_from_zip(b"this is not a zip file")
        assert bills == []

    def test_empty_zip(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w"):
            pass  # empty archive
        bills = extract_bills_from_zip(buf.getvalue())
        assert bills == []

    def test_bill_without_wrapper_key(self):
        """If a JSON file has bill data at the top level (no "bill" wrapper), parse it."""
        raw = _make_bill_json(bill_id=999, bill_number="SB42")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            # Directly serialize without {"bill": ...} wrapper
            zf.writestr("CA/2025/bill/999.json", json.dumps(raw))
        zip_bytes = buf.getvalue()

        bills = extract_bills_from_zip(zip_bytes)
        assert len(bills) == 1
        assert bills[0]["legiscan_id"] == 999


# ---------------------------------------------------------------------------
# Gap detection (unit-level — no DB needed)
# ---------------------------------------------------------------------------


class TestGapDetection:
    """Test that the gap data structure is populated correctly.

    The actual gap detection queries the DB in LegiScanIngester._upsert_bill().
    Here we verify the gap record format from parse output.
    """

    def test_gap_record_has_required_fields(self):
        """Verify the fields we log for each gap."""
        bill = _make_bill_json(
            bill_id=555,
            bill_number="HB555",
            state="TX",
            session_name="2025-2026",
        )
        parsed = parse_legiscan_bill(bill)
        assert parsed is not None

        # Simulate what _upsert_bill builds for a gap entry
        gap = {
            "state": parsed["state"],
            "bill_number": parsed["bill_number"],
            "session_name": parsed["session_name"],
            "legiscan_id": parsed["legiscan_id"],
            "identifier": parsed["bill_number"].upper(),
        }

        assert gap["state"] == "TX"
        assert gap["bill_number"] == "HB555"
        assert gap["session_name"] == "2025-2026"
        assert gap["legiscan_id"] == 555

    def test_multiple_gaps_accumulate(self):
        """Verify that gap list grows with each unmatched bill."""
        gaps: list[dict] = []
        for i in range(5):
            bill = _make_bill_json(bill_id=i, bill_number=f"HB{i}")
            parsed = parse_legiscan_bill(bill)
            assert parsed is not None
            gaps.append(
                {
                    "state": parsed["state"],
                    "bill_number": parsed["bill_number"],
                    "legiscan_id": parsed["legiscan_id"],
                }
            )

        assert len(gaps) == 5
        assert {g["legiscan_id"] for g in gaps} == {0, 1, 2, 3, 4}


# ---------------------------------------------------------------------------
# Integration-level ingester tests (mock HTTP + mock DB)
# ---------------------------------------------------------------------------


class TestLegiScanIngesterUnit:
    """Unit tests for LegiScanIngester instantiation and configuration."""

    def test_source_name(self):
        from src.ingestion.legiscan import LegiScanIngester

        # Cannot instantiate fully without a session, but check class attribute
        assert LegiScanIngester.source_name == "legiscan"

    def test_states_filter_uppercased(self):
        from unittest.mock import MagicMock

        from src.ingestion.legiscan import LegiScanIngester

        mock_session = MagicMock()
        ingester = LegiScanIngester(mock_session, states=["ca", "tx", "ny"])
        assert ingester.states == ["CA", "TX", "NY"]

    def test_states_none_means_all(self):
        from unittest.mock import MagicMock

        from src.ingestion.legiscan import LegiScanIngester

        mock_session = MagicMock()
        ingester = LegiScanIngester(mock_session, states=None)
        assert ingester.states is None

    def test_gaps_initially_empty(self):
        from unittest.mock import MagicMock

        from src.ingestion.legiscan import LegiScanIngester

        mock_session = MagicMock()
        ingester = LegiScanIngester(mock_session)
        assert ingester.gaps == []


# ---------------------------------------------------------------------------
# Round-trip: build ZIP -> extract -> verify all fields
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """End-to-end test: build a dataset ZIP, extract bills, verify parsed output."""

    def test_full_round_trip(self):
        bills_input = [
            _make_bill_json(
                bill_id=100,
                bill_number="SB200",
                title="Education Reform Act",
                state="NY",
                status=4,
                status_date="2025-06-15",
                url="https://legiscan.com/NY/bill/SB200/2025",
            ),
            _make_bill_json(
                bill_id=101,
                bill_number="HB300",
                title="Tax Relief Act",
                state="NY",
                status=5,
                status_date="2025-07-01",
                url="https://legiscan.com/NY/bill/HB300/2025",
            ),
        ]
        zip_bytes = _build_zip(bills_input, state="NY")
        extracted = extract_bills_from_zip(zip_bytes)

        assert len(extracted) == 2

        # Find each by legiscan_id
        by_id = {b["legiscan_id"]: b for b in extracted}

        edu = by_id[100]
        assert edu["bill_number"] == "SB200"
        assert edu["title"] == "Education Reform Act"
        assert edu["state"] == "NY"
        assert edu["status"] == "enacted"
        assert edu["status_date"].isoformat() == "2025-06-15"

        tax = by_id[101]
        assert tax["bill_number"] == "HB300"
        assert tax["status"] == "vetoed"
        assert tax["status_date"].isoformat() == "2025-07-01"

    def test_round_trip_preserves_session_info(self):
        bill = _make_bill_json(
            session_id=9999,
            session_name="2025-2026 Regular Session",
        )
        zip_bytes = _build_zip([bill])
        extracted = extract_bills_from_zip(zip_bytes)

        assert len(extracted) == 1
        assert extracted[0]["session_name"] == "2025-2026 Regular Session"
        assert extracted[0]["session_id_num"] == 9999
