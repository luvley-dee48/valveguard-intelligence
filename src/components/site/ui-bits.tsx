import { motion, useInView, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { priorityStyle, type Priority } from "@/lib/fleet";

export function Reveal({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.45, delay, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}

export function DemoBadge({ label = "Simulated demo data" }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-warning/30 bg-warning/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-warning">
      <span className="h-1.5 w-1.5 rounded-full bg-warning" />{label}
    </span>
  );
}

export function PriorityBadge({ p }: { p: Priority }) {
  return <span className={cn("inline-flex whitespace-nowrap rounded-md border px-2 py-0.5 font-mono text-[11px]", priorityStyle[p])}>{p}</span>;
}

export function Sparkline({ data, className = "stroke-primary" }: { data: number[]; className?: string }) {
  const min = Math.min(...data), max = Math.max(...data);
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * 100},${28 - ((v - min) / (max - min || 1)) * 24}`).join(" ");
  return (
    <svg viewBox="0 0 100 30" className="h-6 w-20" aria-hidden="true" preserveAspectRatio="none">
      <polyline points={pts} fill="none" className={className} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export function CountUp({ to, suffix = "" }: { to: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const reduce = useReducedMotion();
  const [v, setV] = useState(0);
  useEffect(() => {
    if (!inView) return;
    if (reduce) return setV(to);
    const start = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min((t - start) / 900, 1);
      setV(Math.round(to * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, to, reduce]);
  return <span ref={ref}>{v}{suffix}</span>;
}

export function SectionHead({ eyebrow, title, body }: { eyebrow: string; title: ReactNode; body?: ReactNode }) {
  return (
    <Reveal className="mx-auto max-w-3xl text-center">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-primary">{eyebrow}</p>
      <h2 className="mt-3 text-3xl font-semibold sm:text-5xl">{title}</h2>
      {body && <p className="mt-5 text-base leading-relaxed text-muted-foreground sm:text-lg">{body}</p>}
    </Reveal>
  );
}
