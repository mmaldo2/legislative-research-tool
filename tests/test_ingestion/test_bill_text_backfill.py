"""Hermetic unit tests for the bill-text corpus backfill helpers (Slice A, Phases 1-2).

No network, no DB: these cover the pure helpers only -- the GovInfo BILLS filename parser,
the introduced-version predicate, the bill_id resolver, the USLM XML text/date extractors,
the bulkdata session listing parser, and the in-memory ZIP -> BillText-rows builder (the
filter/resolve/miss-count loop). The extractor is exercised against an embedded
BILLS-119s21is-style fixture so a regression in metadata-exclusion fails fast.
"""

import io
import zipfile
from datetime import date

from src.ingestion.govinfo import (
    _VERSION_NAMES,
    _bill_text_rows_from_zip,
    _extract_bill_text_from_uslm,
    _is_introduced,
    _parse_bills_filename,
    _parse_sessions_from_listing,
    _parse_uslm_date,
    _resolve_bill_id,
)
from src.ingestion.normalizer import generate_bill_id, normalize_identifier

# A trimmed but representative USLM bill XML (mirrors a real BILLS-119s21is.xml): a <metadata>
# block carrying dublinCore copyright boilerplate, then the <form> preamble and a <legis-body>.
# The official-title intentionally contains an "&amp;" entity to prove entities are unescaped.
SAMPLE_USLM = """<?xml version="1.0"?>
<!DOCTYPE bill PUBLIC "-//US Congress//DTDs/bill.dtd//EN" "bill.dtd">
<bill bill-stage="Introduced-in-Senate" public-private="public">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dublinCore>
      <dc:title>119 S21 IS: Test Act</dc:title>
      <dc:publisher>U.S. Senate</dc:publisher>
      <dc:date>2025-01-07</dc:date>
      <dc:rights>Pursuant to Title 17 Section 105 of the United States Code, this file is
      not subject to copyright protection and is in the public domain.</dc:rights>
    </dublinCore>
  </metadata>
  <form>
    <distribution-code display="no">II</distribution-code>
    <congress>119th CONGRESS</congress>
    <session>1st Session</session>
    <legis-num>S. 21</legis-num>
    <current-chamber>IN THE SENATE OF THE UNITED STATES</current-chamber>
    <legis-type>A BILL</legis-type>
    <official-title>To require oversight of teleworking &amp; remote employees.</official-title>
  </form>
  <legis-body>
    <section><enum>1.</enum><header>Short title</header>
      <text>This Act may be cited as the Test Act.</text>
    </section>
    <section><enum>2.</enum><header>Findings</header>
      <text>Be it enacted that the Secretary shall report.</text>
    </section>
  </legis-body>
</bill>"""


class TestParseBillsFilename:
    def test_house_and_senate_with_xml(self):
        assert _parse_bills_filename("BILLS-119hr1234ih.xml") == (119, "hr", "1234", "ih")
        assert _parse_bills_filename("BILLS-119s21is.xml") == (119, "s", "21", "is")

    def test_without_xml_suffix(self):
        assert _parse_bills_filename("BILLS-119s21is") == (119, "s", "21", "is")

    def test_case_insensitive(self):
        assert _parse_bills_filename("bills-119HR5IH.XML") == (119, "hr", "5", "ih")

    def test_multi_letter_type_is_total(self):
        # the parser is total even for compound types it will not normally be handed
        assert _parse_bills_filename("BILLS-119hjres10ih.xml") == (119, "hjres", "10", "ih")

    def test_non_introduced_versions_still_parse(self):
        # parsing is version-agnostic; the introduced filter is a separate predicate
        assert _parse_bills_filename("BILLS-119hr1rh.xml") == (119, "hr", "1", "rh")
        assert _parse_bills_filename("BILLS-119s4rs.xml") == (119, "s", "4", "rs")

    def test_rejects_billstatus_and_other_collections(self):
        assert _parse_bills_filename("BILLSTATUS-119hr1234.xml") is None
        assert _parse_bills_filename("CRPT-118srpt25.xml") is None

    def test_rejects_versionless_and_malformed(self):
        assert _parse_bills_filename("BILLS-119hr9417") is None  # no version letters
        assert _parse_bills_filename("BILLS-119hr.xml") is None  # no number
        assert _parse_bills_filename("BILLS-hr119ih") is None  # congress not leading digits
        assert _parse_bills_filename("random.txt") is None
        assert _parse_bills_filename("") is None


class TestIsIntroduced:
    def test_keeps_introduced(self):
        assert _is_introduced("ih")
        assert _is_introduced("is")

    def test_rejects_lookalikes_and_other_versions(self):
        # rih/ris END in ih/is -- an endswith filter would wrongly admit them
        for version in ("rih", "ris", "rfh", "rfs", "pcs", "es", "rs", "eh", "rh", "enr"):
            assert not _is_introduced(version), version


class TestResolveBillId:
    def test_matches_congress_api_ingest_path(self):
        # resolution must reproduce how bills are keyed (normalize_identifier + generate_bill_id)
        assert _resolve_bill_id(119, "s", "21") == generate_bill_id(
            "us", "us-119", normalize_identifier("s21")
        )
        assert _resolve_bill_id(119, "hr", "1234") == generate_bill_id("us", "us-119", "HR1234")

    def test_deterministic(self):
        assert _resolve_bill_id(119, "hr", "5") == _resolve_bill_id(119, "hr", "5")


class TestVersionNames:
    def test_mapping(self):
        assert _VERSION_NAMES["ih"] == "Introduced in House"
        assert _VERSION_NAMES["is"] == "Introduced in Senate"


class TestExtractBillTextFromUslm:
    def test_excludes_metadata_boilerplate(self):
        out = _extract_bill_text_from_uslm(SAMPLE_USLM)
        assert "Pursuant to Title 17" not in out
        assert "copyright" not in out.lower()
        assert "U.S. Senate" not in out  # dc:publisher lives in <metadata>

    def test_includes_bill_body(self):
        out = _extract_bill_text_from_uslm(SAMPLE_USLM)
        assert "A BILL" in out
        assert "119th CONGRESS" in out
        assert "Be it enacted" in out
        assert "Short title" in out

    def test_preserves_newlines(self):
        out = _extract_bill_text_from_uslm(SAMPLE_USLM)
        assert out.count("\n") > 1
        assert len(out.splitlines()) > 1

    def test_no_residual_tags_or_entities(self):
        out = _extract_bill_text_from_uslm(SAMPLE_USLM)
        assert "<" not in out and ">" not in out
        for entity in ("&lt;", "&gt;", "&amp;"):
            assert entity not in out

    def test_entities_are_unescaped(self):
        out = _extract_bill_text_from_uslm(SAMPLE_USLM)
        assert "teleworking & remote employees" in out


class TestParseUslmDate:
    def test_reads_dublincore_date(self):
        assert _parse_uslm_date(SAMPLE_USLM) == date(2025, 1, 7)

    def test_none_when_absent_or_unparseable(self):
        assert _parse_uslm_date("<bill><form><legis-type>A BILL</legis-type></form></bill>") is None
        assert _parse_uslm_date("<bill") is None  # malformed XML -> None, not a raise


class TestParseSessionsFromListing:
    def test_extracts_digit_session_dirs(self):
        listing = {
            "files": [
                {"justFileName": "1"},
                {"justFileName": "2"},
                {"justFileName": "sitemap.xml"},
                {"name": "README"},
            ]
        }
        assert _parse_sessions_from_listing(listing) == ["1", "2"]

    def test_empty_listing(self):
        assert _parse_sessions_from_listing({}) == []


def _make_zip(entries: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


_MINIMAL_USLM = (
    '<?xml version="1.0"?>'
    '<bill bill-stage="{stage}"><form><legis-type>A BILL</legis-type></form>'
    "<legis-body><section><text>Body of {tag}.</text></section></legis-body></bill>"
)


class TestBillTextRowsFromZip:
    def _zip(self):
        return _make_zip(
            {
                "BILLS-119s21is.xml": SAMPLE_USLM,  # introduced, known bill -> resolved
                "BILLS-119s500is.xml": _MINIMAL_USLM.format(  # introduced, UNKNOWN bill -> missed
                    stage="Introduced-in-Senate", tag="s500"
                ),
                "BILLS-119s99rs.xml": _MINIMAL_USLM.format(  # reported, not introduced -> skipped
                    stage="Reported-in-Senate", tag="s99"
                ),
                "BILLSTATUS-119s1.xml": "<x/>",  # different collection -> parse None
                "manifest.txt": "ignored, not xml",
            }
        )

    def test_filters_resolves_and_counts(self):
        known = {_resolve_bill_id(119, "s", "21")}
        rows, stats = _bill_text_rows_from_zip(self._zip(), 119, "1", "s", known)

        assert len(rows) == 1
        assert stats == {
            "entries": 4,  # four .xml entries (manifest.txt excluded)
            "introduced": 2,  # s21is + s500is
            "resolved": 1,  # only s21 is a known bill
            "missed": 1,  # s500 introduced but not in `known`
            "errors": 0,
        }

    def test_row_fields(self):
        known = {_resolve_bill_id(119, "s", "21")}
        rows, _ = _bill_text_rows_from_zip(self._zip(), 119, "1", "s", known)
        row = rows[0]
        assert row["bill_id"] == _resolve_bill_id(119, "s", "21")
        assert row["version_name"] == "Introduced in Senate"
        assert row["version_date"] == date(2025, 1, 7)
        assert row["content_xml"] == SAMPLE_USLM
        assert "Be it enacted" in row["content_text"]
        assert row["word_count"] > 0 and row["content_hash"]
        assert row["source_url"].endswith("#BILLS-119s21is.xml")
        assert "BILLS-119-1-s.zip" in row["source_url"]
        assert "api_key" not in row["source_url"]

    def test_remaining_caps_rows(self):
        known = {_resolve_bill_id(119, "s", "21"), _resolve_bill_id(119, "s", "500")}
        rows, stats = _bill_text_rows_from_zip(self._zip(), 119, "1", "s", known, remaining=1)
        assert len(rows) == 1  # capped, even though two bills are now known

    def test_skips_when_congress_mismatch(self):
        # a stray cross-congress entry must not resolve against this congress's bill set
        known = {_resolve_bill_id(118, "s", "21")}
        zip_bytes = _make_zip({"BILLS-118s21is.xml": SAMPLE_USLM})
        rows, stats = _bill_text_rows_from_zip(zip_bytes, 119, "1", "s", known)
        assert rows == [] and stats["introduced"] == 0
