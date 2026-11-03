---
version: 1
slug: "web-index-html"
primary_target: "web/index.html"
related_targets: ["web/app.js","web/style.css"]
---

Scope: the CRM dashboard (web/index.html, web/style.css, web/app.js), Operate mode. Audience: the Growth Lead every morning, and first-time viewers (MESA evaluators). Task: see in seconds that the pipeline works, then act on what needs a human. Constraints:
- CSP is self-only, so fonts and vendor scripts are self-hosted.
- Scraped text renders as text only.
- No invented reply rates.

## Direction contract

THESIS:
- **Proof as drawn comparisons, with almost no prose:** machine vs manual time; the agent loop shown as a before→after dumbbell against the 60 bar; the funnel with tagged drop reasons; each email plotted on a quality gauge.
- **Refuses:** the light, text-heavy, generic SaaS look the user rejected.

OWN-WORLD:
- **Ground:** dark, #0b0e17, with a faint fixed 22px dot grid.
- **Tiles:** #121725, 14px radius, 1px hairlines.
- **Data palette, each colour with one job:**
  - blue #7aa7ff: agent loop and actions
  - lime #b9f26b: sent and good
  - amber #ffc561: needs you
  - coral #ff7a66: out
  - slate #8a94ab: unknown
- **Type:** Satoshi, self-hosted. 900 weight for numbers and headings, 72px hero figures.
- **Effects:** no glow, no neon edges. One soft cursor spotlight per tile.

STORY: The visitor sees "3 of 11 companies qualified". Status chips show emailed, held and verdicts fixed. The tiles prove speed, the agent loop's corrections, the funnel and email quality. The "Needs you" tile holds the human's next action.

FIRST VIEWPORT:
- **Shell:** a sidebar (Home, Accounts, Pipeline) and a pill run input.
- **Hero:** a 44px sentence with status chips.
- **Bento grid:** time (4 columns) and agent-loop dumbbell (8); funnel (5), emails (3) and quality (4); "Needs you" across all 12.

FORM: canon steered bolder by the user (dark bento, full palette). seed:a61929adcd17044c.

Signature interaction: one GSAP intro, in which tiles rise, numbers count up, bars draw, and each dumbbell dot slides from its website-only score to its researched score. Hovering or focusing an account highlights it across every tile. Lenis smooths the main scroll only when motion is allowed.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
