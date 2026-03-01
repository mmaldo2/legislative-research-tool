"use client";

import { useCallback, useEffect, useState } from "react";

export interface SavedSearch {
  id: string;
  name: string;
  query: string;
  jurisdiction: string;
  mode: "keyword" | "semantic" | "hybrid";
  createdAt: string; // ISO timestamp
}

interface SavedSearchStore {
  schemaVersion: 1;
  searches: SavedSearch[];
}

const STORAGE_KEY = "legis-saved-searches";

function readStore(): SavedSearch[] {
  if (typeof window === "undefined") return [];

  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];

    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      "schemaVersion" in parsed &&
      (parsed as SavedSearchStore).schemaVersion === 1 &&
      "searches" in parsed &&
      Array.isArray((parsed as SavedSearchStore).searches)
    ) {
      return (parsed as SavedSearchStore).searches;
    }

    // Schema mismatch or unexpected shape — reset
    localStorage.removeItem(STORAGE_KEY);
    return [];
  } catch {
    // Corrupted JSON — reset
    localStorage.removeItem(STORAGE_KEY);
    return [];
  }
}

function writeStore(searches: SavedSearch[]): void {
  if (typeof window === "undefined") return;

  const store: SavedSearchStore = {
    schemaVersion: 1,
    searches,
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
}

export function useSavedSearches() {
  const [searches, setSearches] = useState<SavedSearch[]>(() => readStore());

  // Listen for storage events from other tabs/windows
  useEffect(() => {
    function handleStorageChange(e: StorageEvent) {
      if (e.key === STORAGE_KEY) {
        setSearches(readStore());
      }
    }

    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, []);

  const saveSearch = useCallback(
    (params: {
      name: string;
      query: string;
      jurisdiction: string;
      mode: string;
    }) => {
      const newSearch: SavedSearch = {
        id: crypto.randomUUID(),
        name: params.name,
        query: params.query,
        jurisdiction: params.jurisdiction,
        mode: params.mode as SavedSearch["mode"],
        createdAt: new Date().toISOString(),
      };

      setSearches((prev) => {
        const next = [newSearch, ...prev];
        writeStore(next);
        return next;
      });
    },
    [],
  );

  const deleteSearch = useCallback((id: string) => {
    setSearches((prev) => {
      const next = prev.filter((s) => s.id !== id);
      writeStore(next);
      return next;
    });
  }, []);

  return { searches, saveSearch, deleteSearch };
}
