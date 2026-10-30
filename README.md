# ValveGuard Intelligence

Build a premium, responsive, accessible SaaS marketing website for “ValveGuard” — an industrial maintenance intelligence platform that turns valve and equipment readings into ranked, evidence-backed investigation reports.

Do not copy any existing website. Create an original, polished design inspired by modern industrial SaaS, control-room interfaces, and high-end engineering products.

## Brand and product positioning

Product name: ValveGuard

Tagline: Investigate smarter. Maintain with evidence.

ValveGuard helps industrial maintenance teams monitor dozens or hundreds of valves. When readings become unusual, technicians need to know which equipment deserves attention, what evidence supports the concern, and what to inspect first.

Core promise:

“Turn unusual valve readings into ranked, evidence-backed investigation reports.”

Critical positioning boundary — display this clearly in the footer and in the AI section:

“An unusual reading does not automatically mean a valve is failing. ValveGuard flags anomalies for human investigation; it does not certify equipment safety or independently authorize repairs.”

Primary audience:

- Maintenance technicians

- Reliability engineers

- Plant operations managers

- Industrial IoT and asset-performance teams

## Visual direction

Create a dark, technical, premium industrial interface:

- Background: deep graphite navy, near-black steel, subtle blueprint grid.

- Primary accent: industrial cyan / electric teal.

- Secondary accent: safety amber for warnings.

- Success: measured green.

- Danger: controlled red, used sparingly for critical anomalies.

- Surfaces: glassmorphic cards with thin 1px borders, soft inner glow, and subtle noise texture.

- Typography: use a technical geometric sans-serif such as Space Grotesk for headings and Inter or IBM Plex Sans for body text. Use JetBrains Mono or IBM Plex Mono for sensor values, IDs, timestamps, and code-like details.

- Visual motif: valves, flow lines, pressure gauges, sensor pulses, pipeline schematics, and data traces.

- Avoid generic purple gradients, startup clichés, cartoon illustrations, and overly playful shapes.

- The site should feel credible to plant engineers: precise, calm, high-signal, and operational.

## 3D hero requirement

Build an interactive 3D hero using React Three Fiber and drei, with graceful fallback for low-powered devices.

The 3D centerpiece should be a stylized industrial control valve connected to pipes and sensor nodes:

- Metallic valve body with subtle brushed-metal material.

- Slowly rotating actuator.

- Animated flow particles moving through the pipe.

- Sensor nodes emitting soft cyan pulses.

- A few floating translucent data cards around the valve showing:

  - “V-107 · Response time +68%”

  - “Pressure: normal”

  - “Evidence: position lag”

  - “Priority: inspect soon”

- On mouse move, gently parallax the valve and camera.

- On scroll, subtly rotate or zoom the valve.

- Include a “Reduced motion” fallback: static high-quality render with CSS-animated data cards.

- The 3D scene must not block text readability or hurt mobile performance.

## Navigation

Sticky top navigation with blur backdrop:

- ValveGuard logo

- Product

- How it works

- Platform

- AI

- Pricing

- FAQ

- Docs

- GitHub

- Log in

- Sign up free

The logo should be an original minimal mark: a stylized valve wheel or flow-control symbol forming a shield-like shape, with a cyan data pulse passing through it. Use an inline SVG, not a stock icon.

Mobile navigation must use a clean full-screen or slide-in menu.

## Hero section

Headline:

“Know which valve needs attention first.”

Subheadline:

“ValveGuard turns equipment readings into ranked, evidence-backed investigation reports—so maintenance teams spend less time reviewing data and more time preventing downtime.”

Primary button:

“Launch ValveGuard”

Secondary button:

“See how it works”

Below the buttons, show three compact trust indicators:

- “Evidence-first anomaly triage”

- “Built for human investigation”

- “Powered by Gemma 4 via Gemini API”

Hero right side or background:

Interactive 3D valve scene described above.

Also include a compact live-demo preview card titled “Fleet Overview”:

- 20 simulated valves

- Most marked normal

- Three highlighted:

  - V-107: Response time +68%, priority “Inspect soon”

  - V-113: Pressure-position mismatch, priority “Urgent review”

  - V-121: Flatlined vibration sensor, priority “Verify sensor”

- A small animated “Run triage” button that cycles through the anomaly states.

- A clear label: “Simulated demonstration data.”

## Partner and technology strip

Immediately below the hero, add a horizontally scrolling “Built with modern industrial AI infrastructure” strip.

Use subtle grayscale placeholder logos or abstract partner marks for:

- Industrial IoT

- Edge telemetry

- Asset performance

- Cloud data platforms

- Maintenance systems

Do not imply partnerships with real companies unless clearly labeled as illustrative.

Include one prominent, visually distinct badge:

“Gemma 4 · Gemini API”

The badge should animate subtly as it enters the viewport and link to a section explaining Gemma 4’s role.

## Section 1 — The problem

Section title:

“Manual review does not scale.”

Body:

“Maintenance teams may monitor dozens or hundreds of valves. When readings become unusual, technicians must determine which assets deserve attention, what evidence supports the concern, and what to inspect first. Manual review takes time, while poorly explained alerts can create unnecessary inspections or cause important warning signs to be overlooked.”

Show three animated problem cards:

1. “Too many readings”

   - Animated stream of sensor values.

   - Copy: “Dozens or hundreds of valves produce continuous readings.”

2. “Unexplained alerts”

   - Alert icon with a question mark.

   - Copy: “An alert without context creates uncertainty, not action.”

3. “Unclear priorities”

   - Three valves with competing warning levels.

   - Copy: “Technicians need to know what to inspect first—and why.”

Add a transition line:

“ValveGuard replaces guesswork with ranked, evidence-backed investigation.”

## Section 2 — How ValveGuard works

Use a three-step animated horizontal flow, with connecting pipeline lines and moving data pulses.

Step 1 — Collect readings

“Connect valve telemetry, maintenance metadata, and optional inspection photos.”

Step 2 — Detect unusual behaviour

“Deterministic anomaly checks compare readings against baselines, thresholds, trends, and data-quality rules.”

Step 3 — Generate an investigation report

“Gemma 4, accessed through the Gemini API, translates verified technical findings into a clear, evidence-backed report for human review.”

Visual requirement:

- Show a valve sending data into an anomaly engine.

- The anomaly engine highlights one valve.

- The selected valve sends evidence into an AI report card.

- The report card opens with fields: Evidence, Likely explanations, Recommended first action, Data gaps, Confidence.

Add a prominent disclaimer beneath the flow:

“ValveGuard supports investigation. It does not replace qualified maintenance, process-safety, or engineering procedures.”

## Section 3 — Explore the platform

Create two large interactive dashboard preview cards.

### Card 1: Fleet Overview

Purpose:

“See the health of your valve fleet and prioritize the assets that need investigation.”

Preview should include:

- Fleet health summary

- Valve status filters

- Anomaly count

- Searchable valve table

- Priority badges

- Mini trend sparklines

- “Open Fleet Overview” button

### Card 2: Valve Investigation & AI Report

Purpose:

“Inspect the evidence behind an anomaly and review an AI-generated investigation report.”

Preview should include:

- Valve ID V-107

- Sensor trend chart

- Anomaly timeline

- Evidence summary

- Likely explanations with likelihood levels

- Recommended first action

- Data gaps

- Technician actions: Accept, Needs more data, False positive

- “Open Investigation Report” button

Both preview cards should use realistic but clearly simulated industrial UI. Add a small badge: “Demo data.”

## Section 4 — Meet the AI

Section title:

“Meet Gemma 4: evidence first, action second.”

Explain that Gemma 4, accessed through the Gemini API, helps ValveGuard:

- Translate verified technical findings into understandable explanations.

- Identify missing evidence.

- Distinguish possible equipment degradation from sensor or data-quality issues.

- Draft inspection questions for human review.

- Recommend a cautious first investigation step.

Do not claim Gemma 4 predicts failures, certifies safety, or authorizes repairs.

Include an interactive before-and-after example.

Input panel:

“Valve V-107: response time increased 68% over 24 hours. Position deviation: 11%. Pressure and temperature normal. Vibration normal.”

Output panel:

“Assessment: Inspect soon. Confidence: 72%. Evidence: Rising response time with normal pressure and temperature makes actuator or positioner response degradation more plausible than a process upset. Recommended first action: Review positioner diagnostics and observe a non-intrusive partial-stroke response. Data gaps: Recent maintenance history and positioner fault codes.”

Animate the output as if it is being generated, then reveal it fully.

Add a technical badge:

“Model: gemma-4-31b-it · Gemini API”

## Section 5 — Pricing

Create three pricing tiers with a monthly/annual toggle. Annual pricing should show “Save 20%.”

### Starter — Free

Price: $0

Best for: Small teams evaluating ValveGuard.

Features:

- Up to 25 valves

- Daily anomaly checks

- Fleet Overview dashboard

- 50 Gemma 4 investigation reports per month

- CSV upload

- Community support

CTA:

“Sign up free”

Tag: “No credit card required”

### Professional — $149 per site / month

Price shown as $119 per site / month when annual is selected.

Best for: Maintenance teams operating one plant or site.

Everything in Starter, plus:

- Up to 500 valves

- Real-time anomaly monitoring

- Unlimited investigation reports

- Valve Investigation & AI Report workspace

- Technician accept/reject feedback

- Role-based access

- Email support

CTA:

“Start Professional trial”

Tag: “Most popular”

### Enterprise — Custom

Price: “Let’s talk”

Best for: Multi-site industrial operations.

Everything in Professional, plus:

- Unlimited valves and sites

- Private deployment options

- Custom baselines and integration support

- Audit trails

- SSO and advanced governance

- Dedicated success engineer

CTA:

“Contact sales”

Tag: “For regulated environments”

Pricing design:

- Use industrial gauge-style progress indicators for valve limits.

- The Professional card should be visually elevated with a cyan border and subtle animated flow line.

- Add a comparison note: “All plans include evidence-first triage and human-review controls.”

- Add a disclaimer: “Pricing shown for demonstration purposes.”

## Section 6 — FAQ

Use an accessible accordion with smooth height animation, plus icons.

Questions and answers:

1. Does ValveGuard predict valve failure?

“No. ValveGuard identifies unusual behaviour and produces evidence-backed investigation reports. It does not certify equipment safety or independently authorize repairs.”

2. What does Gemma 4 do?

“Gemma 4, accessed through the Gemini API, helps translate verified technical findings into clear explanations, identify missing evidence, and draft inspection questions for human review.”

3. Can ValveGuard replace our maintenance team?

“No. ValveGuard is decision support. Technicians and qualified engineers remain responsible for inspection, maintenance, and safety decisions.”

4. What data does ValveGuard use?

“The MVP supports valve telemetry, equipment metadata, maintenance history, and optional inspection photos. Customers control what data they connect.”

5. How does ValveGuard avoid unnecessary inspections?

“It ranks anomalies using transparent evidence, distinguishes equipment behaviour from possible sensor or data-quality issues, and identifies missing information before recommending action.”

6. Is my plant data secure?

“ValveGuard is designed around least-privilege access and customer-controlled data connections. Enterprise plans can support private deployment and governance requirements.”

7. Can I try it without connecting live equipment?

“Yes. The demo uses simulated valve readings so you can explore Fleet Overview and the AI investigation workflow immediately.”

## Section 7 — Final call to action

Full-width dark section with a subtle 3D valve silhouette or animated pipeline background.

Headline:

“Ready to investigate smarter?”

Subheadline:

“Turn valve readings into clear, evidence-backed priorities for your maintenance team.”

Primary button:

“Launch ValveGuard”

Secondary links:

- View GitHub

- Read documentation

- Model details

Footer disclaimer:

“ValveGuard is a decision-support prototype. It does not certify equipment safety, predict failures with certainty, or independently authorize repairs.”

## Authentication pages

Create polished, separate routes:

### /login

- Email

- Password

- “Log in”

- “Forgot password?”

- “New to ValveGuard? Sign up free”

- Optional “Continue with Google” button, visually present but non-functional in the prototype.

- Left side: compact ValveGuard value panel with a mini Fleet Overview preview.

- Right side: clean form card.

### /signup

- Full name

- Work email

- Company

- Password

- Checkbox: “I agree to the Terms and Privacy Policy.”

- Button: “Create free account”

- Microcopy: “Free plan includes up to 25 valves and 50 Gemma 4 investigation reports per month.”

- Include password strength indicator.

- After signup, show a simulated onboarding screen: “Connect demo fleet” with a button labeled “Load simulated valves.”

Authentication design:

- Use the same dark industrial theme.

- Add subtle animated pipeline lines in the background.

- Forms must have clear validation states, accessible labels, keyboard focus states, and error messages.

- Do not collect or transmit real credentials in the prototype; simulate authentication client-side or with placeholder API routes.

## Interaction and motion

Use refined, purposeful motion:

- Scroll-triggered fade-and-rise for sections.

- Animated data pulses along pipeline connectors.

- Number count-up for metrics.

- Hover glow on dashboard cards.

- Accordion animations for FAQ.

- Subtle 3D parallax in the hero.

- Respect prefers-reduced-motion.

- Keep animations under 500ms where possible; avoid distracting loops.

## Technical requirements

- Build with Next.js App Router, TypeScript, Tailwind CSS, shadcn/ui, Framer Motion, and React Three Fiber.

- Ensure full mobile responsiveness.

- Use semantic HTML and accessible color contrast.

- Add SEO metadata:

  - Title: “ValveGuard — Evidence-backed valve maintenance intelligence”

  - Description: “Turn unusual valve readings into ranked, evidence-backed investigation reports with Gemma 4 via the Gemini API.”

- Include Open Graph metadata and a favicon based on the ValveGuard logo.

- Use placeholder images or original SVG/CSS dashboard mockups; do not use copyrighted screenshots.

- Add clear “Simulated demo data” labels wherever synthetic data appears.

- Make all buttons and links functional within the prototype: navigation, login, signup, dashboard previews, pricing toggle, FAQ accordion, and external GitHub/docs placeholders.

## Copy tone

Professional, calm, precise, and engineering-led. Avoid hype such as “revolutionary,” “magical,” or “fully autonomous.” Emphasize evidence, prioritization, transparency, human oversight, and operational reliability.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/169dd8ae-d8b8-5cd9-9313-15936daaad88).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
