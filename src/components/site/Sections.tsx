import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { motion, useInView, useReducedMotion } from "framer-motion";
import {
  Activity, AlertTriangle, HelpCircle, Layers, Database, Radar, FileText, Search, Check, X, CircleHelp,
  ArrowRight, Sparkles, Cloud, Cpu, Wrench, Radio, Gauge, ShieldAlert, Lock, FlaskConical, Users, Github, BookOpen,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { FLEET, type Priority } from "@/lib/fleet";
import { cn } from "@/lib/utils";
import { CountUp, DemoBadge, PriorityBadge, Reveal, SectionHead, Sparkline } from "./ui-bits";
import { BOUNDARY } from "./Footer";
import { GITHUB_URL } from "./Nav";

/* ---------- Partner strip ---------- */
const marks = [
  { icon: Radio, t: "Industrial IoT" },
  { icon: Cpu, t: "Edge telemetry" },
  { icon: Gauge, t: "Asset performance" },
  { icon: Cloud, t: "Cloud data platforms" },
  { icon: Wrench, t: "Maintenance systems" },
];
export function PartnerStrip() {
  return (
    <section aria-label="Technology categories" className="border-y border-border bg-steel py-8">
      <div className="mx-auto flex max-w-7xl flex-col items-center gap-6 px-4 sm:px-6 md:flex-row">
        <div className="shrink-0 text-center md:text-left">
          <p className="text-sm text-muted-foreground">Built with modern industrial AI infrastructure</p>
          <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">Illustrative categories · not partnerships</p>
        </div>
        <motion.a
          href="#ai"
          initial={{ opacity: 0, scale: 0.9 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.4 }}
          className="glow-ring shrink-0 rounded-full border border-primary/50 bg-primary/10 px-4 py-2 font-mono text-sm text-primary hover:bg-primary/20"
        >
          <Sparkles className="mr-1.5 inline h-4 w-4" />Gemma 4 · Gemini API
        </motion.a>
        <div className="relative w-full overflow-hidden [mask-image:linear-gradient(90deg,transparent,black_10%,black_90%,transparent)]">
          <div className="marquee flex w-max gap-10">
            {[...marks, ...marks].map((m, i) => (
              <span key={i} className="flex items-center gap-2 whitespace-nowrap text-muted-foreground/70 grayscale" aria-hidden={i >= marks.length}>
                <m.icon className="h-5 w-5" /><span className="font-display text-sm">{m.t}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

/* ---------- Problem ---------- */
function Stream() {
  const rows = Array.from({ length: 12 }, (_, i) => `V-${101 + i}  ${(40 + ((i * 17) % 30)).toFixed(1)} psi  ${(i * 7) % 60}ms`);
  return (
    <div className="h-24 overflow-hidden rounded-md bg-steel p-2 font-mono text-[11px] text-primary/80" aria-hidden="true">
      <div className="ticker">{[...rows, ...rows].map((r, i) => <div key={i}>{r}</div>)}</div>
    </div>
  );
}
export function Problem() {
  const cards = [
    { title: "Too many readings", copy: "Dozens or hundreds of valves produce continuous readings.", visual: <Stream />, icon: Activity },
    {
      title: "Unexplained alerts", copy: "An alert without context creates uncertainty, not action.", icon: AlertTriangle,
      visual: <div className="flex h-24 items-center justify-center rounded-md bg-steel"><div className="relative"><AlertTriangle className="h-12 w-12 text-warning" /><HelpCircle className="absolute -right-4 -top-2 h-6 w-6 text-muted-foreground pulse-dot" /></div></div>,
    },
    {
      title: "Unclear priorities", copy: "Technicians need to know what to inspect first—and why.", icon: Layers,
      visual: (
        <div className="flex h-24 items-end justify-center gap-4 rounded-md bg-steel p-3">
          {["bg-warning", "bg-destructive", "bg-warning"].map((c, i) => (
            <div key={i} className="flex flex-col items-center gap-1">
              <span className={cn("h-2 w-2 rounded-full pulse-dot", c)} style={{ animationDelay: `${i * 0.4}s` }} />
              <svg viewBox="0 0 24 24" className="h-10 w-10 text-muted-foreground"><path d="M2 14h6l4-4 4 4h6M12 10V4M8 4h8" fill="none" stroke="currentColor" strokeWidth="1.5" /></svg>
            </div>
          ))}
        </div>
      ),
    },
  ];
  return (
    <section className="mx-auto max-w-7xl px-4 py-24 sm:px-6">
      <SectionHead
        eyebrow="The problem"
        title="Manual review does not scale."
        body="Maintenance teams may monitor dozens or hundreds of valves. When readings become unusual, technicians must determine which assets deserve attention, what evidence supports the concern, and what to inspect first. Manual review takes time, while poorly explained alerts can create unnecessary inspections or cause important warning signs to be overlooked."
      />
      <div className="mt-14 grid gap-5 md:grid-cols-3">
        {cards.map((c, i) => (
          <Reveal key={c.title} delay={i * 0.08} className="glass noise glow-hover rounded-2xl p-5">
            {c.visual}
            <h3 className="mt-5 flex items-center gap-2 text-lg font-semibold"><c.icon className="h-5 w-5 text-primary" />{c.title}</h3>
            <p className="mt-2 text-sm text-muted-foreground">{c.copy}</p>
          </Reveal>
        ))}
      </div>
      <Reveal className="mt-14 text-center font-display text-xl text-foreground sm:text-2xl">
        ValveGuard replaces guesswork with <span className="text-primary">ranked, evidence-backed investigation.</span>
      </Reveal>
    </section>
  );
}

/* ---------- How it works ---------- */
function Connector() {
  return (
    <svg className="hidden h-6 w-full md:block" viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true">
      <line x1="0" y1="5" x2="100" y2="5" className="stroke-border" strokeWidth="2" vectorEffect="non-scaling-stroke" />
      <line x1="0" y1="5" x2="100" y2="5" className="stroke-primary flow-line" strokeWidth="2" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
export function HowItWorks() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-120px" });
  const steps = [
    { icon: Database, n: "01", t: "Collect readings", d: "Connect valve telemetry, maintenance metadata, and optional inspection photos." },
    { icon: Radar, n: "02", t: "Detect unusual behaviour", d: "Deterministic anomaly checks compare readings against baselines, thresholds, trends, and data-quality rules." },
    { icon: FileText, n: "03", t: "Generate an investigation report", d: "Gemma 4, accessed through the Gemini API, translates verified technical findings into a clear, evidence-backed report for human review." },
  ];
  const fields = [
    ["Evidence", "Response time +68% / 24h, position deviation 11%"],
    ["Likely explanations", "Positioner degradation · Actuator friction"],
    ["Recommended first action", "Review positioner diagnostics"],
    ["Data gaps", "Recent maintenance history"],
    ["Confidence", "72%"],
  ];
  return (
    <section id="how" className="relative scroll-mt-20 border-t border-border blueprint py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <SectionHead eyebrow="How it works" title="From raw readings to a report you can act on." />
        <div className="mt-14 grid items-center gap-4 md:grid-cols-[1fr_60px_1fr_60px_1fr]">
          {steps.map((s, i) => (
            <div key={s.n} className="contents">
              <Reveal delay={i * 0.12} className="glass noise glow-hover h-full rounded-2xl p-6">
                <div className="flex items-center justify-between">
                  <s.icon className="h-6 w-6 text-primary" />
                  <span className="font-mono text-xs text-muted-foreground">STEP {s.n}</span>
                </div>
                <h3 className="mt-5 text-lg font-semibold">{s.t}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{s.d}</p>
              </Reveal>
              {i < 2 && <Connector />}
            </div>
          ))}
        </div>

        <div ref={ref} className="mt-12 grid gap-5 lg:grid-cols-[1fr_1fr_1.3fr]">
          <div className="glass rounded-2xl p-5">
            <p className="font-mono text-xs text-muted-foreground">TELEMETRY IN</p>
            <div className="mt-3 grid grid-cols-5 gap-1.5">
              {FLEET.slice(0, 10).map((v) => <div key={v.id} className="rounded bg-muted py-1 text-center font-mono text-[10px] text-muted-foreground">{v.id}</div>)}
            </div>
          </div>
          <div className="glass rounded-2xl p-5">
            <p className="font-mono text-xs text-muted-foreground">ANOMALY ENGINE</p>
            <div className="mt-3 grid grid-cols-5 gap-1.5">
              {FLEET.slice(0, 10).map((v) => (
                <div key={v.id} className={cn("rounded py-1 text-center font-mono text-[10px] transition-all duration-500",
                  inView && v.id === "V-107" ? "bg-warning/25 text-warning glow-ring" : "bg-muted text-muted-foreground/50")}>{v.id}</div>
              ))}
            </div>
            <p className="mt-3 font-mono text-[11px] text-warning">{inView ? "1 valve flagged: V-107" : "scanning…"}</p>
          </div>
          <div className="glass glow-ring rounded-2xl p-5">
            <div className="flex items-center justify-between">
              <p className="font-mono text-xs text-primary">AI REPORT · V-107</p><DemoBadge />
            </div>
            <dl className="mt-3 space-y-2">
              {fields.map(([k, v], i) => (
                <motion.div key={k} initial={{ opacity: 0, x: 12 }} animate={inView ? { opacity: 1, x: 0 } : {}} transition={{ delay: 0.5 + i * 0.12, duration: 0.3 }}
                  className="flex flex-col border-b border-border pb-2 text-sm sm:flex-row sm:gap-3">
                  <dt className="w-44 shrink-0 text-muted-foreground">{k}</dt><dd className="font-mono text-xs leading-5">{v}</dd>
                </motion.div>
              ))}
            </dl>
          </div>
        </div>
        <Reveal className="mx-auto mt-10 max-w-3xl rounded-xl border border-warning/40 bg-warning/5 p-4 text-center text-sm text-foreground">
          <ShieldAlert className="mr-2 inline h-4 w-4 text-warning" />
          ValveGuard supports investigation. It does not replace qualified maintenance, process-safety, or engineering procedures.
        </Reveal>
      </div>
    </section>
  );
}

/* ---------- Platform ---------- */
const filters: (Priority | "All")[] = ["All", "Normal", "Inspect soon", "Urgent review", "Verify sensor"];
function FleetPreview() {
  const [f, setF] = useState<(typeof filters)[number]>("All");
  const [q, setQ] = useState("");
  const rows = FLEET.filter((v) => (f === "All" || v.status === f) && v.id.toLowerCase().includes(q.toLowerCase()));
  const anomalies = FLEET.filter((v) => v.status !== "Normal").length;
  return (
    <div className="glass noise glow-hover flex flex-col rounded-2xl p-5 sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <div><h3 className="text-xl font-semibold">Fleet Overview</h3><p className="mt-1 text-sm text-muted-foreground">See the health of your valve fleet and prioritize the assets that need investigation.</p></div>
        <DemoBadge label="Demo data" />
      </div>
      <div className="mt-5 grid grid-cols-3 gap-3">
        {[["Fleet health", <CountUp key="a" to={85} suffix="%" />, "text-success"], ["Valves", <CountUp key="b" to={20} />, "text-foreground"], ["Anomalies", <CountUp key="c" to={anomalies} />, "text-warning"]].map(([l, v, c]) => (
          <div key={l as string} className="rounded-lg border border-border bg-steel p-3">
            <p className="text-[11px] text-muted-foreground">{l}</p><p className={cn("font-mono text-2xl", c as string)}>{v}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap gap-1.5" role="group" aria-label="Filter by status">
        {filters.map((x) => (
          <button key={x} onClick={() => setF(x)} aria-pressed={f === x}
            className={cn("rounded-md border px-2 py-1 text-xs transition-colors", f === x ? "border-primary/50 bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground")}>{x}</button>
        ))}
      </div>
      <label className="relative mt-3 block">
        <span className="sr-only">Search valves</span>
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search valve ID…" className="w-full rounded-md border border-input bg-steel py-2 pl-8 pr-3 font-mono text-sm placeholder:text-muted-foreground" />
      </label>
      <div className="mt-3 h-64 overflow-auto rounded-lg border border-border">
        <table className="w-full text-left text-xs">
          <thead className="sticky top-0 bg-card text-muted-foreground"><tr><th className="p-2 font-medium">Valve</th><th className="p-2 font-medium">Area</th><th className="p-2 font-medium">Trend</th><th className="p-2 font-medium">Priority</th></tr></thead>
          <tbody>
            {rows.map((v) => (
              <tr key={v.id} className="border-t border-border">
                <td className="p-2 font-mono">{v.id}</td><td className="p-2 text-muted-foreground">{v.area}</td>
                <td className="p-2"><Sparkline data={v.trend} className={v.status === "Normal" ? "stroke-success" : v.status === "Urgent review" ? "stroke-destructive" : v.status === "Verify sensor" ? "stroke-primary" : "stroke-warning"} /></td>
                <td className="p-2"><PriorityBadge p={v.status} /></td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan={4} className="p-4 text-center text-muted-foreground">No valves match.</td></tr>}
          </tbody>
        </table>
      </div>
      <Button asChild variant="glass" className="mt-5 self-start"><Link to="/signup">Open Fleet Overview <ArrowRight /></Link></Button>
    </div>
  );
}

function InvestigationPreview() {
  const [action, setAction] = useState<string | null>(null);
  const pts = Array.from({ length: 24 }, (_, i) => 30 + (i > 12 ? (i - 12) * 4.5 : 0) + Math.sin(i) * 3);
  const path = pts.map((v, i) => `${i === 0 ? "M" : "L"}${(i / 23) * 300},${110 - v}`).join(" ");
  return (
    <div className="glass noise glow-hover flex flex-col rounded-2xl p-5 sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <div><h3 className="text-xl font-semibold">Valve Investigation & AI Report</h3><p className="mt-1 text-sm text-muted-foreground">Inspect the evidence behind an anomaly and review an AI-generated investigation report.</p></div>
        <DemoBadge label="Demo data" />
      </div>
      <div className="mt-5 rounded-lg border border-border bg-steel p-3">
        <div className="flex items-center justify-between font-mono text-xs"><span>V-107 · Response time (ms)</span><PriorityBadge p="Inspect soon" /></div>
        <svg viewBox="0 0 300 110" className="mt-2 h-28 w-full" role="img" aria-label="Response time rising over the last 12 hours">
          <line x1="0" y1="72" x2="300" y2="72" className="stroke-success" strokeDasharray="4 4" strokeOpacity=".5" />
          <path d={path} fill="none" className="stroke-warning" strokeWidth="2" />
        </svg>
        <ol className="mt-1 flex justify-between font-mono text-[10px] text-muted-foreground">
          <li>−24h baseline</li><li className="text-warning">−12h deviation</li><li className="text-warning">now +68%</li>
        </ol>
      </div>
      <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <div className="rounded-lg border border-border p-3"><p className="text-xs text-muted-foreground">Evidence</p><p className="mt-1">Rising response time; position deviation 11%; pressure, temperature, vibration normal.</p></div>
        <div className="rounded-lg border border-border p-3">
          <p className="text-xs text-muted-foreground">Likely explanations</p>
          <ul className="mt-1 space-y-1 text-xs">
            {[["Positioner degradation", "High", "text-warning"], ["Actuator friction", "Medium", "text-primary"], ["Process upset", "Low", "text-muted-foreground"]].map(([a, b, c]) => (
              <li key={a} className="flex justify-between"><span>{a}</span><span className={cn("font-mono", c)}>{b}</span></li>
            ))}
          </ul>
        </div>
        <div className="rounded-lg border border-border p-3"><p className="text-xs text-muted-foreground">Recommended first action</p><p className="mt-1">Review positioner diagnostics.</p></div>
        <div className="rounded-lg border border-border p-3"><p className="text-xs text-muted-foreground">Data gaps</p><p className="mt-1">Maintenance history, fault codes.</p></div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Technician actions">
        {[["Accept", Check, "text-success"], ["Needs more data", CircleHelp, "text-warning"], ["False positive", X, "text-destructive"]].map(([l, I, c]) => {
          const Icon = I as typeof Check;
          return (
            <button key={l as string} onClick={() => setAction(l as string)} aria-pressed={action === l}
              className={cn("flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs transition-colors", action === l ? "border-primary/50 bg-primary/10" : "border-border hover:border-primary/30")}>
              <Icon className={cn("h-3.5 w-3.5", c as string)} />{l as string}
            </button>
          );
        })}
      </div>
      <p className="mt-2 h-4 font-mono text-[11px] text-muted-foreground" aria-live="polite">{action && `Recorded: "${action}" (demo only)`}</p>
      <Button asChild variant="glass" className="mt-3 self-start"><Link to="/signup">Open Investigation Report <ArrowRight /></Link></Button>
    </div>
  );
}

export function Platform() {
  return (
    <section id="platform" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-24 sm:px-6">
      <SectionHead eyebrow="Explore the platform" title="Two workspaces. One investigation trail." />
      <div className="mt-14 grid gap-6 lg:grid-cols-2">
        <Reveal><FleetPreview /></Reveal>
        <Reveal delay={0.1}><InvestigationPreview /></Reveal>
      </div>
    </section>
  );
}

/* ---------- AI ---------- */
const OUTPUT = [
  ["Assessment", "Inspect soon."],
  ["Confidence", "72%"],
  ["Evidence", "Rising response time with normal pressure and temperature makes actuator or positioner response degradation more plausible than a process upset."],
  ["Recommended first action", "Review positioner diagnostics and observe a non-intrusive partial-stroke response."],
  ["Data gaps", "Recent maintenance history and positioner fault codes."],
];
const FULL = OUTPUT.map(([k, v]) => `${k}: ${v}`).join("\n");

export function MeetAI() {
  const reduce = useReducedMotion();
  const [n, setN] = useState(0);
  const [running, setRunning] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-120px" });
  const run = () => {
    if (reduce) { setN(FULL.length); return; }
    setN(0); setRunning(true);
  };
  useEffect(() => { if (inView) run(); }, [inView]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!running) return;
    if (n >= FULL.length) { setRunning(false); return; }
    const t = setTimeout(() => setN((x) => Math.min(x + 4, FULL.length)), 16);
    return () => clearTimeout(t);
  }, [n, running]);
  const shown = FULL.slice(0, n);

  const points = [
    "Translate verified technical findings into understandable explanations.",
    "Identify missing evidence.",
    "Distinguish possible equipment degradation from sensor or data-quality issues.",
    "Draft inspection questions for human review.",
    "Recommend a cautious first investigation step.",
  ];
  return (
    <section id="ai" className="scroll-mt-20 border-y border-border bg-steel py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <SectionHead eyebrow="Meet the AI" title={<>Meet Gemma 4: <span className="text-primary">evidence first, action second.</span></>}
          body="Gemma 4, accessed through the Gemini API, works only on findings that ValveGuard's deterministic checks have already verified. It helps ValveGuard:" />
        <Reveal className="mx-auto mt-8 grid max-w-4xl gap-2 sm:grid-cols-2">
          {points.map((p) => <p key={p} className="flex gap-2 text-sm"><Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />{p}</p>)}
        </Reveal>
        <div ref={ref} className="mt-12 grid gap-5 lg:grid-cols-2">
          <div className="glass rounded-2xl p-5">
            <div className="flex items-center justify-between"><p className="font-mono text-xs text-muted-foreground">INPUT · VERIFIED FINDINGS</p><DemoBadge /></div>
            <p className="mt-4 font-mono text-sm leading-relaxed">Valve V-107: response time increased 68% over 24 hours. Position deviation: 11%. Pressure and temperature normal. Vibration normal.</p>
            <Button variant="glass" size="sm" className="mt-6" onClick={run} disabled={running}><Sparkles />{running ? "Generating…" : "Regenerate report"}</Button>
          </div>
          <div className="glass glow-ring rounded-2xl p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-mono text-xs text-primary">OUTPUT · DRAFT FOR HUMAN REVIEW</p>
              <span className="rounded-md border border-primary/40 px-2 py-0.5 font-mono text-[10px] text-primary">Model: gemma-4-31b-it · Gemini API</span>
            </div>
            <div className="mt-4 min-h-56 whitespace-pre-wrap font-mono text-sm leading-relaxed" aria-live="polite" aria-busy={running}>
              {shown.split("\n").map((line, i) => {
                const [k, ...rest] = line.split(": ");
                return <p key={i} className="mb-2"><span className="text-primary">{k}{rest.length ? ":" : ""}</span>{rest.length ? " " + rest.join(": ") : ""}</p>;
              })}
              {running && <span className="inline-block h-4 w-2 bg-primary pulse-dot align-middle" />}
            </div>
          </div>
        </div>
        <Reveal className="mx-auto mt-10 max-w-3xl rounded-xl border border-warning/40 bg-warning/5 p-4 text-center text-sm">
          <ShieldAlert className="mr-2 inline h-4 w-4 text-warning" />{BOUNDARY}
        </Reveal>
      </div>
    </section>
  );
}

/* ---------- Pricing ---------- */
function GaugeMeter({ value, label }: { value: number; label: string }) {
  const r = 26, c = Math.PI * r;
  return (
    <div className="flex items-center gap-3">
      <svg viewBox="0 0 60 34" className="h-9 w-16" aria-hidden="true">
        <path d="M4 30a26 26 0 0 1 52 0" fill="none" className="stroke-muted" strokeWidth="5" strokeLinecap="round" />
        <path d="M4 30a26 26 0 0 1 52 0" fill="none" className="stroke-primary" strokeWidth="5" strokeLinecap="round" strokeDasharray={`${c * value} ${c}`} />
      </svg>
      <span className="font-mono text-xs text-muted-foreground">{label}</span>
    </div>
  );
}

export function Pricing() {
  const [annual, setAnnual] = useState(false);
  const tiers = [
    { name: "Starter", price: "$0", unit: "free forever", best: "Small teams evaluating ValveGuard.", tag: "No credit card required", gauge: [0.1, "Up to 25 valves"] as const,
      lead: "", features: ["Up to 25 valves", "Daily anomaly checks", "Fleet Overview dashboard", "50 Gemma 4 investigation reports per month", "CSV upload", "Community support"], cta: "Sign up free", to: "/signup" as const },
    { name: "Professional", price: annual ? "$119" : "$149", unit: "per site / month", best: "Maintenance teams operating one plant or site.", tag: "Most popular", gauge: [0.55, "Up to 500 valves"] as const, featured: true,
      lead: "Everything in Starter, plus:", features: ["Up to 500 valves", "Real-time anomaly monitoring", "Unlimited investigation reports", "Valve Investigation & AI Report workspace", "Technician accept/reject feedback", "Role-based access", "Email support"], cta: "Start Professional trial", to: "/signup" as const },
    { name: "Enterprise", price: "Let’s talk", unit: "custom", best: "Multi-site industrial operations.", tag: "For regulated environments", gauge: [1, "Unlimited valves & sites"] as const,
      lead: "Everything in Professional, plus:", features: ["Unlimited valves and sites", "Private deployment options", "Custom baselines and integration support", "Audit trails", "SSO and advanced governance", "Dedicated success engineer"], cta: "Contact sales", href: "mailto:sales@valveguard.example" },
  ];
  return (
    <section id="pricing" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-24 sm:px-6">
      <SectionHead eyebrow="Pricing" title="Start free. Scale by site." />
      <div className="mt-8 flex items-center justify-center gap-3">
        <div className="glass inline-flex rounded-full p-1" role="group" aria-label="Billing period">
          {["Monthly", "Annual"].map((l) => (
            <button key={l} onClick={() => setAnnual(l === "Annual")} aria-pressed={annual === (l === "Annual")}
              className={cn("rounded-full px-4 py-1.5 text-sm transition-colors", annual === (l === "Annual") ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground")}>{l}</button>
          ))}
        </div>
        <span className="rounded-full border border-success/40 bg-success/10 px-2 py-0.5 font-mono text-xs text-success">Save 20%</span>
      </div>
      <div className="mt-12 grid gap-6 lg:grid-cols-3">
        {tiers.map((t, i) => (
          <Reveal key={t.name} delay={i * 0.08} className={cn("glass noise relative flex flex-col overflow-hidden rounded-2xl p-6", t.featured && "glow-ring border-primary/60 lg:-translate-y-3")}>
            {t.featured && (
              <svg className="absolute inset-x-0 top-0 h-1 w-full" viewBox="0 0 100 2" preserveAspectRatio="none" aria-hidden="true">
                <line x1="0" y1="1" x2="100" y2="1" className="stroke-primary flow-line" strokeWidth="2" vectorEffect="non-scaling-stroke" />
              </svg>
            )}
            <div className="flex items-center justify-between">
              <h3 className="text-xl font-semibold">{t.name}</h3>
              <span className={cn("rounded-full border px-2 py-0.5 font-mono text-[10px]", t.featured ? "border-primary/50 text-primary" : "border-border text-muted-foreground")}>{t.tag}</span>
            </div>
            <p className="mt-4"><span className="font-display text-4xl font-semibold">{t.price}</span> <span className="text-sm text-muted-foreground">{t.unit}</span></p>
            {t.featured && annual && <p className="font-mono text-xs text-success">Billed annually · save 20%</p>}
            <p className="mt-2 text-sm text-muted-foreground">Best for: {t.best}</p>
            <div className="mt-5"><GaugeMeter value={t.gauge[0]} label={t.gauge[1]} /></div>
            {t.lead && <p className="mt-5 text-xs font-medium text-muted-foreground">{t.lead}</p>}
            <ul className="mt-3 flex-1 space-y-2 text-sm">
              {t.features.map((f) => <li key={f} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />{f}</li>)}
            </ul>
            <Button asChild variant={t.featured ? "hero" : "glass"} className="mt-6 w-full">
              {t.to ? <Link to={t.to}>{t.cta}</Link> : <a href={t.href}>{t.cta}</a>}
            </Button>
          </Reveal>
        ))}
      </div>
      <p className="mt-8 text-center text-sm text-muted-foreground">All plans include evidence-first triage and human-review controls.</p>
      <p className="mt-1 text-center font-mono text-xs text-muted-foreground/70">Pricing shown for demonstration purposes.</p>
    </section>
  );
}

/* ---------- FAQ ---------- */
const FAQS = [
  [Activity, "Does ValveGuard predict valve failure?", "No. ValveGuard identifies unusual behaviour and produces evidence-backed investigation reports. It does not certify equipment safety or independently authorize repairs."],
  [Sparkles, "What does Gemma 4 do?", "Gemma 4, accessed through the Gemini API, helps translate verified technical findings into clear explanations, identify missing evidence, and draft inspection questions for human review."],
  [Users, "Can ValveGuard replace our maintenance team?", "No. ValveGuard is decision support. Technicians and qualified engineers remain responsible for inspection, maintenance, and safety decisions."],
  [Database, "What data does ValveGuard use?", "The MVP supports valve telemetry, equipment metadata, maintenance history, and optional inspection photos. Customers control what data they connect."],
  [Radar, "How does ValveGuard avoid unnecessary inspections?", "It ranks anomalies using transparent evidence, distinguishes equipment behaviour from possible sensor or data-quality issues, and identifies missing information before recommending action."],
  [Lock, "Is my plant data secure?", "ValveGuard is designed around least-privilege access and customer-controlled data connections. Enterprise plans can support private deployment and governance requirements."],
  [FlaskConical, "Can I try it without connecting live equipment?", "Yes. The demo uses simulated valve readings so you can explore Fleet Overview and the AI investigation workflow immediately."],
] as const;

export function FAQ() {
  return (
    <section id="faq" className="scroll-mt-20 border-t border-border py-24">
      <div className="mx-auto max-w-3xl px-4 sm:px-6">
        <SectionHead eyebrow="FAQ" title="Questions engineers ask." />
        <Accordion type="single" collapsible className="mt-12 space-y-3">
          {FAQS.map(([Icon, q, a], i) => (
            <AccordionItem key={q} value={`q${i}`} className="glass rounded-xl border px-4">
              <AccordionTrigger className="gap-3 text-base hover:no-underline">
                <span className="flex items-center gap-3"><Icon className="h-4 w-4 shrink-0 text-primary" />{q}</span>
              </AccordionTrigger>
              <AccordionContent className="pl-7 text-muted-foreground">{a}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </section>
  );
}

/* ---------- CTA ---------- */
export function FinalCTA() {
  return (
    <section className="relative overflow-hidden border-t border-border bg-steel py-28 blueprint">
      <svg className="absolute inset-0 h-full w-full opacity-40" viewBox="0 0 1200 400" preserveAspectRatio="none" aria-hidden="true">
        <path d="M0 200 H420 a40 40 0 0 1 40 -40 H740 a40 40 0 0 1 40 40 H1200" fill="none" className="stroke-border" strokeWidth="18" />
        <path d="M0 200 H420 a40 40 0 0 1 40 -40 H740 a40 40 0 0 1 40 40 H1200" fill="none" className="stroke-primary flow-line" strokeWidth="2" />
        <path d="M0 320 H1200" fill="none" className="stroke-primary flow-line" strokeOpacity=".5" strokeWidth="1.5" />
      </svg>
      <Reveal className="relative mx-auto max-w-3xl px-4 text-center">
        <h2 className="text-4xl font-semibold sm:text-5xl">Ready to investigate smarter?</h2>
        <p className="mt-5 text-lg text-muted-foreground">Turn valve readings into clear, evidence-backed priorities for your maintenance team.</p>
        <Button asChild variant="hero" size="lg" className="mt-8"><Link to="/signup">Launch ValveGuard <ArrowRight /></Link></Button>
        <div className="mt-6 flex flex-wrap justify-center gap-6 text-sm text-muted-foreground">
          <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 hover:text-primary"><Github className="h-4 w-4" />View GitHub</a>
          <Link to="/docs" className="flex items-center gap-1.5 hover:text-primary"><BookOpen className="h-4 w-4" />Read documentation</Link>
          <a href="#ai" className="flex items-center gap-1.5 hover:text-primary"><Cpu className="h-4 w-4" />Model details</a>
        </div>
      </Reveal>
    </section>
  );
}
