"""Pure parsing + normalization for federal roll-call votes (no I/O).

This module is the SINGLE SOURCE OF TRUTH for the canonical vote vocabularies
(`option`, `chamber`) that the Condorcet Lab Family-1 graders import. Keeping the
parsing logic pure (string in, dict/dataclass out) lets it be unit-tested without
a DB or network, mirroring `test_normalizer.py` / `test_legiscan.py`.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime

import defusedxml.ElementTree as SafeET

# --- canonical vocabularies (graders import these) ---
CHAMBER_HOUSE = "house"
CHAMBER_SENATE = "senate"

# Maps every recorded vote string (House Yea/Nay or Aye/No by vote-type; Senate
# Yea/Nay/Present/Not Voting) to the canonical option set. Unknown -> ValueError
# so the caller quarantines the whole event rather than mis-bucketing a vote.
VOTE_OPTION_MAP: dict[str, str] = {
    "Yea": "yea",
    "Aye": "yea",
    "Yes": "yea",
    "Nay": "nay",
    "No": "nay",
    "Present": "present",
    "Not Voting": "not_voting",
}
OPTION_BUCKETS = ("yea", "nay", "present", "not_voting")

# Recognized federal bill identifier prefixes, longest-first so the regex doesn't
# mis-split (e.g. "SRES5" must not match the bare "S" prefix).
_BILL_REF_RE = re.compile(r"^(HCONRES|HJRES|SCONRES|SJRES|HRES|SRES|HR|S)\d+$")


def normalize_vote_ref(raw: str) -> str:
    """Normalize a roll-call bill reference to the stored `bills.identifier` form.

    Vote sources emit a *spaced* reference ('H R 1234', 'S. 5'); the stored
    identifier has NO internal space ('HR1234', 'S5') because govinfo builds it
    as ``normalize_identifier(f"{type}{number}")``. We therefore strip ALL
    whitespace and dots (NOT ``normalize_identifier``, which only collapses
    existing whitespace and would preserve the space -> a different hash -> miss).
    """
    return re.sub(r"[\s.]", "", raw or "").upper()


def is_bill_ref(legis_num: str | None) -> bool:
    """True if `legis_num` is a resolvable bill reference (not a procedural sentinel
    like 'QUORUM' / 'JOURNAL' / 'MOTION')."""
    if not legis_num:
        return False
    return bool(_BILL_REF_RE.match(normalize_vote_ref(legis_num)))


def normalize_vote_option(raw: str | None) -> str:
    """Map a raw recorded-vote string to the canonical option. Unknown -> ValueError."""
    key = (raw or "").strip()
    if key not in VOTE_OPTION_MAP:
        raise ValueError(f"unknown vote option string: {raw!r}")
    return VOTE_OPTION_MAP[key]


def house_years_for_congress(congress: int) -> list[int]:
    """Calendar years a House Congress spans (rolls reset per year). 118 -> [2023, 2024]."""
    base = 2007 + 2 * (congress - 110)
    return [base, base + 1]


def house_vote_event_id(congress: int, year: int, roll: int) -> str:
    """Deterministic, human-readable PK. Zero-padding width (:04d) is part of the contract."""
    return f"us-house-{congress}-{year}-{roll:04d}"


def senate_vote_event_id(congress: int, session: int, vote: int) -> str:
    """Deterministic, human-readable PK. Zero-padding width (:05d) is part of the contract."""
    return f"us-senate-{congress}-{session}-{vote:05d}"


def parse_house_action_date(raw: str | None) -> date | None:
    """Parse the House `<action-date>` form 'DD-Mon-YYYY' (e.g. '20-Dec-2024')."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw.strip(), "%d-%b-%Y").date()
    except ValueError:
        return None


def parse_house_index(html: str) -> int:
    """Return the highest roll number referenced in a clerk.house.gov year index
    page, or 0 if none found."""
    nums = [int(n) for n in re.findall(r"rollnumber=(\d+)", html or "")]
    return max(nums) if nums else 0


@dataclass
class ParsedVote:
    """Normalized roll-call vote, independent of DB resolution."""

    chamber: str
    congress: int
    session: str | None
    rollcall_num: int
    legis_num: str | None  # raw, e.g. 'H R 10545' or a sentinel like 'QUORUM'
    vote_question: str | None
    vote_type: str | None
    vote_result: str | None
    vote_date: date | None
    official: dict[str, int] = field(default_factory=dict)  # canonical-bucket -> count
    casts: list[tuple[str, str]] = field(default_factory=list)  # (bioguide name-id, raw vote)


def parse_house_roll_xml(xml_text: str) -> ParsedVote | None:
    """Parse one clerk.house.gov roll-call XML into a ParsedVote. None if unparseable."""
    try:
        root = SafeET.fromstring(xml_text)
    except SafeET.ParseError:
        return None
    meta = root.find("vote-metadata")
    if meta is None:
        return None

    def _txt(tag: str) -> str | None:
        v = meta.findtext(tag)
        return v.strip() if v else None

    try:
        congress = int(_txt("congress") or "")
        rollcall_num = int(_txt("rollcall-num") or "")
    except ValueError:
        return None

    tbv = meta.find(".//totals-by-vote")
    official: dict[str, int] = {}
    if tbv is not None:
        official = {
            "yea": int(tbv.findtext("yea-total", "0") or 0),
            "nay": int(tbv.findtext("nay-total", "0") or 0),
            "present": int(tbv.findtext("present-total", "0") or 0),
            "not_voting": int(tbv.findtext("not-voting-total", "0") or 0),
        }

    casts: list[tuple[str, str]] = []
    for rv in root.findall(".//recorded-vote"):
        leg = rv.find("legislator")
        if leg is None:
            continue
        name_id = leg.get("name-id")
        vote = (rv.findtext("vote") or "").strip()
        if name_id and vote:
            casts.append((name_id, vote))

    return ParsedVote(
        chamber=CHAMBER_HOUSE,
        congress=congress,
        session=_txt("session"),
        rollcall_num=rollcall_num,
        legis_num=_txt("legis-num"),
        vote_question=_txt("vote-question"),
        vote_type=_txt("vote-type"),
        vote_result=_txt("vote-result"),
        vote_date=parse_house_action_date(_txt("action-date")),
        official=official,
        casts=casts,
    )


def build_member_map(
    rows: list[tuple[str, str]],
) -> tuple[dict[str, str], set[str]]:
    """Build a collision-safe {bioguide -> people.id} map from (people.id, bioguide_id) rows.

    `people.bioguide_id` has no unique constraint and the table holds duplicate
    person rows (a canonical id==bioguide row plus a GovInfo hash-PK row for the
    same member). Resolution preference: the canonical row where id==bioguide;
    else the lone row; else (>1 row, none canonical) a true collision -> excluded.
    Returns (mapping, collisions).
    """
    by_bio: dict[str, set[str]] = {}
    for people_id, bioguide in rows:
        if bioguide:
            by_bio.setdefault(bioguide, set()).add(people_id)
    mapping: dict[str, str] = {}
    collisions: set[str] = set()
    for bio, ids in by_bio.items():
        if bio in ids:  # canonical congress_legislators row
            mapping[bio] = bio
        elif len(ids) == 1:  # lone hash-PK row
            mapping[bio] = next(iter(ids))
        else:  # ambiguous: refuse to resolve (never guess which person)
            collisions.add(bio)
    return mapping, collisions


def reconcile(computed: dict[str, int], dropped: dict[str, int], official: dict[str, int]) -> bool:
    """Per-bucket reconciliation: for every option, resolved casts + dropped
    (unresolved members, bucketed by their parsed option) must equal the official
    sub-total. Guards against duplicate/misclassified casts an aggregate check misses."""
    for o in OPTION_BUCKETS:
        if computed.get(o, 0) + dropped.get(o, 0) != official.get(o, 0):
            return False
    return True


# --- Senate (senate.gov LIS) ---

_SENATE_DATE_RE = re.compile(r"^([A-Za-z]+ \d+, \d{4})")


def build_lis_bioguide_map(legislators: list[dict]) -> dict[str, str]:
    """Build {lis_member_id -> bioguide} from congress-legislators JSON objects.
    Senate roll-call XML keys members by LIS id, not bioguide; this is the crosswalk."""
    mapping: dict[str, str] = {}
    for leg in legislators:
        ids = leg.get("id", {})
        lis, bioguide = ids.get("lis"), ids.get("bioguide")
        if lis and bioguide:
            mapping[lis] = bioguide
    return mapping


def parse_senate_date(raw: str | None) -> date | None:
    """Parse the Senate detail date 'Month D, YYYY,  HH:MM AM' -> date (date part only,
    no timezone conversion; the full-year detail date avoids the menu's Dec/Jan ambiguity)."""
    if not raw:
        return None
    m = _SENATE_DATE_RE.match(raw.strip())
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%B %d, %Y").date()
    except ValueError:
        return None


def parse_senate_vote_numbers(xml_text: str) -> list[int]:
    """Extract the sorted, de-duplicated vote numbers from a Senate vote-menu XML."""
    try:
        root = SafeET.fromstring(xml_text)
    except SafeET.ParseError:
        return []
    nums: set[int] = set()
    for vn in root.findall(".//vote_number"):
        try:
            nums.add(int((vn.text or "").strip()))
        except (TypeError, ValueError):
            continue
    return sorted(nums)


def parse_senate_vote_xml(xml_text: str) -> ParsedVote | None:
    """Parse one senate.gov roll-call detail XML into a ParsedVote (casts keyed by LIS id)."""
    try:
        root = SafeET.fromstring(xml_text)
    except SafeET.ParseError:
        return None
    try:
        congress = int((root.findtext("congress") or "").strip())
        vote_number = int((root.findtext("vote_number") or "").strip())
    except ValueError:
        return None

    dtype = (root.findtext("document/document_type") or "").strip()
    dnum = (root.findtext("document/document_number") or "").strip()
    dname = (root.findtext("document/document_name") or "").strip()
    legis_num = dname or (f"{dtype} {dnum}".strip() or None)

    official: dict[str, int] = {}
    count = root.find("count")
    if count is not None:

        def _ct(tag: str) -> int:
            t = count.findtext(tag)
            return int(t) if t and t.strip() else 0

        official = {
            "yea": _ct("yeas"),
            "nay": _ct("nays"),
            "present": _ct("present"),
            "not_voting": _ct("absent"),
        }

    casts: list[tuple[str, str]] = []
    for m in root.findall(".//member"):
        lis = (m.findtext("lis_member_id") or "").strip()
        vc = (m.findtext("vote_cast") or "").strip()
        if lis and vc:
            casts.append((lis, vc))

    def _opt(tag: str) -> str | None:
        v = root.findtext(tag)
        return v.strip() if v else None

    return ParsedVote(
        chamber=CHAMBER_SENATE,
        congress=congress,
        session=(root.findtext("session") or "").strip() or None,
        rollcall_num=vote_number,
        legis_num=legis_num,
        vote_question=_opt("question"),
        vote_type=None,
        vote_result=_opt("vote_result"),
        vote_date=parse_senate_date(root.findtext("vote_date")),
        official=official,
        casts=casts,
    )
