"use client";

import { useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { analyzePatterns } from "@/lib/api";
import { formatJurisdiction } from "@/lib/format";
import type { PatternDetectionOutput } from "@/types/api";

interface PatternsTabProps {
  billId: string;
}

const patternVariant = (t: string) => {
  if (t === "identical") return "destructive" as const;
  if (t === "adapted") return "default" as const;
  if (t === "inspired") return "secondary" as const;
  return "outline" as const;
};

export function PatternsTab({ billId }: PatternsTabProps) {
  const [result, setResult] = useState<PatternDetectionOutput | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async () => {
    setLoading(true);
    setError(null);
    try {
      const output = await analyzePatterns(billId);
      setResult(output);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  if (!result) {
    return (
      <div className="flex flex-col items-center gap-4 py-8">
        <p className="text-muted-foreground">
          Detect cross-jurisdictional patterns and model legislation by comparing this bill
          against similar bills from other states.
        </p>
        <Button onClick={handleAnalyze} disabled={loading}>
          {loading ? "Analyzing..." : "Detect Patterns"}
        </Button>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Overview */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Pattern Analysis</CardTitle>
            <div className="flex items-center gap-2">
              <Badge variant={patternVariant(result.pattern_type)}>
                {result.pattern_type}
              </Badge>
              <Badge variant="outline" className="text-xs">
                {(result.confidence * 100).toFixed(0)}% confidence
              </Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="leading-relaxed">{result.summary}</p>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Common Framework:</span>
            <span className="text-sm">{result.common_framework}</span>
          </div>
          {result.source_organization && (
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Source Organization:</span>
              <Badge variant="secondary">{result.source_organization}</Badge>
            </div>
          )}
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Model Legislation Confidence:</span>
            <Badge
              variant={result.model_legislation_confidence > 0.7 ? "destructive" : "outline"}
            >
              {(result.model_legislation_confidence * 100).toFixed(0)}%
            </Badge>
          </div>
        </CardContent>
      </Card>

      {/* Bills Analyzed */}
      {result.bills_analyzed.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">
              Bills Analyzed ({result.bills_analyzed.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {result.bills_analyzed.map((bill) => (
                <Link
                  key={bill.bill_id}
                  href={`/bills/${encodeURIComponent(bill.bill_id)}`}
                  className="block rounded-lg border p-3 transition-colors hover:bg-accent/50"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant="outline" className="font-mono text-xs">
                      {bill.identifier}
                    </Badge>
                    <Badge variant="secondary" className="text-xs">
                      {formatJurisdiction(bill.jurisdiction_id)}
                    </Badge>
                  </div>
                  <p className="text-sm">{bill.title}</p>
                  {bill.variations.length > 0 && (
                    <ul className="mt-1 list-disc pl-5 text-xs text-muted-foreground">
                      {bill.variations.map((v, i) => (
                        <li key={i}>{v}</li>
                      ))}
                    </ul>
                  )}
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Shared Provisions & Variations */}
      <div className="grid gap-4 sm:grid-cols-2">
        {result.shared_provisions.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Shared Provisions</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="list-disc space-y-1 pl-5">
                {result.shared_provisions.map((p, i) => (
                  <li key={i} className="text-sm">{p}</li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
        {result.key_variations.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Key Variations</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="list-disc space-y-1 pl-5">
                {result.key_variations.map((v, i) => (
                  <li key={i} className="text-sm">{v}</li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
