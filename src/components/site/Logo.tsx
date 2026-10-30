import { Link } from "@tanstack/react-router";

export function LogoMark({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <path d="M16 3 27 7v8c0 7-4.6 11.6-11 14-6.4-2.4-11-7-11-14V7z" fill="none" stroke="currentColor" strokeOpacity=".55" strokeWidth="1.8" />
      <circle cx="16" cy="15" r="5" fill="none" stroke="currentColor" strokeOpacity=".55" strokeWidth="1.8" />
      <path d="M16 10v-3M16 20v3M11 15H8M21 15h3" stroke="currentColor" strokeOpacity=".4" strokeWidth="1.5" />
      <path d="M4 15h7l2-3.5 3 7 2-3.5h10" fill="none" className="stroke-primary" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 font-display text-lg font-semibold tracking-tight" aria-label="ValveGuard home">
      <LogoMark />
      <span>Valve<span className="text-primary">Guard</span></span>
    </Link>
  );
}
