"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface SearchFormProps {
  defaultQuery: string;
  defaultJurisdiction: string;
  defaultMode: string;
  collectionId?: number;
}

export function SearchForm({
  defaultQuery,
  defaultJurisdiction,
  defaultMode,
  collectionId,
}: SearchFormProps) {
  const router = useRouter();
  const [query, setQuery] = useState(defaultQuery);
  const [jurisdiction, setJurisdiction] = useState(defaultJurisdiction);
  const [mode, setMode] = useState(defaultMode);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;

    const params = new URLSearchParams();
    params.set("q", query.trim());
    if (jurisdiction) params.set("jurisdiction", jurisdiction);
    if (mode && mode !== "hybrid") params.set("mode", mode);
    if (collectionId) params.set("collection_id", String(collectionId));
    params.set("page", "1");
    router.push(`/search?${params.toString()}`);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row">
      <div className="relative flex-1">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="text"
          placeholder="Search bills... (e.g., 'data privacy', 'qualified immunity')"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="pl-9"
        />
      </div>

      <Input
        type="text"
        placeholder="Jurisdiction (e.g., us-ca)"
        value={jurisdiction}
        onChange={(e) => setJurisdiction(e.target.value)}
        className="w-full sm:w-40"
      />

      <Select value={mode} onValueChange={setMode}>
        <SelectTrigger className="w-full sm:w-32">
          <SelectValue placeholder="Mode" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="hybrid">Hybrid</SelectItem>
          <SelectItem value="keyword">Keyword</SelectItem>
          <SelectItem value="semantic">Semantic</SelectItem>
        </SelectContent>
      </Select>

      <Button type="submit">Search</Button>
    </form>
  );
}
