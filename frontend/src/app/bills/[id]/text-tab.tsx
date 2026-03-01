"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { BillTextResponse } from "@/types/api";

interface BillTextTabProps {
  texts: BillTextResponse[];
}

export function BillTextTab({ texts }: BillTextTabProps) {
  const [selectedId, setSelectedId] = useState(texts[0]?.id ?? "");

  if (texts.length === 0) {
    return (
      <p className="text-muted-foreground">No bill text available.</p>
    );
  }

  const selected = texts.find((t) => t.id === selectedId) ?? texts[0];

  return (
    <div className="space-y-4">
      {/* Version selector */}
      <div className="flex items-center gap-3">
        <Select value={selectedId} onValueChange={setSelectedId}>
          <SelectTrigger className="w-64">
            <SelectValue placeholder="Select version" />
          </SelectTrigger>
          <SelectContent>
            {texts.map((t) => (
              <SelectItem key={t.id} value={t.id}>
                {t.version_name}
                {t.version_date ? ` (${t.version_date})` : ""}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {selected.word_count && (
          <Badge variant="outline" className="text-xs">
            {selected.word_count.toLocaleString()} words
          </Badge>
        )}
      </div>

      {/* Text content */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{selected.version_name}</CardTitle>
        </CardHeader>
        <CardContent>
          {selected.content_text ? (
            <ScrollArea className="max-h-[600px]">
              <pre className="whitespace-pre-wrap font-mono text-sm leading-relaxed">
                {selected.content_text}
              </pre>
            </ScrollArea>
          ) : (
            <p className="text-muted-foreground">
              Text content not available for this version.
              {selected.source_url && (
                <>
                  {" "}
                  <a
                    href={selected.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline"
                  >
                    View source
                  </a>
                </>
              )}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
