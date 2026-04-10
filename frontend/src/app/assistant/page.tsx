import { Suspense } from "react";
import AssistantClientPage from "./page-client";

export default function AssistantPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-3xl px-4 py-8 text-sm text-muted-foreground">Loading assistant…</div>}>
      <AssistantClientPage />
    </Suspense>
  );
}
