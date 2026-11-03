# Sprinto Outbound Autopilot

## What This Is

A Python CLI pipeline that takes a list of company domains and, with no human decisions in the loop, works out which ones fit Sprinto's ICP. For each fit it picks the right decision-maker, works out their two most likely compliance pain points, writes a personalised cold email to them by name with a specific hook, and sends it via the Gmail API. It replaces the Sprinto Growth Lead's manual 15–20 minutes of research and writing per company, where quality slips by the end of a list of 8–15 companies.

Built for MESA PGP Cohort 4, Term 2, AI Case 2 ("Cold Outreach, at Scale"), session on 3 Nov 2026 (1.5 hours).

## Core Value

Run it on a list of domains and a personalised email that a human would actually reply to lands in the inbox. Every decision behind it (why this company, why this person, why this email) can be defended with cited evidence.

## Business Context

- **Customer**: Sprinto's Growth Lead (runs outbound for Sprinto, which automates SOC 2, ISO 27001 and GDPR certification for SaaS companies)
- **Revenue model**: Outbound pipeline for Sprinto's compliance-automation SaaS
- **Success metric**: Qualified prospects reached per hour, with consistent email quality (no fatigue drop-off)
- **Strategy notes**: Case brief at `C:\Users\ROG\Downloads\MESA_Case 02 - 3 Nov.pdf`

## Requirements

### Validated

(None yet. Ship to validate.)

### Active

- [ ] Accept a list of domains (file) and run the full 7-step pipeline end to end, unattended
- [ ] Step 1, Scrape: fetch the homepage plus key pages for raw signal
- [ ] Step 2, Extract: Gemini turns raw content into structured company data (JSON schema)
- [ ] Step 3, Qualify: a scored rubric (0–100, weighted signals, threshold) against a researched Sprinto ICP definition, with an **agent loop** that fetches more information when the data is insufficient. Tools: more site pages (/security, /trust, /pricing, /careers, /customers, /about), Gemini with Google Search grounding (funding stage, news, compliance mentions), and job postings (compliance, GRC and security roles)
- [ ] Step 4, PoC: choose the right decision-maker from a hand-filled `contacts.csv` (sourced manually from Apollo), with role-based selection logic and a stated reason
- [ ] Step 5, Pain points: the two most likely pain points for that specific person and role, grounded in company evidence
- [ ] Step 6, Draft: a personalised email addressed by name, under 120 words, with one specific hook from their own signals, one soft CTA, signed as Sprinto's Growth Lead
- [ ] Step 7, Send: send via the Gmail API (OAuth) with `to:` hardcoded to the user's own address
- [ ] Decision trail: for each company, a JSON trace of every step's input and output plus a readable `report.md` that cites the evidence behind each decision
- [ ] Researched ICP definition ("right companies") written down and used by the qualifier
- [ ] Curated test list of about 8–10 real domains: some should qualify and some shouldn't, to show the filter works

### Out of Scope

- Sending to real prospects. The case requires `to:` to be the user's own address.
- Apollo API automation. The free tier is web UI only, so contacts are hand-filled into `contacts.csv` instead.
- Hunter.io. Apollo was chosen.
- Web UI or dashboard. A CLI is fastest to build in 1.5 hours and is enough for "repeatable".
- Follow-up sequences, reply tracking, CRM sync. Beyond a first-touch email.
- A dry-run mode. The user chose "always send", and sends are safe because they only go to the user's own inbox.

## Context

- **The ICP from the brief:** SaaS companies, typically Series A–C, either preparing for a compliance audit or under pressure from enterprise customers to get certified. "Right companies" must be refined through research. Likely signals: a trust or security page without a certification badge, an enterprise plan or "Contact sales", big-logo customers, compliance or security hiring, recent funding, a mention of an upcoming SOC 2 audit, a move into the EU or US market (GDPR).
- **Likely PoC roles:** CTO, VP Engineering, Head of Security or InfoSec, Compliance or GRC lead, and at smaller companies the CEO or co-founder.
- **Gemini** handles extraction, qualification reasoning, pain-point inference and drafting. Google Search grounding is available on the same API key.
- **Gmail API** needs a Google Cloud OAuth client (`credentials.json`) and a one-time browser consent that writes `token.json`.
- **"Done" according to the brief:** a personalised email lands in the inbox, addressed to a real person by name, with a hook a human would respond to. The builder can defend why this company qualified, why this person, and why the email was written this way.

## Constraints

- **Timeline**: Live session on 3 Nov 2026, 1.5 hours. The walking skeleton must deliver an email to the inbox early.
- **Tech stack**: Python 3, `google-genai` (Gemini), Gmail API (`google-api-python-client`, `google-auth-oauthlib`), `httpx`/`requests` plus BeautifulSoup for scraping. Chosen for the quickest path to the Google APIs.
- **LLM**: Google Gemini API only, the user's key in `.env`.
- **PoC source**: Apollo by hand, then `contacts.csv`. No contact API.
- **Email recipient**: Always the user's own address, from `.env`. Never a prospect.
- **Secrets**: API keys, `credentials.json` and `token.json` are never committed (`.gitignore`).
- **Autonomy**: No interactive prompts during a run. The pipeline must decide every step itself.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python CLI (`python run.py domains.txt`) | Fastest to build, repeatable, easy to demo | — Pending |
| Apollo by hand, then `contacts.csv` | Apollo's free tier has no API; keeps the run fully automatic once filled | — Pending |
| Gemini for every LLM step | User has a Gemini API key; Search grounding gives the agent loop web reach | — Pending |
| Gmail API (OAuth) for sending | Required by the brief; the user chose it over SMTP | — Pending |
| Scored rubric (0–100) plus threshold to qualify | Weighted signals with cited evidence make the decision defensible | — Pending |
| Three agent-loop tools: site pages, Google Search grounding, job postings | Covers compliance, enterprise and hiring signals that the homepage alone misses | — Pending |
| JSON trace plus `report.md` per company | "Defend every decision" needs a lasting, readable evidence trail | — Pending |
| Signed as Sprinto Growth Lead, under 120 words, one hook, soft CTA | Realistic outbound framing; short emails get replies | — Pending |
| Always send, no dry-run | User's choice; the recipient is always their own inbox, so it's safe | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check: still the right priority?
3. Audit Out of Scope: reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-11-03 after initialization*
