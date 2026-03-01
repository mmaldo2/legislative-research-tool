import Link from "next/link";
import { listSessions, listBills } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BillCard } from "@/components/bill-card";
import { formatJurisdiction } from "@/lib/format";
import { Calendar, FileText } from "lucide-react";

interface JurisdictionDetailProps {
  id: string;
}

export async function JurisdictionDetail({ id }: JurisdictionDetailProps) {
  let sessions;
  let recentBills;

  try {
    [sessions, recentBills] = await Promise.all([
      listSessions({ jurisdiction: id, per_page: 20 }),
      listBills({ jurisdiction: id, per_page: 10 }),
    ]);
  } catch {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
        Failed to fetch jurisdiction details. Make sure the API server is
        running.
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold">
          {formatJurisdiction(id)}
        </h1>
        <div className="mt-2 flex items-center gap-2">
          <Badge variant="secondary">
            {sessions.meta.total_count ?? 0} sessions
          </Badge>
          <Badge variant="outline">
            {recentBills.meta.total_count ?? 0} bills
          </Badge>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="sessions">
        <TabsList>
          <TabsTrigger value="sessions">
            <Calendar className="mr-1.5 h-4 w-4" />
            Sessions
          </TabsTrigger>
          <TabsTrigger value="bills">
            <FileText className="mr-1.5 h-4 w-4" />
            Recent Bills
          </TabsTrigger>
        </TabsList>

        <TabsContent value="sessions" className="mt-4">
          {sessions.data.length === 0 ? (
            <p className="text-muted-foreground">No sessions found.</p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {sessions.data.map((s) => (
                <Card key={s.id}>
                  <CardHeader className="py-4">
                    <CardTitle className="text-base">{s.name}</CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                      <Badge variant="outline" className="text-xs font-mono">
                        {s.identifier}
                      </Badge>
                      {s.classification && (
                        <Badge variant="secondary" className="text-xs">
                          {s.classification}
                        </Badge>
                      )}
                      {s.start_date && (
                        <span>
                          {s.start_date}
                          {s.end_date ? ` — ${s.end_date}` : " — present"}
                        </span>
                      )}
                    </div>
                    <Link
                      href={`/search?jurisdiction=${encodeURIComponent(id)}`}
                      className="mt-2 inline-block text-sm text-primary hover:underline"
                    >
                      Browse bills
                    </Link>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="bills" className="mt-4">
          {recentBills.data.length === 0 ? (
            <p className="text-muted-foreground">No bills found.</p>
          ) : (
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
              <Link
                href={`/search?jurisdiction=${encodeURIComponent(id)}`}
                className="mt-4 inline-block text-sm text-primary hover:underline"
              >
                View all bills for {formatJurisdiction(id)}
              </Link>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
