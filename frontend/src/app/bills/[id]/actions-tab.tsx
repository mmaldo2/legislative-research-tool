import { Badge } from "@/components/ui/badge";
import type { BillActionResponse } from "@/types/api";

interface BillActionsTabProps {
  actions: BillActionResponse[];
}

export function BillActionsTab({ actions }: BillActionsTabProps) {
  if (actions.length === 0) {
    return (
      <p className="text-muted-foreground">No actions recorded.</p>
    );
  }

  return (
    <div className="relative pl-6">
      {/* Timeline line */}
      <div className="absolute left-2 top-2 bottom-2 w-px bg-border" />

      <div className="space-y-4">
        {actions.map((action, i) => (
          <div key={i} className="relative">
            {/* Timeline dot */}
            <div className="absolute -left-4 top-1.5 h-2.5 w-2.5 rounded-full border-2 border-primary bg-background" />

            <div className="pb-1">
              <div className="flex items-center gap-2 flex-wrap">
                <time className="text-sm font-medium">
                  {action.action_date}
                </time>
                {action.chamber && (
                  <Badge variant="outline" className="text-xs">
                    {action.chamber === "upper" ? "Senate" : "House"}
                  </Badge>
                )}
                {action.classification?.map((c) => (
                  <Badge key={c} variant="secondary" className="text-xs">
                    {c}
                  </Badge>
                ))}
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {action.description}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
