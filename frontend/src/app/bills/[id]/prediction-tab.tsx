"use client";

import { useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAnalysis } from "@/hooks/use-analysis";
import { predictOutcome } from "@/lib/api";
import type { PredictionOutput, PredictionDirection, PredictedOutcome } from "@/types/api";

interface PredictionTabProps {
  billId: string;
}

const outcomeVariant = (o: PredictedOutcome) => {
  if (o === "pass") return "default" as const;
  if (o === "fail") return "destructive" as const;
  if (o === "stall") return "secondary" as const;
  return "outline" as const;
};

const directionColor = (d: PredictionDirection) => {
  if (d === "positive") return "text-green-600 dark:text-green-400";
  if (d === "negative") return "text-red-600 dark:text-red-400";
  return "text-muted-foreground";
};

const directionSymbol = (d: PredictionDirection) => {
  if (d === "positive") return "+";
  if (d === "negative") return "-";
  return "~";
};

export function PredictionTab({ billId }: PredictionTabProps) {
  const fetcher = useCallback(
    (signal: AbortSignal) => predictOutcome(billId, signal),
    [billId],
  );
  const { result, loading, error, analyze } = useAnalysis<PredictionOutput>(fetcher);

  if (!result) {
    return (
      <div className="flex flex-col items-center gap-4 py-8" aria-busy={loading}>
        <p className="text-muted-foreground">
          Predict this bill&apos;s likely outcome based on its sponsors, legislative
          progress, subject area, and historical patterns.
        </p>
        <Button onClick={analyze} disabled={loading}>
          {loading ? "Predicting..." : "Predict Outcome"}
        </Button>
        {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
      </div>
    );
  }

  const pct = (result.passage_probability * 100).toFixed(0);

  return (
    <div className="space-y-4" aria-live="polite">
      {/* Prediction Overview */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Outcome Prediction</CardTitle>
            <div className="flex items-center gap-2">
              <Badge variant={outcomeVariant(result.predicted_outcome)} className="text-sm">
                {result.predicted_outcome.toUpperCase()}
              </Badge>
              <Badge variant="outline" className="text-xs">
                {(result.confidence * 100).toFixed(0)}% confidence
              </Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Probability bar */}
          <div>
            <div className="flex items-center justify-between text-sm mb-1">
              <span className="font-medium">Passage probability</span>
              <span className="font-mono">{pct}%</span>
            </div>
            <div
              className="h-3 w-full rounded-full bg-muted overflow-hidden"
              role="progressbar"
              aria-valuenow={Number(pct)}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`Passage probability: ${pct}%`}
            >
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>

          <p className="leading-relaxed">{result.summary}</p>
        </CardContent>
      </Card>

      {/* Key Factors */}
      {result.key_factors.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Key Factors</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {result.key_factors.map((f, i) => (
                <div key={i} className="flex gap-3 rounded-lg border p-3">
                  <span
                    className={`shrink-0 text-lg font-bold ${directionColor(f.direction)}`}
                    aria-label={f.direction}
                  >
                    {directionSymbol(f.direction)}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-sm font-medium">{f.factor}</span>
                      <Badge variant="outline" className="text-xs">
                        {f.weight}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">{f.explanation}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Historical Comparison */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Historical Comparison</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed">{result.historical_comparison}</p>
        </CardContent>
      </Card>
    </div>
  );
}
