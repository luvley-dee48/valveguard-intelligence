import { createFileRoute, Link } from "@tanstack/react-router";
import { Nav } from "@/components/site/Nav";
import { Footer } from "@/components/site/Footer";

export const Route = createFileRoute("/docs")({
  head: () => ({
    meta: [
      { title: "Documentation — ValveGuard" },
      { name: "description", content: "How ValveGuard's anomaly checks and Gemma 4 investigation reports work." },
      { property: "og:title", content: "Documentation — ValveGuard" },
      { property: "og:description", content: "Getting started with ValveGuard's evidence-first valve triage." },
    ],
  }),
  component: Docs,
});

const sections = [
  ["Getting started", "Create a free account and load the simulated demo fleet of 20 valves. No live equipment is required."],
  ["Data inputs", "Valve telemetry (position, response time, pressure, temperature, vibration), equipment metadata, maintenance history and optional inspection photos."],
  ["Anomaly checks", "Deterministic rules compare readings to baselines, thresholds, trends and data-quality rules (e.g. flatlined sensors). Results are ranked by evidence strength."],
  ["Investigation reports", "Gemma 4 (gemma-4-31b-it via the Gemini API) receives only verified findings and drafts Evidence, Likely explanations, Recommended first action, Data gaps and Confidence for human review."],
  ["Human review", "Technicians mark each report Accept, Needs more data, or False positive. ValveGuard never authorizes repairs."],
];

function Docs() {
  return (
    <>
      <Nav />
      <main className="mx-auto max-w-3xl px-4 py-20 sm:px-6">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-primary">Documentation · preview</p>
        <h1 className="mt-3 text-4xl font-semibold">ValveGuard documentation</h1>
        <p className="mt-4 text-muted-foreground">A short overview of the prototype. Full documentation is a placeholder.</p>
        <div className="mt-10 space-y-4">
          {sections.map(([t, d]) => (
            <section key={t} className="glass rounded-xl p-5"><h2 className="text-lg font-semibold">{t}</h2><p className="mt-2 text-sm text-muted-foreground">{d}</p></section>
          ))}
        </div>
        <Link to="/signup" className="mt-10 inline-block text-primary hover:underline">Try the demo fleet →</Link>
      </main>
      <Footer />
    </>
  );
}
