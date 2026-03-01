import { Suspense } from "react";
import type { Metadata } from "next";
import { JurisdictionDetail } from "./jurisdiction-detail";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  return {
    title: `${id.toUpperCase()} | Legislative Research Tool`,
  };
}

export default async function JurisdictionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <Suspense fallback={<DetailSkeleton />}>
        <JurisdictionDetail id={id} />
      </Suspense>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="space-y-4">
      <div className="h-8 w-48 animate-pulse rounded bg-muted/30" />
      <div className="h-4 w-96 animate-pulse rounded bg-muted/30" />
      <div className="grid gap-3 sm:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-20 animate-pulse rounded-lg border bg-muted/30"
          />
        ))}
      </div>
    </div>
  );
}
