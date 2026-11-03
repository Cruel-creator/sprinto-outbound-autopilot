# Requirements: Sprinto Outbound Autopilot

**Defined:** 2026-11-03
**Core Value:** Run it on a list of domains and a personalised email that a human would actually reply to lands in the inbox. Every decision behind it (why this company, why this person, why this email) can be defended with cited evidence.

## v1 Requirements

### Setup & Safety

- [ ] **SETUP-01**: User can create the environment with one documented command sequence (Python 3.12 venv plus `requirements.txt`) and configure it through `.env` (`GEMINI_API_KEY`, `RESEND_API_KEY`, `HUNTER_API_KEY`, `TO_EMAIL`, Gemini model IDs), starting from `.env.example`
- [ ] **SETUP-02**: Secrets (`.env`), `cache/`, `out/` and the real `contacts.csv` are git-ignored before any secret file exists, and `git check-ignore` confirms it
- [ ] **SETUP-03**: User can run a preflight that checks each configured Gemini model (one structured call, one grounded call), reports the Hunter credits left, and confirms Resend can send to `TO_EMAIL`. It fails fast with a clear message.

### Run & Orchestration

- [ ] **RUN-01**: User can run `python run.py domains.txt` and the whole 7-step pipeline runs for every domain with no prompts or decisions from the user
- [ ] **RUN-02**: A failure on one domain is recorded with its failed step and status, and never stops the rest of the batch
- [ ] **RUN-03**: Each company ends with exactly one status: `sent`, `not_qualified`, `insufficient_data`, `no_contact` or `failed`
- [ ] **RUN-04**: Scraped pages, LLM responses and Hunter responses are cached on disk, so re-runs don't spend quota. `--force` bypasses the cache.
- [ ] **RUN-05**: Gemini and Hunter calls retry with backoff on 429/5xx and are paced to stay inside free-tier limits

### Scrape (Step 1)

- [ ] **SCRP-01**: The system fetches the homepage and key same-site paths (`/pricing`, `/security`, `/trust`, `/customers`, `/about`, `/careers`), keeping footer text, image alt text and link hrefs
- [ ] **SCRP-02**: Every fetch records a typed outcome (`OK`, `NOT_FOUND`, `BLOCKED`, `TIMEOUT`, `EMPTY_SHELL`, `NON_HTML`, `TOO_BIG`). Only a real 404 counts as a page being absent, and blocked or empty pages count as unknown.
- [ ] **SCRP-03**: Soft-404 pages (same content as the homepage) are detected and treated as not found

### Extract (Step 2)

- [ ] **EXTR-01**: Gemini turns raw page text into a structured `CompanyProfile` (Pydantic schema): product, B2B/SaaS, stage or funding, headcount, customers, pricing tiers, compliance claims, regions, hiring
- [ ] **EXTR-02**: Every extracted fact carries a verbatim evidence quote and source URL, and a fact with no evidence is `unknown`
- [ ] **EXTR-03**: The system marks each quote verified or unverified by checking it appears in the fetched page text

### Qualify (Step 3)

- [ ] **QUAL-01**: The ICP definition (the researched rubric of weighted signals summing to 100, hard disqualifiers, caps, and thresholds 60 qualify / 75 priority / 45–59 nurture) lives in `config/icp.yaml`, and changing the YAML changes behaviour with no code edits
- [ ] **QUAL-02**: Python, not the LLM, computes the 0–100 score from signal states (present, absent or unknown). A "present" signal counts only if it cites an evidence ID that exists in the ledger.
- [ ] **QUAL-03**: Hard disqualifiers (not software, existing Sprinto customer, 2,000+ headcount, tiny pre-seed) end qualification with a stated reason
- [ ] **QUAL-04**: Trust-center fingerprints (Sprinto `*.trust.site`, Vanta, Drata, SafeBase) and certification claims are detected. Fully certified companies are capped and tagged `switch_or_expand_candidate`. Claims about a vendor's certification (such as "hosted on SOC 2 compliant AWS") are not counted as the company's own.
- [ ] **QUAL-05**: Each qualification produces a verdict, a score, the signals with their points and evidence, and a one-paragraph reason

### Agent Loop (Step 3)

- [ ] **AGNT-01**: When the data isn't enough to decide, an agent loop picks the next tool to call. Each iteration is a schema-validated `{findings, next_action}`, and Python executes the action.
- [ ] **AGNT-02**: Tool `fetch_page`: fetches more pages on the same site, from an allow-list of paths
- [ ] **AGNT-03**: Tool `web_research`: a separate Gemini call with Google Search grounding (funding, news, compliance mentions). Its results are stored as unverified evidence with source URLs.
- [ ] **AGNT-04**: Tool `job_postings`: finds compliance, GRC and security hiring signals (careers page or ATS JSON, falling back to search)
- [ ] **AGNT-05**: Python enforces the stopping rules: at most 4 tool calls, at most 2 grounded searches, no repeated actions, a soft 120 s wall clock per domain, and an early exit when the score bounds already decide the verdict. Ending near the threshold with signals still unknown gives `insufficient_data`.
- [ ] **AGNT-06**: Every iteration is logged with its rationale, the signals it targeted, the tool result summary, and the score before and after

### Point of Contact (Step 4)

- [ ] **POC-01**: For qualified companies only, the system calls the Hunter.io Domain Search API (senior and executive seniority) and caches the response per domain
- [ ] **POC-02**: Deterministic role rules by company size pick one person and record the rule that fired, the candidates considered, and a stated reason. Under 50 people: founder or CEO. 51–200: CTO or VP Engineering. 201+: Head of Security or GRC lead.
- [ ] **POC-03**: An optional `contacts.csv` can override or fill in when Hunter returns no suitable person. With neither, the company is `no_contact` and nobody is invented.

### Pain Points (Step 5)

- [ ] **PAIN-01**: The system identifies the two most likely pain points for the chosen person's role, and each pain point cites at least one evidence ID about the company
- [ ] **PAIN-02**: SOC 2-only companies get an expansion angle (ISO 27001 or GDPR) instead of a first-certification pitch

### Draft (Step 6)

- [ ] **DRFT-01**: The system drafts an email addressed to the contact by first name. The greeting and the sign-off ("Sprinto Growth Lead") are inserted by Python, not written by the LLM.
- [ ] **DRFT-02**: The email opens with one specific hook picked by `hook_id` from verified candidates, in this priority: compliance signal, enterprise gap, funding, geography. It ends with one soft call to action.
- [ ] **DRFT-03**: A Python validator enforces a hard limit of 110 words in the body (the brief's limit is 120), one call to action, no placeholders, no banned or spammy phrases, and no factual claims without evidence. Claims about Sprinto come only from `sprinto_facts.md`. The draft is regenerated once if it fails.
- [ ] **DRFT-04**: Each company gets a unique subject line that includes the company name

### Send (Step 7)

- [ ] **SEND-01**: The email is sent through the Resend API, and the recipient is always `TO_EMAIL`. `send()` has no recipient parameter, and a test proves a prospect's address can never reach the `to` field.
- [ ] **SEND-02**: The email body ends with an "Intended recipient" footer (name, title, email from Hunter), so the inbox copy shows who it was written for
- [ ] **SEND-03**: Each report includes an "Open in Gmail (manual fallback, to yourself)" compose link pre-filled with `TO_EMAIL`, the subject and the body

### Decision Trail

- [ ] **TRCE-01**: Each company gets an `out/<domain>/trace.json` with every step's input and output, an evidence ledger (E1, E2… with quote, URL and verified flag), and the model version per LLM call. It is flushed after every step.
- [ ] **TRCE-02**: Each company gets a `report.md`, rendered from the trace with no LLM calls, that answers "why this company", "why this person" and "why this email" with cited evidence
- [ ] **TRCE-03**: Each run writes a batch `out/summary.md` listing every domain with its status, score, top reasons, chosen contact and send result, with rejections shown as first-class results

### Test Data

- [ ] **DATA-01**: A curated `domains.txt` of about 10 real domains: expected qualifiers (getmaxim.ai, bolna.ai, nurix.ai, greptile.com) and deliberate non-fits (salesforce.com, rocketlane.com, hyperbound.ai, atomicwork.com, wakefit.co, gushwork.ai), each with its expected verdict written down

## v2 Requirements

### Demo resilience

- **DEMO-01**: `--replay` mode re-runs from the cache with zero network calls
- **DEMO-02**: `--only <domain>` runs a single domain from the list

### Enrichment & quality

- **ENRH-01**: Jina Reader fallback for JavaScript-only sites (behind `JINA_ENABLED`)
- **ENRH-02**: Email verification for the chosen contact (Hunter's verifier)
- **ENRH-03**: An LLM critic pass that scores draft quality before sending
- **ENRH-04**: Process domains in parallel

## Out of Scope

| Feature | Reason |
|---------|--------|
| Sending to real prospects | The case requires `to:` to be the builder's own address |
| Gmail API (OAuth) sending | Replaced by Resend: no OAuth or Cloud Console setup, and a school admin can't block it |
| Apollo | Replaced by the Hunter.io API, which keeps Step 4 automatic |
| Dry-run toggle or approval prompts | The user chose "always send", and prompts would break unattended runs |
| Web UI or dashboard | A CLI is fastest in 1.5 hours and enough to be repeatable |
| Follow-ups, reply tracking, CRM sync, open/click tracking | Beyond a first-touch email |
| LinkedIn scraping | Against the platform's terms of service and fragile |
| LLM-assigned scores with no rubric | Can't be defended |
| Headless browser (Playwright) | Too heavy for the build window; blocked pages count as unknown instead |

## Traceability

Which phases cover which requirements. Filled in when the roadmap is created.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SETUP-01 | Phase 1 | Pending |
| SETUP-02 | Phase 1 | Pending |
| SETUP-03 | Phase 1 | Pending |
| RUN-01 | Phase 10 | Pending |
| RUN-02 | Phase 10 | Pending |
| RUN-03 | Phase 10 | Pending |
| RUN-04 | Phase 2 | Pending |
| RUN-05 | Phase 2 | Pending |
| SCRP-01 | Phase 3 | Pending |
| SCRP-02 | Phase 3 | Pending |
| SCRP-03 | Phase 3 | Pending |
| EXTR-01 | Phase 4 | Pending |
| EXTR-02 | Phase 4 | Pending |
| EXTR-03 | Phase 4 | Pending |
| QUAL-01 | Phase 5 | Pending |
| QUAL-02 | Phase 5 | Pending |
| QUAL-03 | Phase 5 | Pending |
| QUAL-04 | Phase 5 | Pending |
| QUAL-05 | Phase 5 | Pending |
| AGNT-01 | Phase 6 | Pending |
| AGNT-02 | Phase 6 | Pending |
| AGNT-03 | Phase 6 | Pending |
| AGNT-04 | Phase 6 | Pending |
| AGNT-05 | Phase 6 | Pending |
| AGNT-06 | Phase 6 | Pending |
| POC-01 | Phase 7 | Pending |
| POC-02 | Phase 7 | Pending |
| POC-03 | Phase 7 | Pending |
| PAIN-01 | Phase 8 | Pending |
| PAIN-02 | Phase 8 | Pending |
| DRFT-01 | Phase 8 | Pending |
| DRFT-02 | Phase 8 | Pending |
| DRFT-03 | Phase 8 | Pending |
| DRFT-04 | Phase 8 | Pending |
| SEND-01 | Phase 9 | Pending |
| SEND-02 | Phase 9 | Pending |
| SEND-03 | Phase 9 | Pending |
| TRCE-01 | Phase 2 | Pending |
| TRCE-02 | Phase 9 | Pending |
| TRCE-03 | Phase 10 | Pending |
| DATA-01 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 41 total
- Mapped to phases: 41
- Unmapped: 0

---
*Requirements defined: 2026-11-03*
*Last updated: 2026-11-03 after roadmap creation (traceability filled)*
