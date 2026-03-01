import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { getPerson, listBills } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BillCard } from "@/components/bill-card";
import { formatJurisdiction, formatParty } from "@/lib/format";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  try {
    const person = await getPerson(decodeURIComponent(id));
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
    person = await getPerson(decodeURIComponent(id));
  } catch {
    notFound();
  }

  // Fetch bills sponsored by this person (the API doesn't have a sponsor filter,
  // so we show jurisdiction bills as context — a future enhancement)
  let recentBills;
  try {
    recentBills = person.current_jurisdiction_id
      ? await listBills({
          jurisdiction: person.current_jurisdiction_id,
          per_page: 10,
        })
      : null;
  } catch {
    recentBills = null;
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
              {person.current_chamber === "upper" ? "Senate" : "House"}
            </Badge>
          )}
          {person.current_district && (
            <Badge variant="outline">
              District {person.current_district}
            </Badge>
          )}
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="info">
        <TabsList>
          <TabsTrigger value="info">Info</TabsTrigger>
          <TabsTrigger value="bills">Recent Bills</TabsTrigger>
        </TabsList>

        <TabsContent value="info" className="mt-4">
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
                  <dd>
                    {person.current_chamber === "upper"
                      ? "Senate"
                      : person.current_chamber === "lower"
                        ? "House"
                        : "N/A"}
                  </dd>
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
        </TabsContent>

        <TabsContent value="bills" className="mt-4">
          {recentBills && recentBills.data.length > 0 ? (
            <div className="space-y-3">
              {recentBills.data.map((bill) => (
                <BillCard
                  key={bill.id}
                  id={bill.id}
                  identifier={bill.identifier}
                  title={bill.title}
                  jurisdiction_id={bill.jurisdiction_id}
                  status={bill.status}
                />
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground">
              No recent bills available for this legislator&apos;s jurisdiction.
            </p>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
