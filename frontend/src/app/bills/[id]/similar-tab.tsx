import Link from "next/link";
import { getSimilarBills } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { formatJurisdiction } from "@/lib/format";

interface SimilarTabProps {
  billId: string;
}

export async function SimilarTab({ billId }: SimilarTabProps) {
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
        <Link key={bill.bill_id} href={`/bills/${encodeURIComponent(bill.bill_id)}`}>
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
                {bill.title.length > 200 ? bill.title.slice(0, 200) + "..." : bill.title}
              </CardTitle>
            </CardHeader>
          </Card>
        </Link>
      ))}
    </div>
  );
}
