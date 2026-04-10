import Link from "next/link";
import { compareBills, getBill } from "@/lib/api";
import { ApiErrorBanner } from "@/components/api-error";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatJurisdiction, formatStatus, statusVariant } from "@/lib/format";

interface ComparisonViewProps {
  billIdA: string;
  billIdB: string;
  collectionId?: string;
}

export async function ComparisonView({ billIdA, billIdB, collectionId }: ComparisonViewProps) {
  let billA, billB, comparison;
  try {
    [billA, billB, comparison] = await Promise.all([
      getBill(billIdA),
      getBill(billIdB),
      compareBills(billIdA, billIdB),
    ]);
  } catch {
    return (
      <ApiErrorBanner
        message="Failed to load comparison. Make sure the API server is running."
        className="mt-4"
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        {[billA, billB].map((bill) => {
          const billHref = collectionId
            ? `/bills/${encodeURIComponent(bill.id)}?collection_id=${collectionId}`
            : `/bills/${encodeURIComponent(bill.id)}`;
          return (
            <Card key={bill.id}>
              <CardHeader>
                <div className="mb-1 flex items-center gap-2 flex-wrap">
                  <Badge variant="outline" className="font-mono text-xs">
                    {bill.identifier}
                  </Badge>
                  <Badge variant="secondary" className="text-xs">
                    {formatJurisdiction(bill.jurisdiction_id)}
                  </Badge>
                  {bill.status && (
                    <Badge variant={statusVariant(bill.status)} className="text-xs">
                      {formatStatus(bill.status)}
                    </Badge>
                  )}
                </div>
                <CardTitle className="text-base">{bill.title}</CardTitle>
                <div className="mt-3 flex gap-2">
                  <Link href={billHref} className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent">
                    Open Bill
                  </Link>
                  {collectionId && (
                    <Link href={`/collections/${collectionId}`} className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent">
                      Back to Investigation
                    </Link>
                  )}
                </div>
              </CardHeader>
            </Card>
          );
        })}
      </div>

      {/* Similarity score */}
      <div className="flex items-center gap-3 rounded-lg border p-4">
        <div className="text-2xl font-bold">
          {(comparison.similarity_score * 100).toFixed(0)}%
        </div>
        <div>
          <p className="font-medium">Similarity Score</p>
          <p className="text-sm text-muted-foreground">
            {comparison.is_model_legislation
              ? "Potential model legislation detected"
              : "Based on AI analysis of bill provisions"}
          </p>
        </div>
        {comparison.is_model_legislation && (
          <Badge variant="destructive" className="ml-auto">
            Model Legislation
          </Badge>
        )}
      </div>

      {/* Overall assessment */}
      <Card>
        <CardHeader>
          <CardTitle>Overall Assessment</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed">{comparison.overall_assessment}</p>
        </CardContent>
      </Card>

      {/* Shared provisions */}
      {comparison.shared_provisions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Shared Provisions</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc pl-5 space-y-1 text-sm">
              {comparison.shared_provisions.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Key differences */}
      {comparison.key_differences.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Key Differences</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc pl-5 space-y-1 text-sm">
              {comparison.key_differences.map((d, i) => (
                <li key={i}>{d}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Unique provisions side by side */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Unique to {billA.identifier}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {comparison.unique_to_a.length > 0 ? (
              <ul className="list-disc pl-5 space-y-1 text-sm">
                {comparison.unique_to_a.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">No unique provisions.</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Unique to {billB.identifier}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {comparison.unique_to_b.length > 0 ? (
              <ul className="list-disc pl-5 space-y-1 text-sm">
                {comparison.unique_to_b.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">No unique provisions.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
