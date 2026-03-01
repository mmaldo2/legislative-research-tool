import { getJurisdictionStats } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiErrorBanner } from "@/components/api-error";
import { formatStatus, statusVariant } from "@/lib/format";

interface StatsTabProps {
  jurisdictionId: string;
}

export async function StatsTab({ jurisdictionId }: StatsTabProps) {
  let stats;

  try {
    stats = await getJurisdictionStats(jurisdictionId);
  } catch {
    return (
      <ApiErrorBanner message="Failed to load jurisdiction statistics. Make sure the API server is running." />
    );
  }

  if (
    stats.total_bills === 0 &&
    stats.total_legislators === 0 &&
    Object.keys(stats.bills_by_status).length === 0
  ) {
    return (
      <p className="text-muted-foreground">
        No statistics available for this jurisdiction.
      </p>
    );
  }

  // Determine the top status (the one with the most bills)
  const statusEntries = Object.entries(stats.bills_by_status);
  const topStatus =
    statusEntries.length > 0
      ? statusEntries.reduce((best, curr) =>
          curr[1] > best[1] ? curr : best,
        )
      : null;

  // Max count for proportional bar widths
  const maxStatusCount =
    statusEntries.length > 0
      ? Math.max(...statusEntries.map(([, count]) => count))
      : 1;

  return (
    <div className="space-y-6">
      {/* Stats cards row */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Bills
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total_bills.toLocaleString()}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Legislators
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total_legislators.toLocaleString()}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Top Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            {topStatus ? (
              <div className="flex items-center gap-2">
                <Badge variant={statusVariant(topStatus[0])}>
                  {formatStatus(topStatus[0])}
                </Badge>
                <span className="text-sm text-muted-foreground">
                  ({topStatus[1].toLocaleString()} bills)
                </span>
              </div>
            ) : (
              <span className="text-sm text-muted-foreground">N/A</span>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Bills by Status */}
      {statusEntries.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Bills by Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {statusEntries
                .sort(([, a], [, b]) => b - a)
                .map(([status, count]) => (
                  <div key={status} className="space-y-1">
                    <div className="flex items-center justify-between text-sm">
                      <Badge variant={statusVariant(status)} className="text-xs">
                        {formatStatus(status)}
                      </Badge>
                      <span className="font-medium tabular-nums">
                        {count.toLocaleString()}
                      </span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-muted">
                      <div
                        className="h-2 rounded-full bg-primary transition-all"
                        style={{
                          width: `${(count / maxStatusCount) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Bills by Session */}
      {stats.bills_by_session.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Bills by Session</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Session Name</TableHead>
                  <TableHead className="text-right">Bill Count</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stats.bills_by_session.map((session) => (
                  <TableRow key={session.session_id}>
                    <TableCell>{session.session_name}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {session.bill_count.toLocaleString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Top Subjects */}
      {stats.top_subjects.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top Subjects</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {stats.top_subjects.map((item) => (
                <Badge key={item.subject} variant="secondary" className="text-xs">
                  {item.subject}
                  <span className="ml-1 rounded-full bg-background/50 px-1.5 py-0.5 text-[10px] font-semibold tabular-nums">
                    {item.count.toLocaleString()}
                  </span>
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
