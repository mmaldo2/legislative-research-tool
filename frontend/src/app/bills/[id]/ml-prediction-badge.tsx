"use client";

import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { getBillPrediction } from "@/lib/api";
import type { MLPredictionResponse } from "@/types/api";

interface MLPredictionBadgeProps {
  billId: string;
}

function probabilityColor(p: number): string {
  if (p >= 0.5) return "text-green-600 dark:text-green-400";
  if (p >= 0.2) return "text-yellow-600 dark:text-yellow-400";
  return "text-muted-foreground";
}

function barColor(p: number): string {
  if (p >= 0.5) return "bg-green-500";
  if (p >= 0.2) return "bg-yellow-500";
  return "bg-muted-foreground";
}

export function MLPredictionBadge({ billId }: MLPredictionBadgeProps) {
  const [prediction, setPrediction] = useState<MLPredictionResponse | null>(null);
  const [error, setError] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    getBillPrediction(billId, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setPrediction(data);
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(true);
      });

    return () => controller.abort();
  }, [billId]);

  if (error || !prediction) return null;

  const pct = (prediction.committee_passage_probability * 100).toFixed(0);
  const basePct = (prediction.base_rate * 100).toFixed(1);
  const topFactors = prediction.key_factors.slice(0, 3);

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge
            variant="outline"
            className="cursor-default gap-1.5 py-1 pl-1.5 pr-2.5"
          >
            <div
              className="h-2.5 w-2.5 rounded-full shrink-0"
              style={{
                background: `conic-gradient(
                  ${prediction.committee_passage_probability >= 0.5 ? "#22c55e" : prediction.committee_passage_probability >= 0.2 ? "#eab308" : "#6b7280"}
                  ${prediction.committee_passage_probability * 360}deg,
                  #e5e7eb ${prediction.committee_passage_probability * 360}deg
                )`,
              }}
            />
            <span className={`font-mono text-xs ${probabilityColor(prediction.committee_passage_probability)}`}>
              {pct}% passage
            </span>
          </Badge>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="max-w-xs">
          <div className="space-y-2 text-xs">
            <div className="font-medium">ML Committee Passage Prediction</div>
            <div className="flex items-center gap-2">
              <div className="flex-1">
                <div
                  className="h-1.5 w-full rounded-full bg-muted overflow-hidden"
                  role="progressbar"
                  aria-valuenow={Number(pct)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div
                    className={`h-full rounded-full ${barColor(prediction.committee_passage_probability)}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
              <span className="font-mono shrink-0">{pct}%</span>
            </div>
            <div className="text-muted-foreground">
              Base rate: {basePct}% of bills clear committee
            </div>
            {topFactors.length > 0 && (
              <div className="space-y-0.5 pt-1 border-t">
                <div className="font-medium">Top factors:</div>
                {topFactors.map((f) => (
                  <div key={f.feature} className="flex items-center gap-1">
                    <span className={f.impact === "positive" ? "text-green-500" : "text-red-500"}>
                      {f.impact === "positive" ? "+" : "-"}
                    </span>
                    <span>{f.feature.replace(/_/g, " ")}</span>
                  </div>
                ))}
              </div>
            )}
            <div className="text-muted-foreground pt-1 border-t">
              Model v{prediction.model_version}
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
