"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  Menu,
  X,
  Scale,
  Search,
  Building2,
  Users,
  FolderOpen,
  Bot,
  FileText,
  FilePenLine,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

const primaryNavItems = [
  { href: "/collections", label: "Investigations", icon: FolderOpen },
  { href: "/search", label: "Search", icon: Search },
  { href: "/assistant", label: "Assistant", icon: Bot },
];

const secondaryNavItems = [
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/composer", label: "Composer", icon: FilePenLine },
  { href: "/jurisdictions", label: "Jurisdictions", icon: Building2 },
  { href: "/legislators", label: "Legislators", icon: Users },
];

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-14 max-w-7xl items-center px-4">
        {/* Logo */}
        <Link href="/" className="mr-6 flex items-center gap-2 font-semibold">
          <Scale className="h-5 w-5" />
          <span className="hidden sm:inline">LegisResearch</span>
        </Link>

        <nav className="hidden md:flex md:items-center md:gap-1">
          {primaryNavItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground",
                pathname.startsWith(item.href)
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground",
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          ))}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="text-muted-foreground">
                More
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              {secondaryNavItems.map((item) => (
                <DropdownMenuItem key={item.href} asChild>
                  <Link href={item.href} className="flex items-center gap-2">
                    <item.icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </nav>

        <div className="flex-1" />

        {/* Mobile nav */}
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild className="md:hidden">
            <Button variant="ghost" size="icon">
              {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              <span className="sr-only">Toggle menu</span>
            </Button>
          </SheetTrigger>
          <SheetContent side="right" className="w-64">
            <SheetTitle className="sr-only">Navigation</SheetTitle>
            <nav className="mt-6 flex flex-col gap-2">
              {[...primaryNavItems, ...secondaryNavItems].map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className={cn(
                    "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-accent",
                    pathname.startsWith(item.href)
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground",
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </Link>
              ))}
            </nav>
          </SheetContent>
        </Sheet>
      </div>
    </header>
  );
}
