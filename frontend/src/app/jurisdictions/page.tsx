import { Suspense } from "react";
import type { Metadata } from "next";
import { parsePageParam } from "@/lib/format";
import { JurisdictionGrid } from "./jurisdiction-grid";

export const metadata: Metadata = {
  title: "Jurisdictions | Legislative Research Tool",
};

export default async function JurisdictionsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const classification =
    typeof params.type === "string" ? params.type : undefined;
  const page = parsePageParam(params.page);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold">Jurisdictions</h1>
      <p className="mb-6 text-muted-foreground">
        Browse federal and state legislatures. Click a jurisdiction to view its
        sessions and bills.
      </p>
      <Suspense
        key={`${classification}-${page}`}
        fallback={<GridSkeleton />}
      >
        <JurisdictionGrid classification={classification} page={page} />
      </Suspense>
    </div>
  );
}

function GridSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 12 }).map((_, i) => (
        <div
          key={i}
          className="h-24 animate-pulse rounded-lg border bg-muted/30"
        />
      ))}
    </div>
  );
}
