# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- Sprinto's Growth Lead, who runs outbound and reviews the accounts the pipeline produced every morning.
- First-time viewers in the same moment: MESA case evaluators seeing the system live. The dashboard must make sense to both without anyone explaining it.

## Product Purpose

Sprinto Outbound Autopilot takes a list of company domains and, with no human decisions, decides which fit Sprinto's ICP. For each fit it picks the decision-maker, finds two pain points and writes and sends a personalised email, which lands in the user's own inbox.
- **It replaces:** 15–20 minutes of manual research and writing per company.
- **Success:** every decision (why this company, why this person, why this email) can be defended with cited evidence.

The CRM is the local window onto those decisions.

## Positioning

The proof leads, not the pitch:
- An agent loop resolves thin-signal companies that a fixed pipeline would guess wrong; each report shows both verdicts.
- Points only count with cited, verified evidence.
- A reviewer scores every email.
- An email that fails the checks is held, never sent.

## Operating Context

Local tool: `python app.py` serves http://127.0.0.1:8765 from `out/*/trace.json` and `out/review.csv`.
- **Review workflow:** the Growth Lead reviews each account, then sets stage, agreement, edit level, replied and notes. Those columns feed the 90-day measurement plan and kill criterion in DECISIONS.md.
- **New runs:** typing domains starts a background run.

## Capabilities and Constraints

- **Statuses:** sent, held, not_qualified, insufficient_data, no_contact, failed.
- **Lanes:**
  - pipeline-derived: Qualified, Needs review, Contacted, Needs data, Not a fit
  - set by the Growth Lead: Replied, Meeting, Won, Lost
- **Per account:**
  - fixed-pipeline vs agent-loop verdict and score
  - ICP signals with evidence (verified on the page, or from web search)
  - the contact, with the rule and reason
  - pain points
  - the email, with reviewer scores (overall, specificity, relevance, reply) and critique
  - the activity trace
- **Stack:** Python stdlib server plus static HTML/CSS/JS, no build step. The server sends CSP `default-src 'self'`.
- Scraped text is untrusted: render it as text only, never as HTML.
- Emails only ever go to the user's own address.

## Brand Commitments

- **Visual direction for the CRM:** the user first chose the category standard on 3 Nov 2026, at Stripe-dashboard craft. After seeing it, they rejected the light, text-heavy version as generic and AI-looking. They asked for:
  - a cooler palette
  - far less text
  - a bolder look

  The CRM is now a dark bento dashboard with a four-colour data palette and minimal copy. It keeps Stripe-level chart clarity.
- **Motion:** the user asked for GSAP and Lenis motion, plus React Bits-style effects.

## Evidence on Hand

Real run data in `out/`: 10 domains, 3 qualified, 3 verdicts changed by the agent loop, real reviewer scores. Baseline from the case brief: 15–20 minutes per company by hand, lists of 8–15 companies.
- **Not yet collected:** reply rate and the Growth Lead's agreement rate.
- **Don't fabricate** customers, reply rates or results.

## Product Principles

1. **Proof first:** the first screen shows that the system works and why its calls can be trusted.
2. **Self-explanatory:** every number says what it means and what it compares against; no legend needed.
3. **Every claim traces to evidence:** a verdict, score or email opens onto its sources.
4. **The human acts where the system can't:** held emails, missing contacts and replies are clearly the human's queue.
