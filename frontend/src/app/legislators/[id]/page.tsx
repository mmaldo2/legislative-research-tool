import { cache } from "react";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { ApiError, getPerson } from "@/lib/api";

const getPersonCached = cache((id: string) => getPerson(id));
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatChamber, formatJurisdiction, formatParty } from "@/lib/format";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  try {
    const person = await getPersonCached(id);
    return { title: `${person.name} | Legislative Research Tool` };
  } catch {
    return { title: "Legislator Not Found" };
  }
}

export default async function LegislatorPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let person;
  try {
    person = await getPersonCached(id);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      notFound();
    }
    throw err;
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold">{person.name}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {person.party && (
            <Badge variant="outline">
              {person.party} ({formatParty(person.party)})
            </Badge>
          )}
          {person.current_jurisdiction_id && (
            <Badge variant="secondary">
              {formatJurisdiction(person.current_jurisdiction_id)}
            </Badge>
          )}
          {person.current_chamber && (
            <Badge variant="secondary">
              {formatChamber(person.current_chamber)}
            </Badge>
          )}
          {person.current_district && (
            <Badge variant="outline">
              District {person.current_district}
            </Badge>
          )}
        </div>
      </div>

      {/* Legislator details */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Legislator Details</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-3 sm:grid-cols-2">
            <div>
              <dt className="text-sm font-medium text-muted-foreground">
                Name
              </dt>
              <dd>{person.name}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-muted-foreground">
                Party
              </dt>
              <dd>{person.party ?? "N/A"}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-muted-foreground">
                Chamber
              </dt>
              <dd>{formatChamber(person.current_chamber)}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-muted-foreground">
                District
              </dt>
              <dd>{person.current_district ?? "N/A"}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-muted-foreground">
                Jurisdiction
              </dt>
              <dd>
                {person.current_jurisdiction_id
                  ? formatJurisdiction(person.current_jurisdiction_id)
                  : "N/A"}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
