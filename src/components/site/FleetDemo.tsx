import { Link } from "@tanstack/react-router";
import { Play } from "lucide-react";
import { FLEET } from "@/lib/fleet";
import { cn } from "@/lib/utils";
import { DemoBadge, PriorityBadge } from "./ui-bits";

export function FleetDemo({ compact = false }: { compact?: boolean }) {
  const flagged = FLEET.filter((v) => v.status !== "Normal");
  return (
    <div className="glass noise rounded-2xl p-4 sm:p-5">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold">Fleet Overview</h3>
          <p className="font-mono text-[11px] text-muted-foreground">20 valves · {flagged.length} flagged</p>
        </div>
        <DemoBadge />
      </div>
      <div className="mt-4 grid grid-cols-10 gap-1.5" role="img" aria-label="20 simulated valves, 17 normal, 3 flagged">
        {FLEET.map((v) => (
          <div
            key={v.id}
            title={`${v.id}: ${v.status}`}
            className={cn(
              "aspect-square rounded-[4px] border transition-all duration-300",
              v.status === "Normal" && "border-success/20 bg-success/15",
              v.status === "Inspect soon" && "border-warning/50 bg-warning/30",
              v.status === "Urgent review" && "border-destructive/50 bg-destructive/30",
              v.status === "Verify sensor" && "border-primary/50 bg-primary/30",
            )}
          />
        ))}
      </div>
      {!compact && (
        <ul className="mt-4 space-y-1.5">
          {flagged.map((v) => (
            <li key={v.id} className="flex items-center justify-between gap-2 rounded-lg border border-transparent px-2 py-1.5 text-xs">
              <span className="font-mono text-foreground">{v.id}</span>
              <span className="flex-1 truncate text-muted-foreground">{v.finding}</span>
              <PriorityBadge p={v.status} />
            </li>
          ))}
        </ul>
      )}
      {/* This card is a static illustration. The real investigation runs on the live demo page,
          against the FastAPI backend and the Gemini API. */}
      <Link
        to="/demo"
        className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg border border-primary/40 bg-primary/10 py-2 text-xs font-medium text-primary transition-colors hover:bg-primary/20"
      >
        <Play className="h-3.5 w-3.5" /> Run a real investigation
      </Link>
    </div>
  );
}
