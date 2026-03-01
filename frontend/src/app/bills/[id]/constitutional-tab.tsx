"use client";

import { useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAnalysis } from "@/hooks/use-analysis";
import { analyzeConstitutional } from "@/lib/api";
import type { ConstitutionalAnalysisOutput } from "@/types/api";

interface ConstitutionalTabProps {
  billId: string;
}

const severityVariant = (s: string) => {
  if (s === "high") return "destructive" as const;
  if (s === "moderate") return "default" as const;
  return "secondary" as const;
};

const riskVariant = (r: string) => {
  if (r === "high") return "destructive" as const;
  if (r === "moderate") return "default" as const;
  if (r === "low") return "secondary" as const;
  return "outline" as const;
};

export function ConstitutionalTab({ billId }: ConstitutionalTabProps) {
  const fetcher = useCallback(
    (signal: AbortSignal) => analyzeConstitutional(billId, signal),
    [billId],
  );
  const { result, loading, error, analyze } = useAnalysis<ConstitutionalAnalysisOutput>(fetcher);

  if (!result) {
    return (
      <div className="flex flex-col items-center gap-4 py-8" aria-busy={loading}>
        <p className="text-muted-foreground">
          Analyze this bill for potential constitutional concerns, preemption issues, and
          relevant legal precedents.
        </p>
        <Button onClick={analyze} disabled={loading}>
          {loading ? "Analyzing..." : "Run Constitutional Analysis"}
        </Button>
        {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-4" aria-live="polite">
      {/* Overview */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Constitutional Analysis</CardTitle>
            <div className="flex items-center gap-2">
              <Badge variant={riskVariant(result.overall_risk_level)}>
                {result.overall_risk_level} risk
              </Badge>
              <Badge variant="outline" className="text-xs">
                {(result.confidence * 100).toFixed(0)}% confidence
              </Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="leading-relaxed">{result.summary}</p>
          {result.has_severability_clause && (
            <Badge variant="outline">Severability clause present</Badge>
          )}
        </CardContent>
      </Card>

      {/* Concerns */}
      {result.concerns.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">
              Constitutional Concerns ({result.concerns.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {result.concerns.map((concern, i) => (
                <div key={i} className="border-l-2 border-muted pl-4">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant={severityVariant(concern.severity)}>
                      {concern.severity}
                    </Badge>
                    <span className="text-sm font-medium">{concern.provision}</span>
                  </div>
                  <p className="text-sm mb-1">{concern.description}</p>
                  <p className="text-xs text-muted-foreground">
                    Bill section: {concern.bill_section}
                  </p>
                  {concern.relevant_precedents.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {concern.relevant_precedents.map((p, j) => (
                        <Badge key={j} variant="outline" className="text-xs">
                          {p}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Preemption Issues */}
      {result.preemption_issues.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Preemption Issues</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1 pl-5">
              {result.preemption_issues.map((issue, i) => (
                <li key={i}>{issue}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {result.concerns.length === 0 && result.preemption_issues.length === 0 && (
        <p className="text-muted-foreground">
          No constitutional concerns identified for this bill.
        </p>
      )}
    </div>
  );
}
