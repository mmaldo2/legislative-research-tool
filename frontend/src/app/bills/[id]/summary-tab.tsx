import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { BillSummaryOutput } from "@/types/api";

interface BillSummaryTabProps {
  summary: BillSummaryOutput | null;
}

export function BillSummaryTab({ summary }: BillSummaryTabProps) {
  if (!summary) {
    return (
      <p className="text-muted-foreground">
        No AI summary available for this bill yet.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {/* Plain English Summary */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Summary</CardTitle>
            <Badge variant="outline" className="text-xs">
              {(summary.confidence * 100).toFixed(0)}% confidence
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <p className="leading-relaxed">{summary.plain_english_summary}</p>
        </CardContent>
      </Card>

      {/* Key Provisions */}
      {summary.key_provisions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Key Provisions</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1 pl-5">
              {summary.key_provisions.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Affected Populations */}
      {summary.affected_populations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Affected Populations</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {summary.affected_populations.map((p, i) => (
                <Badge key={i} variant="secondary">
                  {p}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Changes to Existing Law */}
      {summary.changes_to_existing_law.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Changes to Existing Law</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1 pl-5">
              {summary.changes_to_existing_law.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Fiscal & Effective Date */}
      {(summary.fiscal_implications || summary.effective_date) && (
        <div className="grid gap-4 sm:grid-cols-2">
          {summary.fiscal_implications && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Fiscal Implications</CardTitle>
              </CardHeader>
              <CardContent>
                <p>{summary.fiscal_implications}</p>
              </CardContent>
            </Card>
          )}
          {summary.effective_date && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Effective Date</CardTitle>
              </CardHeader>
              <CardContent>
                <p>{summary.effective_date}</p>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
