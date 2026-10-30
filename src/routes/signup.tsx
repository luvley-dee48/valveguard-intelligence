import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { Database, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AuthShell, Field, GoogleButton, emailOk } from "@/components/site/AuthShell";
import { FleetDemo } from "@/components/site/FleetDemo";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/signup")({
  validateSearch: (s: Record<string, unknown>): { onboard?: boolean } => (s.onboard ? { onboard: true } : {}),
  head: () => ({
    meta: [
      { title: "Sign up free — ValveGuard" },
      { name: "description", content: "Create a free ValveGuard account: up to 25 valves and 50 Gemma 4 investigation reports per month." },
      { property: "og:title", content: "Sign up free — ValveGuard" },
      { property: "og:description", content: "Start investigating valve anomalies with evidence-backed reports." },
    ],
  }),
  component: Signup,
});

export function passwordScore(p: string) {
  let s = 0;
  if (p.length >= 8) s++;
  if (p.length >= 12) s++;
  if (/[A-Z]/.test(p) && /[a-z]/.test(p)) s++;
  if (/\d/.test(p) && /[^A-Za-z0-9]/.test(p)) s++;
  return s;
}
const LABELS = ["Too weak", "Weak", "Fair", "Good", "Strong"];
const COLORS = ["bg-destructive", "bg-destructive", "bg-warning", "bg-primary", "bg-success"];

function Onboarding() {
  const [loaded, setLoaded] = useState(false);
  return (
    <div>
      <p className="font-mono text-xs text-success"><Check className="mr-1 inline h-3.5 w-3.5" />Account ready (simulated)</p>
      <h1 className="mt-2 text-2xl font-semibold">Connect demo fleet</h1>
      <p className="mt-1 text-sm text-muted-foreground">Explore ValveGuard with 20 simulated valves before connecting any live equipment.</p>
      {!loaded ? (
        <Button variant="hero" size="lg" className="mt-6 w-full" onClick={() => setLoaded(true)}><Database />Load simulated valves</Button>
      ) : (
        <div className="mt-6 space-y-4">
          <FleetDemo />
          <Button asChild variant="glass" className="w-full"><Link to="/" hash="platform">Explore the platform</Link></Button>
        </div>
      )}
    </div>
  );
}

function Signup() {
  const { onboard } = Route.useSearch();
  const [f, setF] = useState({ name: "", email: "", company: "", pw: "" });
  const [agree, setAgree] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [done, setDone] = useState(false);
  const score = passwordScore(f.pw);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const er: Record<string, string> = {};
    if (!f.name.trim()) er.name = "Enter your full name.";
    if (!emailOk(f.email)) er.email = "Enter a valid work email.";
    if (!f.company.trim()) er.company = "Enter your company.";
    if (score < 2) er.pw = "Use at least 8 characters with mixed case, numbers or symbols.";
    if (!agree) er.agree = "You must agree to continue.";
    setErrors(er);
    if (!Object.keys(er).length) setDone(true);
  };

  if (done || onboard) return <AuthShell><Onboarding /></AuthShell>;

  return (
    <AuthShell>
      <h1 className="text-2xl font-semibold">Create your free account</h1>
      <p className="mt-1 text-sm text-muted-foreground">Free plan includes up to 25 valves and 50 Gemma 4 investigation reports per month.</p>
      <form className="mt-6 space-y-4" onSubmit={submit} noValidate>
        <Field id="name" label="Full name" autoComplete="name" value={f.name} onChange={set("name")} error={errors.name} />
        <Field id="email" label="Work email" type="email" autoComplete="email" value={f.email} onChange={set("email")} error={errors.email} />
        <Field id="company" label="Company" autoComplete="organization" value={f.company} onChange={set("company")} error={errors.company} />
        <div>
          <Field id="pw" label="Password" type="password" autoComplete="new-password" value={f.pw} onChange={set("pw")} error={errors.pw} />
          <div className="mt-2 flex gap-1" aria-hidden="true">
            {[0, 1, 2, 3].map((i) => <span key={i} className={cn("h-1 flex-1 rounded-full transition-colors", i < score ? COLORS[score] : "bg-muted")} />)}
          </div>
          {f.pw && <p className="mt-1 font-mono text-[11px] text-muted-foreground" aria-live="polite">Strength: {LABELS[score]}</p>}
        </div>
        <div>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="mt-0.5 h-4 w-4 accent-primary" aria-invalid={!!errors.agree} />
            <span>I agree to the <a href="#" className="text-primary hover:underline">Terms</a> and <a href="#" className="text-primary hover:underline">Privacy Policy</a>.</span>
          </label>
          {errors.agree && <p className="mt-1 text-xs text-destructive">{errors.agree}</p>}
        </div>
        <Button variant="hero" size="lg" className="w-full">Create free account</Button>
      </form>
      <div className="my-5 flex items-center gap-3 text-xs text-muted-foreground"><span className="h-px flex-1 bg-border" />or<span className="h-px flex-1 bg-border" /></div>
      <GoogleButton />
      <p className="mt-6 text-center text-sm text-muted-foreground">Already have an account? <Link to="/login" className="text-primary hover:underline">Log in</Link></p>
    </AuthShell>
  );
}
