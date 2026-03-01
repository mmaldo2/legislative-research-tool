"use client";

import { useCallback } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAnalysis } from "@/hooks/use-analysis";
import { getDiffusion } from "@/lib/api";
import { formatJurisdiction } from "@/lib/format";
import type { DiffusionOutput } from "@/types/api";

interface DiffusionTabProps {
  billId: string;
}

export function DiffusionTab({ billId }: DiffusionTabProps) {
  const fetcher = useCallback(
    (signal: AbortSignal) => getDiffusion(billId, 10, signal),
    [billId],
  );
  const { result, loading, error, analyze } = useAnalysis<DiffusionOutput>(fetcher);

  if (!result) {
    return (
      <div className="flex flex-col items-center gap-4 py-8" aria-busy={loading}>
        <p className="text-muted-foreground">
          Track how this legislative idea has spread across jurisdictions over
          time by finding similar bills in other states.
        </p>
        <Button onClick={analyze} disabled={loading}>
          {loading ? "Searching..." : "Track Diffusion"}
        </Button>
        {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-4" aria-live="polite">
      {/* Summary */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Policy Diffusion</CardTitle>
            <Badge variant="outline" className="text-xs">
              {result.total_jurisdictions} jurisdiction{result.total_jurisdictions !== 1 && "s"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="leading-relaxed">{result.summary}</p>
          <div className="flex flex-wrap gap-4 text-sm">
            <div>
              <span className="font-medium">Source: </span>
              <Badge variant="secondary" className="font-mono text-xs">
                {result.source_identifier}
              </Badge>
              {" "}
              <span className="text-muted-foreground">
                ({formatJurisdiction(result.source_jurisdiction)})
              </span>
            </div>
            {result.earliest_date && result.latest_date && (
              <div className="text-muted-foreground">
                {result.earliest_date} &mdash; {result.latest_date}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Timeline */}
      {result.timeline.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">
              Timeline ({result.timeline.length} bills)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {result.timeline.map((event) => (
                <Link
                  key={event.bill_id}
                  href={`/bills/${encodeURIComponent(event.bill_id)}`}
                  className="flex items-start gap-3 rounded-lg border p-3 transition-colors hover:bg-accent/50"
                >
                  <div className="shrink-0 w-24 text-xs text-muted-foreground pt-0.5">
                    {event.status_date ?? "No date"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant="outline" className="font-mono text-xs">
                        {event.identifier}
                      </Badge>
                      <Badge variant="secondary" className="text-xs">
                        {formatJurisdiction(event.jurisdiction_id)}
                      </Badge>
                      <Badge variant="outline" className="text-xs">
                        {(event.similarity_score * 100).toFixed(0)}% similar
                      </Badge>
                    </div>
                    <p className="text-sm truncate">{event.title}</p>
                    {event.status && (
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Status: {event.status}
                      </p>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
