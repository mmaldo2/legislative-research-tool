import { Suspense } from "react";
import ReportsClientPage from "./page-client";

export default function ReportsPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-4xl px-4 py-8 text-sm text-muted-foreground">Loading reports…</div>}>
      <ReportsClientPage />
    </Suspense>
  );
}
