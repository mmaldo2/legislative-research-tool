import { Suspense, cache } from "react";
import { notFound } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import type { Metadata } from "next";
import { ApiError, getPerson, getPersonStats } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiErrorBanner } from "@/components/api-error";
import { formatChamber, formatJurisdiction, formatParty } from "@/lib/format";
import { FileText, User, Vote } from "lucide-react";
import { SponsoredBillsTab } from "./sponsored-bills-tab";
import { VotingRecordTab } from "./voting-record-tab";

const getPersonCached = cache((id: string) => getPerson(id));

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
  let stats;
  let statsError: string | null = null;

  try {
    person = await getPersonCached(id);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      notFound();
    }
    throw err;
  }

  try {
    stats = await getPersonStats(id);
  } catch {
    statsError = "Failed to load legislator statistics.";
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-start gap-5">
          {person.image_url && (
            <Image
              src={person.image_url}
              alt={`Photo of ${person.name}`}
              width={96}
              height={96}
              className="h-24 w-24 shrink-0 rounded-lg border object-cover"
              unoptimized
            />
          )}
          <div className="flex-1">
            <h1 className="text-2xl font-bold">{person.name}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {person.party && (
                <Badge variant="outline">
                  {person.party} ({formatParty(person.party)})
                </Badge>
              )}
              {person.current_jurisdiction_id && (
                <Link href={`/jurisdictions/${encodeURIComponent(person.current_jurisdiction_id)}`}>
                  <Badge variant="secondary" className="cursor-pointer">
                    {formatJurisdiction(person.current_jurisdiction_id)}
                  </Badge>
                </Link>
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
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="profile">
        <TabsList>
          <TabsTrigger value="profile">
            <User className="mr-1.5 h-4 w-4" />
            Profile
          </TabsTrigger>
          <TabsTrigger value="bills">
            <FileText className="mr-1.5 h-4 w-4" />
            Sponsored Bills
          </TabsTrigger>
          <TabsTrigger value="votes">
            <Vote className="mr-1.5 h-4 w-4" />
            Voting Record
          </TabsTrigger>
        </TabsList>

        {/* Profile Tab */}
        <TabsContent value="profile" className="mt-4 space-y-6">
          {/* Stats Card */}
          {statsError ? (
            <ApiErrorBanner message={statsError} />
          ) : stats ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Activity Statistics</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <div className="rounded-lg border p-4 text-center">
                    <p className="text-2xl font-bold">{stats.bills_sponsored}</p>
                    <p className="text-sm text-muted-foreground">Bills Sponsored</p>
                  </div>
                  <div className="rounded-lg border p-4 text-center">
                    <p className="text-2xl font-bold">{stats.bills_cosponsored}</p>
                    <p className="text-sm text-muted-foreground">Bills Cosponsored</p>
                  </div>
                  <div className="rounded-lg border p-4 text-center">
                    <p className="text-2xl font-bold">{stats.votes_cast}</p>
                    <p className="text-sm text-muted-foreground">Votes Cast</p>
                  </div>
                  <div className="rounded-lg border p-4 text-center">
                    <p className="text-2xl font-bold">
                      {stats.vote_participation_rate !== null
                        ? `${(stats.vote_participation_rate * 100).toFixed(1)}%`
                        : "N/A"}
                    </p>
                    <p className="text-sm text-muted-foreground">Participation Rate</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : null}

          {/* Details Grid */}
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
                    {person.current_jurisdiction_id ? (
                      <Link
                        href={`/jurisdictions/${encodeURIComponent(person.current_jurisdiction_id)}`}
                        className="text-primary hover:underline"
                      >
                        {formatJurisdiction(person.current_jurisdiction_id)}
                      </Link>
                    ) : (
                      "N/A"
                    )}
                  </dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Sponsored Bills Tab */}
        <TabsContent value="bills" className="mt-4">
          <Suspense
            fallback={
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="h-20 animate-pulse rounded-lg border bg-muted/30" />
                ))}
              </div>
            }
          >
            <SponsoredBillsTab personId={id} />
          </Suspense>
        </TabsContent>

        {/* Voting Record Tab */}
        <TabsContent value="votes" className="mt-4">
          <Suspense
            fallback={
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="h-16 animate-pulse rounded-lg border bg-muted/30" />
                ))}
              </div>
            }
          >
            <VotingRecordTab personId={id} />
          </Suspense>
        </TabsContent>
      </Tabs>
    </div>
  );
}
