import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[50vh] max-w-md flex-col items-center justify-center gap-4 px-4 text-center">
      <h1 className="text-2xl font-bold">Page Not Found</h1>
      <p className="text-muted-foreground">
        The resource you&apos;re looking for doesn&apos;t exist or may have been
        removed.
      </p>
      <Button asChild>
        <Link href="/">Return to search</Link>
      </Button>
    </div>
  );
}
