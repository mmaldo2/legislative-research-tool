"use client";

import { useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAnalysis } from "@/hooks/use-analysis";
import { analyzeVersionDiff } from "@/lib/api";
import type { VersionDiffOutput, BillTextResponse } from "@/types/api";

interface VersionDiffTabProps {
  billId: string;
  texts: BillTextResponse[];
}

const significanceVariant = (s: string) => {
  if (s === "major") return "destructive" as const;
  if (s === "moderate") return "default" as const;
  return "secondary" as const;
};

export function VersionDiffTab({ billId, texts }: VersionDiffTabProps) {
  const fetcher = useCallback(
    (signal: AbortSignal) => analyzeVersionDiff(billId, undefined, undefined, signal),
    [billId],
  );
  const { result, loading, error, analyze } = useAnalysis<VersionDiffOutput>(fetcher);

  const textsWithContent = texts.filter((t) => t.content_text);

  if (textsWithContent.length < 2) {
    return (
      <p className="text-muted-foreground">
        This bill needs at least 2 text versions for diff analysis.
        Currently {textsWithContent.length} version{textsWithContent.length !== 1 ? "s" : ""} available.
      </p>
    );
  }

  if (!result) {
    return (
      <div className="flex flex-col items-center gap-4 py-8" aria-busy={loading}>
        <p className="text-muted-foreground">
          Compare {textsWithContent.length} versions of this bill to identify substantive changes.
        </p>
        <Button onClick={analyze} disabled={loading}>
          {loading ? "Analyzing..." : "Analyze Version Differences"}
        </Button>
        {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-4" aria-live="polite">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">
              {result.version_a_name} → {result.version_b_name}
            </CardTitle>
            <Badge variant="outline" className="text-xs">
              {(result.confidence * 100).toFixed(0)}% confidence
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="leading-relaxed">{result.summary_of_changes}</p>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Direction:</span>
            <Badge variant="secondary">{result.direction_of_change}</Badge>
          </div>
        </CardContent>
      </Card>

      {/* Changes */}
      {result.changes.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">
              Changes ({result.changes.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {result.changes.map((change, i) => (
                <div key={i} className="border-l-2 border-muted pl-4">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant={significanceVariant(change.significance)}>
                      {change.significance}
                    </Badge>
                    <Badge variant="outline">{change.change_type}</Badge>
                    <span className="text-sm font-medium">{change.section}</span>
                  </div>
                  <p className="text-sm">{change.description}</p>
                  {change.before && (
                    <div className="mt-1 rounded bg-destructive/10 p-2 text-xs">
                      <span className="font-medium">Before: </span>
                      {change.before}
                    </div>
                  )}
                  {change.after && (
                    <div className="mt-1 rounded bg-green-500/10 p-2 text-xs">
                      <span className="font-medium">After: </span>
                      {change.after}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Amendments */}
      {result.amendments_incorporated.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Amendments Incorporated</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1 pl-5">
              {result.amendments_incorporated.map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
