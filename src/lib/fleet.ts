export type Priority = "Normal" | "Inspect soon" | "Urgent review" | "Verify sensor";

export interface Valve {
  id: string;
  area: string;
  status: Priority;
  finding: string;
  trend: number[];
}

const areas = ["Feedwater", "Steam header", "Cooling loop", "Condensate", "Process line"];

function wave(seed: number, drift = 0, flat = false): number[] {
  return Array.from({ length: 16 }, (_, i) =>
    flat ? 50 : 50 + Math.sin(i * 0.8 + seed) * 8 + Math.cos(i * 1.7 + seed * 2) * 4 + drift * i,
  );
}

export const FLEET: Valve[] = Array.from({ length: 20 }, (_, i) => {
  const n = 101 + i;
  const id = `V-${n}`;
  const base: Valve = { id, area: areas[i % areas.length] ?? "Process line", status: "Normal", finding: "Within baseline", trend: wave(i) };
  if (n === 107) return { ...base, status: "Inspect soon", finding: "Response time +68%", trend: wave(i, 2.2) };
  if (n === 113) return { ...base, status: "Urgent review", finding: "Pressure-position mismatch", trend: wave(i, -2.6) };
  return base;
});
// V-121 sits outside 101-120; append it as the 20th simulated valve.
FLEET[19] = { id: "V-121", area: "Cooling loop", status: "Verify sensor", finding: "Flatlined vibration sensor", trend: wave(0, 0, true) };

export const priorityStyle: Record<Priority, string> = {
  Normal: "bg-success/10 text-success border-success/30",
  "Inspect soon": "bg-warning/10 text-warning border-warning/30",
  "Urgent review": "bg-destructive/10 text-destructive border-destructive/30",
  "Verify sensor": "bg-primary/10 text-primary border-primary/30",
};
