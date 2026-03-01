/** Formatting helpers used across the frontend. */

/** Display-friendly jurisdiction name from ID like "us-ca" → "US-CA". */
export function formatJurisdiction(id: string): string {
  return id.toUpperCase().replace(/-/g, "-");
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
