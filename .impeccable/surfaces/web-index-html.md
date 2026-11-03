---
version: 1
slug: "web-index-html"
primary_target: "web/index.html"
related_targets: ["web/app.js","web/style.css"]
---

Scope: the CRM (web/index.html, web/style.css, web/app.js).
- **Home:** a scroll-told report.
- **Accounts, Pipeline and the drawer:** working tools.

Audience: the Growth Lead and first-time viewers (MESA evaluators).

User-pinned brief, 3 Nov 2026:
- "very minimal luxury"
- "the dashboard should make sense"
- "scroll and animation should be crazy"
- not AI slop
- skills: Lenis, GSAP, Vanta, React Bits, Impeccable, design-taste, Playwright

Constraints:
- CSP is self-only, so everything is vendored.
- Scraped text renders as text only.
- No invented figures.

## Direction contract

THESIS: One number per screen, at monument scale. Each pinned chapter turns one claim into motion you scrub with the scroll: time collapsing from 17:30 to 0:15, verdicts crossing the 60 line, the funnel narrowing, emails stacking. Refuses: the tile-and-chip dashboard.

OWN-WORLD:
- **Ground:** obsidian #0b0b0d.
- **Ink:** warm white #ecebe6. Secondary text #a3a19a, faint text #6d6b66.
- **Hairlines:** at 10% ink.
- **Accent:** one, Klein ultramarine #3d4bff (#8c95ff for small text), for "what the system did".
- **States:** ember #e58a62 for "needs you"; "out" is dimmed ink.
- **Type:** Clash Grotesk at 200–300 for numerals and headings, Switzer for UI text.
- **Surfaces:** no cards on Home; hairline rules only.
- **Vanta FOG:** ultramarine smoke in the hero only.

STORY:
1. The hero says 11 researched, 3 worth writing to.
2. Time: 17:30 by hand collapses to 0:15.
3. The agent loop moves 3 verdicts over the bar.
4. The funnel shows where companies dropped out.
5. The emails stack, each with its score.
6. Needs you: the actions, then a link to the accounts.

FIRST VIEWPORT:
- **Hero:** full height. The Vanta fog sits right of centre; a 112px light headline sits bottom-left with three inline facts under it.
- **Header:** a thin top bar with wordmark, nav and a minimal run field.
- **Index:** a right-edge chapter index.
- **Progress:** a hairline scroll-progress line at the top.

FORM: user-pinned (minimal luxury scroll report) over canon. seed:a61929adcd17044c.

Signature interaction:
- **ScrollTrigger pins** each chapter and scrubs its number or chart with the scroll; Lenis provides the smoothing.
- **SplitText** reveals the hero line by line.
- **Hover/focus** on an account highlights it everywhere it appears.
- **Reduced motion and mobile:** no pins and no fog; static final states.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
