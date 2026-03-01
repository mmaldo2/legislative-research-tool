import Link from "next/link";
import { listJurisdictions } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Pagination } from "@/components/pagination";
import { Building2, Globe, MapPin } from "lucide-react";

interface JurisdictionGridProps {
  classification?: string;
  page: number;
}

const classificationIcon: Record<string, typeof Globe> = {
  country: Globe,
  state: Building2,
  territory: MapPin,
};

export async function JurisdictionGrid({
  classification,
  page,
}: JurisdictionGridProps) {
  let data;
  try {
    data = await listJurisdictions({
      classification,
      page,
      per_page: 60,
    });
  } catch {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
        Failed to fetch jurisdictions. Make sure the API server is running.
      </div>
    );
  }

  if (data.data.length === 0) {
    return (
      <p className="text-center text-muted-foreground">
        No jurisdictions found.
      </p>
    );
  }

  return (
    <div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {data.data.map((j) => {
          const Icon = classificationIcon[j.classification] ?? Globe;
          return (
            <Link
              key={j.id}
              href={`/jurisdictions/${encodeURIComponent(j.id)}`}
            >
              <Card className="transition-colors hover:bg-accent/50">
                <CardHeader className="flex flex-row items-center gap-3 py-4">
                  <Icon className="h-5 w-5 text-muted-foreground shrink-0" />
                  <div className="flex-1 min-w-0">
                    <CardTitle className="text-base truncate">
                      {j.name}
                    </CardTitle>
                    <div className="mt-1 flex items-center gap-2">
                      <Badge variant="outline" className="text-xs font-mono">
                        {j.id}
                      </Badge>
                      <Badge variant="secondary" className="text-xs">
                        {j.classification}
                      </Badge>
                    </div>
                  </div>
                </CardHeader>
              </Card>
            </Link>
          );
        })}
      </div>

      <Pagination
        page={data.meta.page ?? page}
        perPage={data.meta.per_page ?? 60}
        totalCount={data.meta.total_count ?? 0}
      />
    </div>
  );
}
