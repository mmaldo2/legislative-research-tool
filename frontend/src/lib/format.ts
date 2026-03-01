/** Formatting helpers used across the frontend. */

/** US state/territory jurisdiction names keyed by two-letter code. */
const STATE_NAMES: Record<string, string> = {
  al: "Alabama", ak: "Alaska", az: "Arizona", ar: "Arkansas", ca: "California",
  co: "Colorado", ct: "Connecticut", de: "Delaware", fl: "Florida", ga: "Georgia",
  hi: "Hawaii", id: "Idaho", il: "Illinois", in: "Indiana", ia: "Iowa",
  ks: "Kansas", ky: "Kentucky", la: "Louisiana", me: "Maine", md: "Maryland",
  ma: "Massachusetts", mi: "Michigan", mn: "Minnesota", ms: "Mississippi",
  mo: "Missouri", mt: "Montana", ne: "Nebraska", nv: "Nevada", nh: "New Hampshire",
  nj: "New Jersey", nm: "New Mexico", ny: "New York", nc: "North Carolina",
  nd: "North Dakota", oh: "Ohio", ok: "Oklahoma", or: "Oregon", pa: "Pennsylvania",
  ri: "Rhode Island", sc: "South Carolina", sd: "South Dakota", tn: "Tennessee",
  tx: "Texas", ut: "Utah", vt: "Vermont", va: "Virginia", wa: "Washington",
  wv: "West Virginia", wi: "Wisconsin", wy: "Wyoming", dc: "District of Columbia",
  pr: "Puerto Rico", vi: "U.S. Virgin Islands", gu: "Guam", as: "American Samoa",
  mp: "Northern Mariana Islands",
};

/** Display-friendly jurisdiction name. Handles "us", "us-ca", or OCD IDs. */
export function formatJurisdiction(id: string): string {
  const lower = id.toLowerCase();
  if (lower === "us") return "United States";
  // Handle "us-ca" style IDs
  const match = lower.match(/^us-([a-z]{2})$/);
  if (match) return STATE_NAMES[match[1]] ?? id.toUpperCase();
  // Handle OCD-style IDs: extract state code from the path
  const ocdMatch = lower.match(/state:([a-z]{2})/);
  if (ocdMatch) return STATE_NAMES[ocdMatch[1]] ?? id.toUpperCase();
  return id.toUpperCase();
}

/** Map chamber identifier to a human-readable label. */
const CHAMBER_LABELS: Record<string, string> = {
  upper: "Senate",
  lower: "House",
  joint: "Joint",
  legislature: "Legislature",
};

export function formatChamber(chamber: string | null | undefined): string {
  if (!chamber) return "N/A";
  return CHAMBER_LABELS[chamber] ?? chamber.charAt(0).toUpperCase() + chamber.slice(1);
}

/** Map bill status to a human label. */
export function formatStatus(status: string | null): string {
  if (!status) return "Unknown";
  const map: Record<string, string> = {
    introduced: "Introduced",
    passed_lower: "Passed Lower",
    passed_upper: "Passed Upper",
    enacted: "Enacted",
    vetoed: "Vetoed",
    failed: "Failed",
  };
  return map[status] ?? status.charAt(0).toUpperCase() + status.slice(1);
}

/** Map status to a badge variant. */
export function statusVariant(
  status: string | null,
): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "enacted":
      return "default";
    case "failed":
    case "vetoed":
      return "destructive";
    case "passed_lower":
    case "passed_upper":
      return "secondary";
    default:
      return "outline";
  }
}

/** Map party to a short label. */
export function formatParty(party: string | null): string {
  if (!party) return "";
  const map: Record<string, string> = {
    Democratic: "D",
    Republican: "R",
    Independent: "I",
    Libertarian: "L",
    Green: "G",
  };
  return map[party] ?? party;
}

/** Truncate text to a max length, appending "..." if needed. */
export function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return text.slice(0, max).trimEnd() + "...";
}

/** Safely parse a page search param, defaulting to 1 for invalid values. */
export function parsePageParam(raw: string | string[] | undefined): number {
  const parsed = typeof raw === "string" ? parseInt(raw, 10) : NaN;
  return Number.isNaN(parsed) || parsed < 1 ? 1 : Math.min(parsed, 10000);
}

/** Validate a search mode param against allowed values. */
const SEARCH_MODES = ["keyword", "semantic", "hybrid"] as const;
export type SearchMode = (typeof SEARCH_MODES)[number];

export function parseSearchMode(raw: string | string[] | undefined): SearchMode {
  const value = typeof raw === "string" ? raw : "";
  return SEARCH_MODES.includes(value as SearchMode) ? (value as SearchMode) : "hybrid";
}

/** Check if a URL uses a safe protocol (http or https). */
export function isSafeUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}
