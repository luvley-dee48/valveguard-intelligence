import { createFileRoute, Link } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle, ArrowRight, Check, CircleHelp, Cpu, Database, Loader2, RefreshCw, ShieldCheck, Sparkles, X,
} from "lucide-react";
import { Nav } from "@/components/site/Nav";
import { Footer } from "@/components/site/Footer";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  ApiError,
  api,
  errorMessage,
  getStoredToken,
  storeToken,
  type AiCall,
  type AiStatus,
  type Priority,
  type Report,
  type Valve,
  type ValveDetail,
} from "@/lib/api";

export const Route = createFileRoute("/demo")({
  head: () => ({
    meta: [
      { title: "Live demo — ValveGuard" },
      {
        name: "description",
        content: "Run a real Gemma 4 investigation on 20 simulated valves and review the report it drafts.",
      },
      { property: "og:title", content: "Live demo — ValveGuard" },
      { property: "og:description", content: "Run a real Gemma 4 investigation on simulated valve telemetry." },
    ],
  }),
  component: DemoPage,
});

const PRIORITY: Record<Priority, { label: string; badge: string; tile: string }> = {
  urgent_review: {
    label: "Urgent review",
    badge: "border-destructive/50 bg-destructive/10 text-destructive",
    tile: "border-destructive/50 bg-destructive/25",
  },
  inspect_soon: {
    label: "Inspect soon",
    badge: "border-warning/50 bg-warning/10 text-warning",
    tile: "border-warning/50 bg-warning/25",
  },
  verify_sensor: {
    label: "Verify sensor",
    badge: "border-primary/50 bg-primary/10 text-primary",
    tile: "border-primary/50 bg-primary/25",
  },
  normal: {
    label: "Normal",
    badge: "border-success/40 bg-success/10 text-success",
    tile: "border-success/25 bg-success/15",
  },
};

const LIKELIHOOD: Record<string, string> = {
  high: "text-destructive",
  medium: "text-warning",
  low: "text-muted-foreground",
};
const URGENCY: Record<string, string> = {
  immediate: "text-destructive",
  within_24h: "text-warning",
  this_week: "text-primary",
  monitor: "text-muted-foreground",
};
const REVIEW_LABEL: Record<Report["review"], string> = {
  pending: "Pending review",
  accepted: "Accepted",
  needs_data: "Needs more data",
  false_positive: "False positive",
};

function num(v: number | null, unit = "", digits = 1): string {
  return v === null || v === undefined ? "—" : `${v.toFixed(digits)}${unit}`;
}

function DemoPage() {
  const [token, setToken] = useState<string | null>(null);
  const [valves, setValves] = useState<Valve[]>([]);
  const [status, setStatus] = useState<"booting" | "ready" | "error">("booting");
  const [error, setError] = useState("");
  const [ai, setAi] = useState<AiStatus | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [detail, setDetail] = useState<ValveDetail | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [calls, setCalls] = useState<AiCall[]>([]);
  const [running, setRunning] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [notice, setNotice] = useState("");

  const select = useCallback(async (tok: string, id: number) => {
    setSelected(id);
    setDetail(null);
    setReport(null);
    setNotice("");
    try {
      setDetail(await api.valve(tok, id));
    } catch (e) {
      setNotice(errorMessage(e));
    }
  }, []);

  const boot = useCallback(async () => {
    setStatus("booting");
    setError("");
    try {
      let tok = getStoredToken();
      let list: Valve[] | null = null;
      if (tok) {
        try {
          list = await api.valves(tok);
        } catch (e) {
          if (e instanceof ApiError && e.status === 401) tok = null;
          else throw e;
        }
      }
      if (!tok || !list) {
        const session = await api.createDemoSession();
        tok = session.token;
        storeToken(tok);
        list = await api.valves(tok);
      }
      setToken(tok);
      setValves(list);
      setCalls(await api.aiCalls(tok));
      setStatus("ready");
      const first =
        list.find((v) => v.priority === "urgent_review") ?? list.find((v) => v.priority !== "normal") ?? list[0];
      if (first) await select(tok, first.id);
    } catch (e) {
      setError(errorMessage(e));
      setStatus("error");
    }
  }, [select]);

  useEffect(() => {
    void boot();
    api
      .aiStatus()
      .then(setAi)
      .catch(() => setAi(null));
  }, [boot]);

  const runReport = async () => {
    if (!token || !selected) return;
    setRunning(true);
    setNotice("");
    try {
      setReport(await api.runReport(token, selected));
      setCalls(await api.aiCalls(token));
    } catch (e) {
      setNotice(errorMessage(e));
    } finally {
      setRunning(false);
    }
  };

  const review = async (decision: Report["review"]) => {
    if (!token || !report) return;
    setReviewing(true);
    setNotice("");
    try {
      setReport(await api.reviewReport(token, report.id, decision));
    } catch (e) {
      setNotice(errorMessage(e));
    } finally {
      setReviewing(false);
    }
  };

  const restart = () => {
    storeToken(null);
    setValves([]);
    setSelected(null);
    setDetail(null);
    setReport(null);
    setCalls([]);
    setNotice("");
    void boot();
  };

  const flagged = valves.filter((v) => v.priority !== "normal");

  return (
    <>
      <Nav />
      <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-primary">Live demo · real backend</p>
        <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold sm:text-4xl">Run an actual Gemma 4 investigation</h1>
            <p className="mt-3 max-w-2xl text-muted-foreground">
              Twenty simulated valves, real rule engine, real model call. The readings are fake; the database, the
              anomaly rules and the Gemini API request are not.
            </p>
          </div>
          <Button variant="glass" size="sm" onClick={restart} disabled={status === "booting"}>
            <RefreshCw className={cn("h-4 w-4", status === "booting" && "animate-spin")} /> New demo session
          </Button>
        </div>

        {status === "error" && (
          <div className="mt-8 rounded-xl border border-destructive/40 bg-destructive/5 p-5">
            <p className="flex items-center gap-2 font-medium text-destructive">
              <AlertTriangle className="h-4 w-4" /> The demo could not reach the ValveGuard API
            </p>
            <p className="mt-2 text-sm text-muted-foreground">{error}</p>
            <pre className="mt-3 overflow-x-auto rounded-md bg-steel p-3 font-mono text-xs text-muted-foreground">
              bash run.sh{"\n"}
              npm run dev
            </pre>
            <Button variant="glass" size="sm" className="mt-3" onClick={() => void boot()}>
              <RefreshCw className="h-4 w-4" /> Try again
            </Button>
          </div>
        )}

        {status === "booting" && (
          <div className="mt-10 flex items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
            <Loader2 className="h-4 w-4 animate-spin" /> Creating an isolated demo organisation and seeding 20 valves…
          </div>
        )}

        {status === "ready" && (
          <div className="mt-8 grid gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <section className="glass noise rounded-2xl p-5">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <h2 className="flex items-center gap-2 text-sm font-semibold">
                    <Database className="h-4 w-4 text-primary" /> Fleet overview
                  </h2>
                  <p className="font-mono text-[11px] text-muted-foreground">
                    {valves.length} valves · {flagged.length} flagged · GET /api/valves
                  </p>
                </div>
                <span className="rounded-full border border-warning/30 bg-warning/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-warning">
                  Simulated readings
                </span>
              </div>

              <div className="mt-4 grid grid-cols-5 gap-1.5 sm:grid-cols-10" role="group" aria-label="Select a valve">
                {valves.map((v) => (
                  <button
                    key={v.id}
                    type="button"
                    onClick={() => token && void select(token, v.id)}
                    aria-pressed={selected === v.id}
                    aria-label={`${v.tag}: ${PRIORITY[v.priority].label}`}
                    title={`${v.tag} · ${PRIORITY[v.priority].label}`}
                    className={cn(
                      "flex aspect-square items-center justify-center rounded-[5px] border font-mono text-[10px] transition-all",
                      PRIORITY[v.priority].tile,
                      v.priority === "normal" ? "text-success/70" : "text-foreground",
                      selected === v.id && "ring-2 ring-primary ring-offset-2 ring-offset-background",
                    )}
                  >
                    {v.tag.replace("V-", "")}
                  </button>
                ))}
              </div>

              <ul className="mt-4 space-y-1.5">
                {flagged.map((v) => (
                  <li
                    key={v.id}
                    className={cn(
                      "flex items-center justify-between gap-2 rounded-lg border border-transparent px-2 py-1.5 text-xs",
                      selected === v.id && "border-primary/40 bg-primary/5",
                    )}
                  >
                    <span className="font-mono text-foreground">{v.tag}</span>
                    <span className="flex-1 truncate text-muted-foreground">{v.finding}</span>
                    <span
                      className={cn(
                        "inline-flex whitespace-nowrap rounded-md border px-2 py-0.5 font-mono text-[11px]",
                        PRIORITY[v.priority].badge,
                      )}
                    >
                      {PRIORITY[v.priority].label}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-4 border-t border-border pt-3 text-xs text-muted-foreground">
                Health, priority and findings come from <span className="font-mono">app/analytics.py</span>. No model is
                involved in choosing what is flagged.
              </p>
            </section>

            <section className="glass rounded-2xl p-5">
              {!detail && <p className="text-sm text-muted-foreground">Loading the selected valve…</p>}
              {detail && (
                <>
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <h2 className="flex items-center gap-2 font-mono text-lg font-semibold">{detail.tag}</h2>
                      <p className="text-xs text-muted-foreground">
                        {detail.name} · {detail.area} · {detail.type}
                      </p>
                    </div>
                    <span
                      className={cn(
                        "inline-flex whitespace-nowrap rounded-md border px-2 py-0.5 font-mono text-[11px]",
                        PRIORITY[detail.priority].badge,
                      )}
                    >
                      {PRIORITY[detail.priority].label}
                    </span>
                  </div>

                  <dl className="mt-4 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
                    {[
                      ["Position", num(detail.position_pct, "%")],
                      ["Command", num(detail.command_pct, "%")],
                      ["Response", num(detail.response_ms, " ms", 0)],
                      ["Baseline", num(detail.baseline_response_ms, " ms", 0)],
                      ["Pressure", num(detail.pressure_bar, " bar", 2)],
                      ["Temperature", num(detail.temperature_c, " °C")],
                      ["Vibration", num(detail.vibration_mm_s, " mm/s", 2)],
                      ["Health", `${detail.health}/100`],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-lg border border-border bg-steel p-2">
                        <dt className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</dt>
                        <dd className="mt-0.5 font-mono text-foreground">{value}</dd>
                      </div>
                    ))}
                  </dl>

                  <div className="mt-4">
                    <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                      Rule findings sent to the model
                    </p>
                    {detail.findings.length === 0 ? (
                      <p className="mt-1 text-xs text-success">No rule fired. A report would honestly say so.</p>
                    ) : (
                      <ul className="mt-1 space-y-1 text-xs">
                        {detail.findings.map((f) => (
                          <li key={f.rule} className="rounded-md border border-border px-2 py-1.5">
                            <span className="font-mono text-foreground">{f.title}</span>
                            <span className="text-muted-foreground"> — {f.detail}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={() => void runReport()}
                    disabled={running}
                    className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg border border-primary/40 bg-primary/10 py-2.5 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:opacity-60"
                  >
                    {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                    {running ? "Waiting for the model…" : "Run Gemma 4 investigation"}
                  </button>

                  {ai && !ai.configured && (
                    <p className="mt-2 text-[11px] leading-relaxed text-warning">
                      GEMINI_API_KEY is not set on this server, so this run returns the labelled rule-based fallback.
                      Add the key to <span className="font-mono">.env</span> and restart the API for a real Gemma 4
                      report; the request path is identical.
                    </p>
                  )}

                  {notice && (
                    <p role="alert" className="mt-3 rounded-md border border-destructive/40 bg-destructive/5 p-2 text-xs text-destructive">
                      {notice}
                    </p>
                  )}

                  {report && <ReportCard report={report} onReview={review} busy={reviewing} />}
                </>
              )}
            </section>
          </div>
        )}

        <section className="mt-6 grid gap-4 lg:grid-cols-3">
          <div className="glass rounded-xl p-4">
            <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Exact model identifier</p>
            <p className="mt-2 break-all font-mono text-sm text-primary">{ai?.model ?? "gemma-4-26b-a4b-it"}</p>
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
              Default <span className="font-mono">GEMINI_MODEL</span> in <span className="font-mono">app/config.py</span>.
              <span className="font-mono"> gemma-4-31b-it</span> is the other hosted Gemma 4 size. A{" "}
              <span className="font-mono">gemini-*</span> id would be a different model family.
            </p>
          </div>
          <div className="glass rounded-xl p-4">
            <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Inference path</p>
            <p className="mt-2 break-all font-mono text-[11px] leading-relaxed text-foreground">
              {ai?.endpoint ?? "https://generativelanguage.googleapis.com/v1beta/models/gemma-4-26b-a4b-it:generateContent"}
            </p>
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
              Report button → <span className="font-mono">POST /api/valves/&#123;id&#125;/reports</span> →{" "}
              <span className="font-mono">app/api.py create_report()</span> →{" "}
              <span className="font-mono">app/ai.py diagnose() → _call_gemini()</span>.
            </p>
          </div>
          <div className="glass rounded-xl p-4">
            <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              What it contributes here
            </p>
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
              The summary, likely explanations, first action, next checks, data gaps, urgency and confidence you see in
              the report card. The model interprets findings the backend already computed; it never sets priority,
              raises alerts or authorises work.
            </p>
          </div>
        </section>

        <section className="glass mt-6 rounded-2xl p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <Cpu className="h-4 w-4 text-primary" /> Model call log
            </h2>
            <span className="font-mono text-[11px] text-muted-foreground">
              ai_calls · GET /api/system/ai-calls
            </span>
          </div>
          {calls.length === 0 ? (
            <p className="mt-3 text-xs text-muted-foreground">
              No calls yet. Run an investigation above and the row appears here with the model, the API-reported
              modelVersion, latency and any error.
            </p>
          ) : (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-xs">
                <thead className="text-muted-foreground">
                  <tr>
                    <th className="py-1.5 pr-3 font-medium">Time</th>
                    <th className="py-1.5 pr-3 font-medium">Valve</th>
                    <th className="py-1.5 pr-3 font-medium">Source</th>
                    <th className="py-1.5 pr-3 font-medium">Model</th>
                    <th className="py-1.5 pr-3 font-medium">API modelVersion</th>
                    <th className="py-1.5 pr-3 font-medium">Latency</th>
                    <th className="py-1.5 font-medium">Error</th>
                  </tr>
                </thead>
                <tbody>
                  {calls.map((c) => (
                    <tr key={c.id} className="border-t border-border">
                      <td className="py-1.5 pr-3 font-mono text-muted-foreground">{c.ts?.replace("T", " ").slice(5, 19)}</td>
                      <td className="py-1.5 pr-3 font-mono">{c.valve_tag ?? "—"}</td>
                      <td className="py-1.5 pr-3">
                        <span
                          className={cn(
                            "rounded border px-1.5 py-0.5 font-mono text-[10px]",
                            c.source === "gemini"
                              ? "border-success/40 bg-success/10 text-success"
                              : "border-warning/40 bg-warning/10 text-warning",
                          )}
                        >
                          {c.source}
                        </span>
                      </td>
                      <td className="py-1.5 pr-3 font-mono">{c.model ?? "—"}</td>
                      <td className="py-1.5 pr-3 font-mono">{c.api_model_version ?? "—"}</td>
                      <td className="py-1.5 pr-3 font-mono">{c.latency_ms} ms</td>
                      <td className="py-1.5 text-muted-foreground">{c.error ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <div className="mt-8 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warning/40 bg-warning/5 p-4 text-sm">
          <p className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-warning" />
            Decision support only. A person accepts or rejects every report; the model never authorises repairs.
          </p>
          <Link to="/signup" className="flex items-center gap-1 text-primary hover:underline">
            Create a real account <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </main>
      <Footer />
    </>
  );
}

function ReportCard({
  report,
  onReview,
  busy,
}: {
  report: Report;
  onReview: (decision: Report["review"]) => void;
  busy: boolean;
}) {
  const a = report.analysis;
  const live = report.source === "gemini";
  return (
    <div className="mt-4 rounded-xl border border-primary/30 bg-primary/[0.03] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-xs text-primary">
          REPORT #{report.id} · {report.valve_tag ?? "valve"}
        </p>
        <span
          className={cn(
            "rounded-md border px-2 py-0.5 font-mono text-[10px]",
            live ? "border-success/40 bg-success/10 text-success" : "border-warning/40 bg-warning/10 text-warning",
          )}
        >
          {live ? `${report.model} · Gemini API` : "Rule-based fallback"}
        </span>
      </div>

      <p className="mt-3 text-sm leading-relaxed">{a.summary}</p>

      <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
        <div className="rounded-lg border border-border p-2.5">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Likely explanations</p>
          <ul className="mt-1 space-y-1">
            {a.likely_explanations.map((e) => (
              <li key={e.cause} className="flex justify-between gap-2">
                <span>{e.cause}</span>
                <span className={cn("font-mono", LIKELIHOOD[e.likelihood] ?? "text-muted-foreground")}>{e.likelihood}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-lg border border-border p-2.5">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Recommended first action</p>
          <p className="mt-1">{a.recommended_first_action}</p>
        </div>
        <div className="rounded-lg border border-border p-2.5">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Next checks</p>
          <ul className="mt-1 space-y-0.5">
            {a.next_checks.length === 0 ? <li className="text-muted-foreground">—</li> : a.next_checks.map((c) => <li key={c}>· {c}</li>)}
          </ul>
        </div>
        <div className="rounded-lg border border-border p-2.5">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Data gaps</p>
          <ul className="mt-1 space-y-0.5">
            {a.data_gaps.length === 0 ? <li className="text-muted-foreground">—</li> : a.data_gaps.map((c) => <li key={c}>· {c}</li>)}
          </ul>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11px]">
        <span>
          urgency <span className={URGENCY[a.urgency] ?? "text-muted-foreground"}>{a.urgency.replace("_", " ")}</span>
        </span>
        <span>
          confidence <span className="text-foreground">{Math.round(a.confidence * 100)}%</span>
        </span>
        <span>
          latency <span className="text-foreground">{report.latency_ms} ms</span>
        </span>
        {report.error && <span className="text-warning">fallback reason: {report.error}</span>}
      </div>

      <div className="mt-3 border-t border-border pt-3">
        <div className="flex flex-wrap items-center gap-2">
          {([
            ["accepted", "Accept", Check, "text-success"],
            ["needs_data", "Needs more data", CircleHelp, "text-warning"],
            ["false_positive", "False positive", X, "text-destructive"],
          ] as const).map(([decision, label, Icon, color]) => (
            <button
              key={decision}
              type="button"
              disabled={busy}
              onClick={() => onReview(decision)}
              aria-pressed={report.review === decision}
              className={cn(
                "flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs transition-colors disabled:opacity-60",
                report.review === decision ? "border-primary/60 bg-primary/10" : "border-border hover:border-primary/40",
              )}
            >
              <Icon className={cn("h-3.5 w-3.5", color)} /> {label}
            </button>
          ))}
          <span className="font-mono text-[11px] text-muted-foreground" aria-live="polite">
            {REVIEW_LABEL[report.review]}
            {report.reviewed_by ? ` · ${report.reviewed_by}` : ""}
          </span>
        </div>
      </div>
    </div>
  );
}
