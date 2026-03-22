"use client";

import { useMemo } from "react";
import DiffMatchPatch from "diff-match-patch";
import { Badge } from "@/components/ui/badge";

interface RevisionDiffProps {
  oldText: string;
  newText: string;
  oldLabel?: string;
  newLabel?: string;
  changeSource?: string;
}

/**
 * Inline word-level diff between two text revisions.
 * Green highlight for additions, red strikethrough for deletions.
 */
export function RevisionDiff({
  oldText,
  newText,
  oldLabel = "Previous",
  newLabel = "Current",
  changeSource,
}: RevisionDiffProps) {
  const diffs = useMemo(() => {
    const dmp = new DiffMatchPatch();
    const result = dmp.diff_main(oldText, newText);
    dmp.diff_cleanupSemantic(result);
    return result;
  }, [oldText, newText]);

  const hasChanges = diffs.some(([op]) => op !== 0);

  if (!hasChanges) {
    return (
      <div className="text-xs text-muted-foreground italic py-2">
        No changes between {oldLabel} and {newLabel}.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>{oldLabel}</span>
        <span>&rarr;</span>
        <span>{newLabel}</span>
        {changeSource && (
          <Badge variant="outline" className="text-[10px] py-0">
            {changeSource}
          </Badge>
        )}
      </div>
      <div className="rounded border p-3 text-xs leading-relaxed whitespace-pre-wrap font-mono">
        {diffs.map(([op, text], i) => {
          if (op === 1) {
            // Addition
            return (
              <span
                key={i}
                className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
              >
                {text}
              </span>
            );
          }
          if (op === -1) {
            // Deletion
            return (
              <span
                key={i}
                className="bg-red-100 text-red-800 line-through dark:bg-red-900/30 dark:text-red-300"
              >
                {text}
              </span>
            );
          }
          // Unchanged
          return <span key={i}>{text}</span>;
        })}
      </div>
    </div>
  );
}
