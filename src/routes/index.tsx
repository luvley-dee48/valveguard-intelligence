import { createFileRoute } from "@tanstack/react-router";
import { Nav } from "@/components/site/Nav";
import { Footer } from "@/components/site/Footer";
import { Hero } from "@/components/site/Hero";
import { FAQ, FinalCTA, HowItWorks, MeetAI, PartnerStrip, Platform, Pricing, Problem } from "@/components/site/Sections";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "ValveGuard — Evidence-backed valve maintenance intelligence" },
      { name: "description", content: "Turn unusual valve readings into ranked, evidence-backed investigation reports with Gemma 4 via the Gemini API." },
      { property: "og:title", content: "ValveGuard — Evidence-backed valve maintenance intelligence" },
      { property: "og:description", content: "Turn unusual valve readings into ranked, evidence-backed investigation reports with Gemma 4 via the Gemini API." },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <>
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground">Skip to content</a>
      <Nav />
      <main id="main">
        <Hero />
        <PartnerStrip />
        <Problem />
        <HowItWorks />
        <Platform />
        <MeetAI />
        <Pricing />
        <FAQ />
        <FinalCTA />
      </main>
      <Footer />
    </>
  );
}
