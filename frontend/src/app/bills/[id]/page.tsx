import { Suspense, cache } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { ApiError, getBill, getBillBriefUrl } from "@/lib/api";

const getBillCached = cache((id: string) => getBill(id));
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatJurisdiction, formatStatus, statusVariant } from "@/lib/format";
import { BillSummaryTab } from "./summary-tab";
import { BillTextTab } from "./text-tab";
import { BillActionsTab } from "./actions-tab";
import { BillSponsorsTab } from "./sponsors-tab";
import { SimilarTab } from "./similar-tab";
import { VersionDiffTab } from "./version-diff-tab";
import { ConstitutionalTab } from "./constitutional-tab";
import { PatternsTab } from "./patterns-tab";
import { DiffusionTab } from "./diffusion-tab";
import { PredictionTab } from "./prediction-tab";
import { MLPredictionBadge } from "./ml-prediction-badge";
import { HearingsTab } from "./hearings-tab";
import { SaveToCollection } from "@/components/save-to-collection";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  try {
    const bill = await getBillCached(id);
    return { title: `${bill.identifier} | Legislative Research Tool` };
  } catch {
    return { title: "Bill Not Found" };
  }
}

export default async function BillDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { id } = await params;
  const qp = await searchParams;
  const collectionId = typeof qp.collection_id === "string" ? qp.collection_id : undefined;
  let bill;
  try {
    bill = await getBillCached(id);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      notFound();
    }
    throw err;
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      {collectionId && (
        <div className="mb-4">
          <Link href={`/collections/${collectionId}`} className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent">
            Back to Investigation
          </Link>
        </div>
      )}
      <div className="mb-6">
        <div className="mb-2 flex flex-wrap items-center gap-2">
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
          <MLPredictionBadge billId={id} />
        </div>
        <div className="flex items-start gap-3">
          <h1 className="flex-1 text-2xl font-bold leading-tight">{bill.title}</h1>
          <div className="flex shrink-0 items-center gap-2">
            <SaveToCollection billId={id} />
            <a
              href={getBillBriefUrl(id)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent"
            >
              Download Brief
            </a>
          </div>
        </div>
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
          <TabsTrigger value="similar">Similar</TabsTrigger>
          <TabsTrigger value="version-diff">Version Diff</TabsTrigger>
          <TabsTrigger value="constitutional">Constitutional</TabsTrigger>
          <TabsTrigger value="patterns">Patterns</TabsTrigger>
          <TabsTrigger value="diffusion">Diffusion</TabsTrigger>
          <TabsTrigger value="prediction">Prediction</TabsTrigger>
          <TabsTrigger value="hearings">Hearings</TabsTrigger>
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

        <TabsContent value="similar" className="mt-4">
          <Suspense
            fallback={
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="h-20 animate-pulse rounded-lg border bg-muted/30" />
                ))}
              </div>
            }
          >
            <SimilarTab billId={id} collectionId={collectionId} />
          </Suspense>
        </TabsContent>

        <TabsContent value="version-diff" className="mt-4">
          <VersionDiffTab billId={id} texts={bill.texts} />
        </TabsContent>

        <TabsContent value="constitutional" className="mt-4">
          <ConstitutionalTab billId={id} />
        </TabsContent>

        <TabsContent value="patterns" className="mt-4">
          <PatternsTab billId={id} />
        </TabsContent>

        <TabsContent value="diffusion" className="mt-4">
          <DiffusionTab billId={id} />
        </TabsContent>

        <TabsContent value="prediction" className="mt-4">
          <PredictionTab billId={id} />
        </TabsContent>

        <TabsContent value="hearings" className="mt-4">
          <HearingsTab billId={id} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
