import Link from "next/link";
import { getSimilarBills } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { formatJurisdiction, truncate } from "@/lib/format";

interface SimilarTabProps {
  billId: string;
  collectionId?: string;
}

export async function SimilarTab({ billId, collectionId }: SimilarTabProps) {
  let data;
  try {
    data = await getSimilarBills(billId, { top_k: 10, min_score: 0.3 });
  } catch {
    return <p className="text-sm text-muted-foreground">Unable to load similar bills.</p>;
  }

  if (data.data.length === 0) {
    return (
      <p className="text-muted-foreground">
        No similar bills found across jurisdictions.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {data.data.map((bill) => (
        <div key={bill.bill_id} className="space-y-2">
          <Link href={collectionId ? `/bills/${encodeURIComponent(bill.bill_id)}?collection_id=${collectionId}` : `/bills/${encodeURIComponent(bill.bill_id)}`}>
            <Card className="transition-colors hover:bg-accent/50">
              <CardHeader className="gap-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge variant="outline" className="font-mono text-xs">
                    {bill.identifier}
                  </Badge>
                  <Badge variant="secondary" className="text-xs">
                    {formatJurisdiction(bill.jurisdiction_id)}
                  </Badge>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {(bill.similarity_score * 100).toFixed(0)}% similar
                  </span>
                </div>
                <CardTitle className="text-base leading-snug">
                  {truncate(bill.title, 200)}
                </CardTitle>
              </CardHeader>
            </Card>
          </Link>
          <div className="flex justify-end">
            <Link
              href={collectionId ? `/compare?a=${encodeURIComponent(billId)}&b=${encodeURIComponent(bill.bill_id)}&collection_id=${collectionId}` : `/compare?a=${encodeURIComponent(billId)}&b=${encodeURIComponent(bill.bill_id)}`}
              className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent"
            >
              Compare with current bill
            </Link>
          </div>
        </div>
      ))}
    </div>
  );
}
