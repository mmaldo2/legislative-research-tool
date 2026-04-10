import { Suspense } from "react";
import Link from "next/link";
import type { Metadata } from "next";
import CompareClientPage from "./page-client";
import { ComparisonView } from "./comparison-view";

export const metadata: Metadata = {
  title: "Compare Bills | Legislative Research Tool",
};

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ a?: string; b?: string; collection_id?: string }>;
}) {
  const { a, b, collection_id } = await searchParams;

  if (!a || !b) {
    return (
      <Suspense fallback={<div className="mx-auto max-w-5xl px-4 py-8 text-sm text-muted-foreground">Loading comparison…</div>}>
        <CompareClientPage collectionIdParam={collection_id} />
      </Suspense>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      {collection_id && (
        <div className="mb-4">
          <Link href={`/collections/${collection_id}`} className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent">
            Back to Investigation
          </Link>
        </div>
      )}
      <h1 className="mb-2 text-2xl font-bold">Bill Comparison</h1>
      <p className="mb-6 text-muted-foreground">
        {collection_id
          ? "Comparing bills from the active investigation. Use the results to refine your working set or continue into memo generation."
          : "Compare two bills side by side and inspect their shared provisions, differences, and overall similarity."}
      </p>
      <Suspense fallback={<ComparisonSkeleton />}>
        <ComparisonView billIdA={a} billIdB={b} collectionId={collection_id} />
      </Suspense>
    </div>
  );
}

function ComparisonSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="h-32 animate-pulse rounded-lg bg-muted/30" />
        <div className="h-32 animate-pulse rounded-lg bg-muted/30" />
      </div>
      <div className="h-64 animate-pulse rounded-lg bg-muted/30" />
    </div>
  );
}
