import { Link } from "@tanstack/react-router";
import { Logo } from "./Logo";
import { GITHUB_URL } from "./Nav";

export const BOUNDARY =
  "An unusual reading does not automatically mean a valve is failing. ValveGuard flags anomalies for human investigation; it does not certify equipment safety or independently authorize repairs.";

export function Footer() {
  return (
    <footer className="border-t border-border bg-steel">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-6 md:grid-cols-4">
        <div className="md:col-span-2">
          <Logo />
          <p className="mt-3 text-sm text-muted-foreground">Investigate smarter. Maintain with evidence.</p>
          <p className="mt-6 max-w-md rounded-lg border border-warning/30 bg-warning/5 p-4 text-sm text-muted-foreground">{BOUNDARY}</p>
        </div>
        <div>
          <h3 className="text-sm font-semibold">Product</h3>
          <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
            <li><a href="/#how" className="hover:text-foreground">How it works</a></li>
            <li><a href="/#platform" className="hover:text-foreground">Platform</a></li>
            <li><a href="/#pricing" className="hover:text-foreground">Pricing</a></li>
            <li><a href="/#faq" className="hover:text-foreground">FAQ</a></li>
          </ul>
        </div>
        <div>
          <h3 className="text-sm font-semibold">Resources</h3>
          <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
            <li><Link to="/docs" className="hover:text-foreground">Documentation</Link></li>
            <li><a href="/#ai" className="hover:text-foreground">Model details</a></li>
            <li><a href={GITHUB_URL} target="_blank" rel="noreferrer" className="hover:text-foreground">GitHub</a></li>
            <li><Link to="/login" className="hover:text-foreground">Log in</Link></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-border">
        <p className="mx-auto max-w-7xl px-4 py-6 font-mono text-xs text-muted-foreground sm:px-6">
          ValveGuard is a decision-support prototype. It does not certify equipment safety, predict failures with certainty, or independently authorize repairs. © 2026 ValveGuard.
        </p>
      </div>
    </footer>
  );
}
