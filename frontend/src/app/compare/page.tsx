import { Suspense } from "react";
import type { Metadata } from "next";
import { ComparisonView } from "./comparison-view";

export const metadata: Metadata = {
  title: "Compare Bills | Legislative Research Tool",
};

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ a?: string; b?: string }>;
}) {
  const { a, b } = await searchParams;

  if (!a || !b) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8">
        <h1 className="text-2xl font-bold mb-4">Compare Bills</h1>
        <p className="text-muted-foreground">
          Select two bills to compare. Use the &ldquo;Similar Bills&rdquo; tab on any bill detail page
          to find related legislation, then click &ldquo;Compare&rdquo; to see a side-by-side analysis.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">Bill Comparison</h1>
      <Suspense fallback={<ComparisonSkeleton />}>
        <ComparisonView billIdA={a} billIdB={b} />
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
