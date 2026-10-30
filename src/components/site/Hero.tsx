import { lazy, Suspense, useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { ArrowRight, ShieldCheck, Users, Cpu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FleetDemo } from "./FleetDemo";
import { StaticValve } from "./StaticValve";

const HeroScene = lazy(() => import("./HeroScene"));

const cards = [
  { t: "V-107 · Response time +68%", c: "text-warning", pos: "left-[4%] top-[12%]" },
  { t: "Pressure: normal", c: "text-success", pos: "right-[6%] top-[6%]" },
  { t: "Evidence: position lag", c: "text-primary", pos: "left-[8%] bottom-[16%]" },
  { t: "Priority: inspect soon", c: "text-warning", pos: "right-[4%] bottom-[24%]" },
];

function useCan3D() {
  const [ok, setOk] = useState<boolean | null>(null);
  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const weak = (navigator.hardwareConcurrency ?? 4) <= 2;
    let gl = false;
    try { gl = !!document.createElement("canvas").getContext("webgl2"); } catch { gl = false; }
    setOk(!reduce && !weak && gl);
  }, []);
  return ok;
}

export function Hero() {
  const can3D = useCan3D();
  return (
    <section id="product" className="relative overflow-hidden blueprint">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_70%_30%,var(--color-primary)_0%,transparent_55%)] opacity-[0.08]" />
      <div className="relative mx-auto grid max-w-7xl gap-10 px-4 pb-20 pt-14 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:pt-20">
        <div className="relative z-10 flex flex-col justify-center">
          <p className="inline-flex w-fit items-center gap-2 rounded-full border border-primary/30 bg-primary/5 px-3 py-1 font-mono text-xs text-primary">
            <span className="h-1.5 w-1.5 rounded-full bg-primary pulse-dot" /> Investigate smarter. Maintain with evidence.
          </p>
          <h1 className="mt-6 text-4xl font-semibold leading-[1.05] sm:text-6xl">
            <span className="text-gradient">Know which valve needs attention first.</span>
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground">
            ValveGuard turns equipment readings into ranked, evidence-backed investigation reports—so maintenance teams spend less time reviewing data and more time preventing downtime.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button asChild variant="hero" size="lg"><Link to="/signup">Launch ValveGuard <ArrowRight /></Link></Button>
            <Button asChild variant="glass" size="lg"><a href="#how">See how it works</a></Button>
          </div>
          <ul className="mt-8 grid gap-3 text-sm text-muted-foreground sm:grid-cols-3">
            <li className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-primary" />Evidence-first anomaly triage</li>
            <li className="flex items-center gap-2"><Users className="h-4 w-4 text-primary" />Built for human investigation</li>
            <li className="flex items-center gap-2"><Cpu className="h-4 w-4 text-primary" />Powered by Gemma 4 via Gemini API</li>
          </ul>
        </div>
        <div className="relative">
          <div className="relative h-[340px] sm:h-[420px]" aria-hidden="true">
            {can3D ? (
              <Suspense fallback={<StaticValve />}><HeroScene /></Suspense>
            ) : (
              <StaticValve />
            )}
            {cards.map((c, i) => (
              <div key={c.t} className={`glass float-card absolute rounded-lg px-3 py-2 font-mono text-[11px] sm:text-xs ${c.pos}`} style={{ animationDelay: `${i * 1.2}s` }}>
                <span className={c.c}>●</span> {c.t}
              </div>
            ))}
          </div>
          <div className="relative z-10 mx-auto -mt-6 max-w-md">
            <FleetDemo />
          </div>
        </div>
      </div>
    </section>
  );
}
