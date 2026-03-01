import Link from "next/link";
import { listPeople } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Pagination } from "@/components/pagination";
import { formatJurisdiction, formatParty } from "@/lib/format";

interface LegislatorsListProps {
  jurisdiction?: string;
  party?: string;
  chamber?: string;
  q?: string;
  page: number;
}

export async function LegislatorsList({
  jurisdiction,
  party,
  chamber,
  q,
  page,
}: LegislatorsListProps) {
  let data;
  try {
    data = await listPeople({ jurisdiction, party, chamber, q, page, per_page: 20 });
  } catch {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
        Failed to fetch legislators. Make sure the API server is running.
      </div>
    );
  }

  if (data.data.length === 0) {
    return (
      <p className="text-center text-muted-foreground">
        No legislators found.
      </p>
    );
  }

  return (
    <div>
      <div className="space-y-2">
        {data.data.map((person) => (
          <Link
            key={person.id}
            href={`/legislators/${encodeURIComponent(person.id)}`}
          >
            <Card className="transition-colors hover:bg-accent/50">
              <CardContent className="flex items-center gap-3 py-3">
                <div className="flex-1">
                  <p className="font-medium">{person.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {person.current_chamber === "upper" ? "Senate" : "House"}
                    {person.current_district
                      ? `, District ${person.current_district}`
                      : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {person.current_jurisdiction_id && (
                    <Badge variant="secondary" className="text-xs">
                      {formatJurisdiction(person.current_jurisdiction_id)}
                    </Badge>
                  )}
                  {person.party && (
                    <Badge variant="outline" className="text-xs">
                      {formatParty(person.party)}
                    </Badge>
                  )}
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      <Pagination
        page={data.meta.page ?? page}
        perPage={data.meta.per_page ?? 20}
        totalCount={data.meta.total_count ?? 0}
      />
    </div>
  );
}
