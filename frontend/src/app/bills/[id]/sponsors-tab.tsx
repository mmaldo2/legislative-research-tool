import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { formatParty } from "@/lib/format";
import type { SponsorResponse } from "@/types/api";

interface BillSponsorsTabProps {
  sponsors: SponsorResponse[];
}

export function BillSponsorsTab({ sponsors }: BillSponsorsTabProps) {
  if (sponsors.length === 0) {
    return (
      <p className="text-muted-foreground">No sponsors listed.</p>
    );
  }

  const primary = sponsors.filter((s) => s.classification === "primary");
  const cosponsors = sponsors.filter((s) => s.classification !== "primary");

  return (
    <div className="space-y-6">
      {primary.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Primary Sponsor{primary.length > 1 ? "s" : ""}
          </h3>
          <div className="grid gap-2 sm:grid-cols-2">
            {primary.map((s) => (
              <SponsorCard key={s.person_id} sponsor={s} />
            ))}
          </div>
        </div>
      )}

      {cosponsors.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Cosponsors ({cosponsors.length})
          </h3>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {cosponsors.map((s) => (
              <SponsorCard key={s.person_id} sponsor={s} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function SponsorCard({ sponsor }: { sponsor: SponsorResponse }) {
  return (
    <Link href={`/legislators/${encodeURIComponent(sponsor.person_id)}`}>
      <Card className="transition-colors hover:bg-accent/50">
        <CardContent className="flex items-center gap-3 py-3">
          <div className="flex-1">
            <p className="font-medium">{sponsor.name}</p>
          </div>
          {sponsor.party && (
            <Badge variant="outline" className="text-xs">
              {formatParty(sponsor.party)}
            </Badge>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
