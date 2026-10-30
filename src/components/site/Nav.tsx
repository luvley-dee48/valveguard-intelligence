import { Link } from "@tanstack/react-router";
import { Menu, X, Github } from "lucide-react";
import { useEffect, useState } from "react";
import { Logo } from "./Logo";
import { Button } from "@/components/ui/button";

export const GITHUB_URL = "https://github.com/";

const links = [
  { label: "Product", href: "/#product" },
  { label: "How it works", href: "/#how" },
  { label: "Platform", href: "/#platform" },
  { label: "AI", href: "/#ai" },
  { label: "Pricing", href: "/#pricing" },
  { label: "FAQ", href: "/#faq" },
];

export function Nav() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/70 backdrop-blur-xl">
      <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6" aria-label="Main">
        <Logo />
        <ul className="hidden items-center gap-1 lg:flex">
          {links.map((l) => (
            <li key={l.label}><a href={l.href} className="rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground">{l.label}</a></li>
          ))}
          <li><Link to="/docs" className="rounded-md px-3 py-2 text-sm text-muted-foreground hover:text-foreground">Docs</Link></li>
          <li><a href={GITHUB_URL} target="_blank" rel="noreferrer" className="flex items-center gap-1 rounded-md px-3 py-2 text-sm text-muted-foreground hover:text-foreground"><Github className="h-4 w-4" />GitHub</a></li>
        </ul>
        <div className="hidden items-center gap-2 lg:flex">
          <Button asChild variant="ghost" size="sm"><Link to="/login">Log in</Link></Button>
          <Button asChild variant="hero" size="sm"><Link to="/signup">Sign up free</Link></Button>
        </div>
        <button className="rounded-md p-2 lg:hidden" aria-label="Open menu" aria-expanded={open} onClick={() => setOpen(true)}><Menu /></button>
      </nav>
      {open && (
        <div className="fixed inset-0 z-50 flex flex-col bg-background blueprint lg:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <div className="flex h-16 items-center justify-between border-b border-border px-4">
            <Logo />
            <button className="rounded-md p-2" aria-label="Close menu" onClick={() => setOpen(false)}><X /></button>
          </div>
          <ul className="flex flex-col gap-1 p-6 font-display text-2xl">
            {links.map((l) => <li key={l.label}><a href={l.href} onClick={() => setOpen(false)} className="block py-2 hover:text-primary">{l.label}</a></li>)}
            <li><Link to="/docs" onClick={() => setOpen(false)} className="block py-2 hover:text-primary">Docs</Link></li>
            <li><a href={GITHUB_URL} target="_blank" rel="noreferrer" className="block py-2 hover:text-primary">GitHub</a></li>
          </ul>
          <div className="mt-auto grid gap-3 p-6">
            <Button asChild variant="glass" size="lg"><Link to="/login">Log in</Link></Button>
            <Button asChild variant="hero" size="lg"><Link to="/signup">Sign up free</Link></Button>
          </div>
        </div>
      )}
    </header>
  );
}
