"use client";

import { FormEvent, useState } from "react";
import { Bookmark, Check } from "lucide-react";
import { useSavedSearches } from "@/hooks/use-saved-searches";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

interface SaveSearchButtonProps {
  query: string;
  jurisdiction: string;
  mode: string;
}

export function SaveSearchButton({
  query,
  jurisdiction,
  mode,
}: SaveSearchButtonProps) {
  const { saveSearch } = useSavedSearches();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(query);
  const [saved, setSaved] = useState(false);

  function handleOpen(isOpen: boolean) {
    setOpen(isOpen);
    if (isOpen) {
      setName(query);
      setSaved(false);
    }
  }

  function handleSave(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;

    saveSearch({
      name: name.trim(),
      query,
      jurisdiction,
      mode,
    });

    setOpen(false);
    setSaved(true);

    // Reset the "Saved!" indicator after 2 seconds
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" disabled={saved}>
          {saved ? (
            <>
              <Check className="h-4 w-4" />
              Saved!
            </>
          ) : (
            <>
              <Bookmark className="h-4 w-4" />
              Save Search
            </>
          )}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Save Search</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSave} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <label htmlFor="search-name" className="text-sm font-medium">
              Name
            </label>
            <Input
              id="search-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter a name for this search"
              autoFocus
            />
          </div>
          <div className="flex flex-col gap-1 rounded-md bg-muted px-3 py-2 text-sm">
            <span className="text-muted-foreground">Query:</span>
            <code>{query}</code>
            {jurisdiction && (
              <>
                <span className="mt-1 text-muted-foreground">
                  Jurisdiction:
                </span>
                <span>{jurisdiction}</span>
              </>
            )}
            <span className="mt-1 text-muted-foreground">Mode:</span>
            <span>{mode}</span>
          </div>
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={!name.trim()}>
              Save
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
