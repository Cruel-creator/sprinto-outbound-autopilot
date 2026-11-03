# Roadmap: Sprinto Outbound Autopilot

## Overview

The pipeline is built as horizontal layers in the order data flows: domain -> scraped pages -> CompanyProfile -> qualification (rubric, then bounded agent loop) -> contact -> pain points and draft -> send and report -> unattended batch run. Phase 1 burns down external risk first. A preflight proves that Gemini (structured and grounded), Hunter and Resend all work, and it puts a test email in the user's inbox before any pipeline code exists. Phase 2 lays the shared backbone that every later layer writes into: the trace and evidence ledger, the single Gemini client, the disk cache, and retry with pacing. Each layer after that is built fully and checked on real domains from the curated list. Phase 10 wires them into `python run.py domains.txt`, which runs unattended and writes a batch summary.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Setup & Preflight** - Install from one command sequence with secrets git-ignored, and a preflight that proves Gemini, Hunter and Resend work (test email lands in the inbox)
- [ ] **Phase 2: Foundations** - Shared models, the single Gemini client (cache, retry, pacing, grounded search) and the per-company trace with an evidence ledger flushed after every step
- [ ] **Phase 3: Scrape** - Homepage plus key pages with typed fetch outcomes and soft-404 detection, run against the curated test list
- [ ] **Phase 4: Extract** - Gemini turns page text into an evidence-backed CompanyProfile with verified or unverified quotes
- [ ] **Phase 5: Qualify** - Deterministic 0-100 ICP score from `config/icp.yaml`, with hard disqualifiers, trust-center caps and a stated reason
- [ ] **Phase 6: Agent Loop** - A bounded JSON controller loop that gathers more evidence (site pages, grounded research, job postings) when the data can't decide the verdict
- [ ] **Phase 7: Point of Contact** - Hunter lookup for qualified companies only, cached, with deterministic role rules, a CSV override and an honest `no_contact`
- [ ] **Phase 8: Pain Points & Draft** - Two evidence-cited pain points per contact, then a validated email of 110 words or fewer with one verified hook and one soft CTA
- [ ] **Phase 9: Send & Report** - Resend delivery locked to `TO_EMAIL`, an intended-recipient footer, and a `report.md` that defends every decision, with a Gmail compose fallback
- [ ] **Phase 10: Batch Run** - `python run.py domains.txt` runs unattended over the list, with per-domain isolation, one status per company, and `out/summary.md`

## Phase Details

### Phase 1: Setup & Preflight
**Goal**: The project installs cleanly on the user's Windows machine with secrets protected, and every external service is proven to work before any pipeline code is written. The user sees a real email from the system in their own inbox.
**Depends on**: Nothing (first phase)
**Requirements**: SETUP-01, SETUP-02, SETUP-03
**Success Criteria** (what must be TRUE):
  1. Following the documented sequence (`py -3.12 -m venv .venv`, install `requirements.txt`, copy `.env.example` to `.env`) gives a working environment. `.env.example` lists `GEMINI_API_KEY`, `RESEND_API_KEY`, `HUNTER_API_KEY`, `TO_EMAIL` and the Gemini model IDs.
  2. `git check-ignore` confirms that `.env`, `cache/`, `out/` and `contacts.csv` are ignored, and `.gitignore` was committed before any `.env` file existed.
  3. Running the preflight delivers a test email through Resend to `TO_EMAIL`, and it shows up in the user's Gmail inbox.
  4. The preflight reports a passing structured call and a passing grounded call for each configured Gemini model, plus the number of Hunter searches left.
  5. With a wrong key or an unknown model ID, the preflight stops early with a one-line message naming the failed service, not a stack trace.
**Plans**: TBD

### Phase 2: Foundations
**Goal**: Every later layer has one shared, typed backbone. It has a single Gemini client with a disk cache, retry and pacing, and a per-company trace whose evidence ledger is on disk after every step.
**Depends on**: Phase 1
**Requirements**: TRCE-01, RUN-04, RUN-05
**Success Criteria** (what must be TRUE):
  1. Recording a step for a test domain writes `out/<domain>/trace.json` straight away. It holds the step's input, its output, and the model version of every LLM call the step made.
  2. Evidence added to the ledger gets sequential IDs (E1, E2, ...), each with a quote, a source URL and a verified flag, and can be read back from `trace.json`.
  3. Making the same Gemini call twice reaches the network once and serves the second from `cache/`. The force option (wired to `--force`) bypasses the cache.
  4. A simulated 429 or 5xx from Gemini is retried with backoff, visible in the log, instead of crashing the run. Calls are paced to stay inside the configured free-tier rate.
**Plans**: TBD

### Phase 3: Scrape
**Goal**: For any domain, the system fetches the homepage and key pages and records an honest, typed outcome for each, so an unreachable page is never mistaken for a missing one.
**Depends on**: Phase 2
**Requirements**: SCRP-01, SCRP-02, SCRP-03, DATA-01
**Success Criteria** (what must be TRUE):
  1. `domains.txt` holds about 10 real domains: the expected qualifiers getmaxim.ai, bolna.ai, nurix.ai and greptile.com, plus the deliberate non-fits salesforce.com, rocketlane.com, hyperbound.ai, atomicwork.com, wakefit.co and gushwork.ai. Each domain's expected verdict is written down next to it.
  2. Scraping a domain fetches the homepage plus `/pricing`, `/security`, `/trust`, `/customers`, `/about` and `/careers`. The saved text keeps footer text, image alt text and link hrefs, so a footer trust badge is visible.
  3. Every fetch shows exactly one typed outcome (`OK`, `NOT_FOUND`, `BLOCKED`, `TIMEOUT`, `EMPTY_SHELL`, `NON_HTML`, `TOO_BIG`). A blocked or empty page is reported as unknown, never as absent.
  4. A path that returns 200 with the homepage's content (a soft 404) is reported as `NOT_FOUND`.
  5. Scraping the same domain again reads its pages from the disk cache, with no network fetch.
**Plans**: TBD

### Phase 4: Extract
**Goal**: Raw page text becomes a structured CompanyProfile in which every fact traces back to a verbatim quote, and anything unsupported is honestly `unknown`.
**Depends on**: Phase 3
**Requirements**: EXTR-01, EXTR-02, EXTR-03
**Success Criteria** (what must be TRUE):
  1. Extracting a scraped domain produces a CompanyProfile in `trace.json` with these fields: product, B2B/SaaS, stage or funding, headcount, customers, pricing tiers, compliance claims, regions and hiring.
  2. Every fact that isn't `unknown` has a verbatim quote and source URL registered in the evidence ledger. A fact with no evidence appears as `unknown`.
  3. Each quote is marked verified when it appears in the fetched page text and unverified when it doesn't, so a fabricated quote is visibly flagged.
**Plans**: TBD

### Phase 5: Qualify
**Goal**: Each company gets a defensible, deterministic 0-100 ICP score and verdict. Python computes it from a researched rubric in YAML, and every point is tied to evidence that resolves in the ledger.
**Depends on**: Phase 4
**Requirements**: QUAL-01, QUAL-02, QUAL-03, QUAL-04, QUAL-05
**Success Criteria** (what must be TRUE):
  1. `config/icp.yaml` holds weighted signals summing to 100, hard disqualifiers, caps, and the thresholds (60 qualify, 75 priority, 45-59 nurture). Changing a weight or threshold in the YAML changes the score or verdict on the next run, with no code edits.
  2. The score is computed in Python from signal states (present, absent, unknown). A signal marked present that cites an evidence ID missing from the ledger earns zero points.
  3. A hard-disqualified company (for example salesforce.com at 2,000+ headcount, or a non-software business) ends `not_qualified` with the disqualifier named as the reason.
  4. A fully certified company with a Sprinto, Vanta, Drata or SafeBase trust center is capped and tagged `switch_or_expand_candidate`. A phrase like "hosted on SOC 2 compliant AWS" is not counted as the company's own certification.
  5. Each qualification shows a verdict, a score, every signal with its points and evidence IDs, and a one-paragraph reason.
**Plans**: TBD

### Phase 6: Agent Loop
**Goal**: When the scraped evidence can't settle a verdict, a bounded agent loop gathers more evidence on its own and stops under rules that Python enforces.
**Depends on**: Phase 5 (score bounds for early exit; reuses Phase 3's fetcher for `fetch_page`)
**Requirements**: AGNT-01, AGNT-02, AGNT-03, AGNT-04, AGNT-05, AGNT-06
**Success Criteria** (what must be TRUE):
  1. For a domain with too many unknown signals, the loop runs. Each iteration is a schema-validated `{findings, next_action}`, and Python executes the chosen tool.
  2. The three tools behave as follows:
     - `fetch_page` fetches only allow-listed same-site paths.
     - `web_research` adds its grounded results to the ledger as unverified evidence with source URLs.
     - `job_postings` surfaces compliance, GRC and security hiring signals.
  3. No domain exceeds 4 tool calls, 2 grounded searches or about 120 s, and no action is repeated. The loop exits early once the score bounds already decide the verdict.
  4. A domain that ends near the threshold with signals still unknown gets `insufficient_data`, not a guessed verdict.
  5. For every iteration, `trace.json` shows the rationale, the targeted signals, a summary of the tool result, and the score before and after.
**Plans**: TBD

### Phase 7: Point of Contact
**Goal**: For each qualified company, the system picks one real decision-maker automatically and states exactly why that person. It doesn't waste Hunter's 25 monthly searches and never invents anyone.
**Depends on**: Phase 5 (qualified verdict and headcount; built after Phase 6 in sequence)
**Requirements**: POC-01, POC-02, POC-03
**Success Criteria** (what must be TRUE):
  1. Hunter Domain Search (seniority senior and executive) is called only for qualified companies. Non-qualified domains make zero Hunter calls.
  2. A second lookup for the same domain spends no Hunter credit because it reads `cache/hunter/<domain>.json`, unless forced. A Hunter 429 or 5xx is retried with backoff through the shared wrapper.
  3. The chosen contact comes with:
     - the rule that fired: under 50 people, founder or CEO; 51-200, CTO or VP Engineering; 201+, Head of Security or GRC lead
     - the candidates considered
     - a stated reason
  4. A `contacts.csv` row overrides or fills in for a domain. With no suitable Hunter result and no CSV row, the company ends `no_contact` and nobody is invented.
**Plans**: TBD

### Phase 8: Pain Points & Draft
**Goal**: For each chosen contact, the system writes a short, evidence-grounded email a human would reply to. It has two role-specific pain points, one verified hook and one soft CTA, and nothing is made up.
**Depends on**: Phase 7
**Requirements**: PAIN-01, PAIN-02, DRFT-01, DRFT-02, DRFT-03, DRFT-04
**Success Criteria** (what must be TRUE):
  1. Each company with a contact shows two pain points fitted to the contact's role. Each cites at least one evidence ID that resolves in the ledger. A SOC 2-only company gets an ISO 27001 or GDPR expansion angle, not a first-certification pitch.
  2. The draft greets the contact by first name, exactly as returned, and ends with "Sprinto Growth Lead". Python inserts both, not the LLM.
  3. The draft opens with one hook chosen by `hook_id` from the verified candidates (priority: compliance signal, enterprise gap, funding, geography) and ends with one soft call to action.
  4. The validator rejects:
     - a body over 110 words
     - more than one CTA
     - placeholders
     - banned or spammy phrases
     - claims without evidence (Sprinto claims may come only from `sprinto_facts.md`)

     A failing draft is regenerated once, and the result is recorded.
  5. Every company's subject line is unique and includes the company name.
**Plans**: TBD

### Phase 9: Send & Report
**Goal**: A qualified company's personalised email lands in the user's inbox and can never reach a prospect. A readable report defends every decision behind it.
**Depends on**: Phase 8
**Requirements**: SEND-01, SEND-02, SEND-03, TRCE-02
**Success Criteria** (what must be TRUE):
  1. A drafted email arrives in `TO_EMAIL`'s Gmail inbox through Resend. It ends with an "Intended recipient" footer giving the contact's name, title and Hunter email.
  2. `send()` has no recipient parameter. A passing test proves that even a hostile contact record, with a prospect address in every field, can never reach Resend's `to` field.
  3. `out/<domain>/report.md` is rendered from `trace.json` with no LLM calls. It answers "why this company", "why this person" and "why this email", each with cited evidence IDs.
  4. `report.md` contains an "Open in Gmail (manual fallback, to yourself)" link that opens a Gmail compose window pre-filled with `TO_EMAIL`, the subject and the body.
**Plans**: TBD

### Phase 10: Batch Run
**Goal**: One command runs the whole 7-step pipeline over the curated list with no human decisions. One bad domain never stops the batch, every company ends with exactly one status, and a summary shows rejections as real results.
**Depends on**: Phase 9
**Requirements**: RUN-01, RUN-02, RUN-03, TRCE-03
**Success Criteria** (what must be TRUE):
  1. `python run.py domains.txt` runs all 7 steps for every domain with no prompts, and personalised emails arrive in the inbox for the companies that qualify.
  2. A domain that fails mid-pipeline is recorded with its failed step and status `failed`, and the remaining domains still complete.
  3. Every company ends with exactly one status: `sent`, `not_qualified`, `insufficient_data`, `no_contact` or `failed`.
  4. `out/summary.md` lists every domain with its status, score, top reasons, chosen contact and send result. Rejections are shown as first-class rows, and the outcomes can be checked against the expected verdicts in `domains.txt`.
  5. Re-running the same list with no `--force` spends no new Hunter credits and serves cached pages and LLM responses.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Setup & Preflight | 0/TBD | Not started | - |
| 2. Foundations | 0/TBD | Not started | - |
| 3. Scrape | 0/TBD | Not started | - |
| 4. Extract | 0/TBD | Not started | - |
| 5. Qualify | 0/TBD | Not started | - |
| 6. Agent Loop | 0/TBD | Not started | - |
| 7. Point of Contact | 0/TBD | Not started | - |
| 8. Pain Points & Draft | 0/TBD | Not started | - |
| 9. Send & Report | 0/TBD | Not started | - |
| 10. Batch Run | 0/TBD | Not started | - |
