import { cache } from "react";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { ApiError, getBill } from "@/lib/api";

const getBillCached = cache((id: string) => getBill(id));
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatJurisdiction, formatStatus, statusVariant } from "@/lib/format";
import { BillSummaryTab } from "./summary-tab";
import { BillTextTab } from "./text-tab";
import { BillActionsTab } from "./actions-tab";
import { BillSponsorsTab } from "./sponsors-tab";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  try {
    const bill = await getBillCached(decodeURIComponent(id));
    return { title: `${bill.identifier} | Legislative Research Tool` };
  } catch {
    return { title: "Bill Not Found" };
  }
}

export default async function BillDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let bill;
  try {
    bill = await getBillCached(decodeURIComponent(id));
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
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <Badge variant="outline" className="font-mono">
            {bill.identifier}
          </Badge>
          <Badge variant="secondary">
            {formatJurisdiction(bill.jurisdiction_id)}
          </Badge>
          {bill.status && (
            <Badge variant={statusVariant(bill.status)}>
              {formatStatus(bill.status)}
            </Badge>
          )}
          {bill.status_date && (
            <span className="text-sm text-muted-foreground">
              as of {bill.status_date}
            </span>
          )}
        </div>
        <h1 className="text-2xl font-bold leading-tight">{bill.title}</h1>
        {bill.subject && bill.subject.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {bill.subject.map((s) => (
              <Badge key={s} variant="outline" className="text-xs">
                {s}
              </Badge>
            ))}
          </div>
        )}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="summary">
        <TabsList>
          <TabsTrigger value="summary">Summary</TabsTrigger>
          <TabsTrigger value="text">
            Text ({bill.texts.length})
          </TabsTrigger>
          <TabsTrigger value="actions">
            Actions ({bill.actions.length})
          </TabsTrigger>
          <TabsTrigger value="sponsors">
            Sponsors ({bill.sponsors.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="summary" className="mt-4">
          <BillSummaryTab summary={bill.ai_summary} />
        </TabsContent>

        <TabsContent value="text" className="mt-4">
          <BillTextTab texts={bill.texts} />
        </TabsContent>

        <TabsContent value="actions" className="mt-4">
          <BillActionsTab actions={bill.actions} />
        </TabsContent>

        <TabsContent value="sponsors" className="mt-4">
          <BillSponsorsTab sponsors={bill.sponsors} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
