import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { AuthShell, Field, GoogleButton, emailOk } from "@/components/site/AuthShell";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Log in — ValveGuard" },
      { name: "description", content: "Log in to ValveGuard to review ranked, evidence-backed valve investigation reports." },
      { property: "og:title", content: "Log in — ValveGuard" },
      { property: "og:description", content: "Access your ValveGuard fleet overview and investigation reports." },
    ],
  }),
  component: Login,
});

function Login() {
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [errors, setErrors] = useState<{ email?: string; pw?: string }>({});
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const er: typeof errors = {};
    if (!emailOk(email)) er.email = "Enter a valid work email.";
    if (pw.length < 8) er.pw = "Password must be at least 8 characters.";
    setErrors(er);
    if (Object.keys(er).length) return;
    setBusy(true);
    setTimeout(() => nav({ to: "/signup", search: { onboard: true } }), 600);
  };

  return (
    <AuthShell>
      <h1 className="text-2xl font-semibold">Log in</h1>
      <p className="mt-1 text-sm text-muted-foreground">Welcome back to ValveGuard.</p>
      <form className="mt-6 space-y-4" onSubmit={submit} noValidate>
        <Field id="email" label="Email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} error={errors.email} />
        <Field id="password" label="Password" type="password" autoComplete="current-password" value={pw} onChange={(e) => setPw(e.target.value)} error={errors.pw} />
        <div className="text-right">
          <button type="button" onClick={() => setMsg("Password reset is simulated in this prototype.")} className="text-sm text-primary hover:underline">Forgot password?</button>
        </div>
        {msg && <p role="status" className="text-xs text-muted-foreground">{msg}</p>}
        <Button variant="hero" className="w-full" size="lg" disabled={busy}>{busy ? "Logging in…" : "Log in"}</Button>
      </form>
      <div className="my-5 flex items-center gap-3 text-xs text-muted-foreground"><span className="h-px flex-1 bg-border" />or<span className="h-px flex-1 bg-border" /></div>
      <GoogleButton />
      <p className="mt-6 text-center text-sm text-muted-foreground">New to ValveGuard? <Link to="/signup" className="text-primary hover:underline">Sign up free</Link></p>
    </AuthShell>
  );
}
