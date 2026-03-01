"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface UseAnalysisResult<T> {
  result: T | null;
  loading: boolean;
  error: string | null;
  analyze: () => void;
}

/**
 * Generic hook for on-demand AI analysis with abort-on-unmount.
 *
 * @param fetcher — async function that performs the analysis API call.
 *   Receives an AbortSignal for cancellation support.
 */
export function useAnalysis<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
): UseAnalysisResult<T> {
  const [result, setResult] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Abort in-flight request on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const analyze = useCallback(() => {
    // Cancel any previous in-flight request
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    fetcher(controller.signal)
      .then((output) => {
        if (!controller.signal.aborted) {
          setResult(output);
        }
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Analysis failed");
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });
  }, [fetcher]);

  return { result, loading, error, analyze };
}
