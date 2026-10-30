import type { ReactNode } from "react";
import { Logo } from "./Logo";
import { FleetDemo } from "./FleetDemo";
import { cn } from "@/lib/utils";

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen overflow-hidden blueprint">
      <svg className="pointer-events-none absolute inset-0 h-full w-full opacity-50" viewBox="0 0 1200 800" preserveAspectRatio="none" aria-hidden="true">
        <path d="M0 140 H500 V420 H1200" fill="none" className="stroke-primary flow-line" strokeOpacity=".4" strokeWidth="1.5" />
        <path d="M0 680 H760 V260 H1200" fill="none" className="stroke-primary flow-line" strokeOpacity=".3" strokeWidth="1.5" />
      </svg>
      <div className="relative mx-auto grid min-h-screen max-w-6xl items-center gap-10 px-4 py-10 sm:px-6 lg:grid-cols-2">
        <aside className="hidden lg:block">
          <Logo />
          <h2 className="mt-8 text-4xl font-semibold leading-tight">Know which valve needs attention first.</h2>
          <p className="mt-4 max-w-md text-muted-foreground">Ranked, evidence-backed investigation reports for maintenance teams—always reviewed by people.</p>
          <div className="mt-8 max-w-sm"><FleetDemo compact /></div>
        </aside>
        <main className="mx-auto w-full max-w-md">
          <div className="mb-6 lg:hidden"><Logo /></div>
          <div className="glass noise rounded-2xl p-6 sm:p-8">{children}</div>
          <p className="mt-4 text-center font-mono text-[11px] text-muted-foreground">Prototype · credentials are never stored or sent anywhere.</p>
        </main>
      </div>
    </div>
  );
}

export function Field({ id, label, error, ...props }: React.InputHTMLAttributes<HTMLInputElement> & { id: string; label: string; error?: string | undefined }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium">{label}</label>
      <input
        id={id}
        aria-invalid={!!error}
        aria-describedby={error ? `${id}-err` : undefined}
        className={cn("w-full rounded-lg border bg-steel px-3 py-2.5 text-sm outline-none transition-colors placeholder:text-muted-foreground focus:border-primary", error ? "border-destructive" : "border-input")}
        {...props}
      />
      {error && <p id={`${id}-err`} className="mt-1 text-xs text-destructive">{error}</p>}
    </div>
  );
}

export function GoogleButton() {
  return (
    <button type="button" onClick={() => alert("Google sign-in is not available in this prototype.")} className="flex w-full items-center justify-center gap-2 rounded-lg border border-input py-2.5 text-sm transition-colors hover:border-primary/40">
      <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden="true"><path fill="currentColor" d="M21.6 12.2c0-.7-.1-1.4-.2-2H12v3.8h5.4a4.6 4.6 0 0 1-2 3v2.5h3.2c1.9-1.7 3-4.3 3-7.3zM12 22c2.7 0 5-.9 6.6-2.4l-3.2-2.5c-.9.6-2 1-3.4 1-2.6 0-4.8-1.8-5.6-4.1H3.1v2.6A10 10 0 0 0 12 22zM6.4 14a6 6 0 0 1 0-3.9V7.5H3.1a10 10 0 0 0 0 9zM12 6c1.5 0 2.8.5 3.8 1.5l2.9-2.9A10 10 0 0 0 3.1 7.5L6.4 10C7.2 7.7 9.4 6 12 6z" /></svg>
      Continue with Google
    </button>
  );
}

export const emailOk = (e: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e);
