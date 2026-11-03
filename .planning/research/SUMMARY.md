# Project Research Summary

**Project:** Sprinto Outbound Autopilot
**Domain:** AI-driven B2B cold-outreach pipeline. A Python CLI that scrapes, extracts, qualifies with a bounded agent loop, finds the PoC via the Hunter.io API, identifies pain points, drafts, and sends via Resend to the builder's own inbox.
**Researched:** 2026-11-03
**Confidence:** MEDIUM overall. HIGH on the SDK and scraping choices, MEDIUM on ICP weights and benchmarks, LOW-MEDIUM on free-tier quota numbers.

## Decisions That Override Research (made after research, 2026-11-03)

The four research files were written assuming the **Gmail API** for sending and **Apollo, hand-filled into `contacts.csv`**, for contacts. The user changed both. Where the research files disagree with this section, **this section wins**:

| Area | Research assumed | Now decided | Consequences |
|------|------------------|-------------|--------------|
| Sending (Step 7) | Gmail API with OAuth (`gmail.send`), `auth.py`, `token.json`, Cloud Console setup | **Resend API** (`RESEND_API_KEY`) sending from `onboarding@resend.dev` unless a domain is verified | Drop `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`, `auth.py` and every OAuth pitfall. Sending from `onboarding@resend.dev` only delivers to the Resend account owner's email, so `TO_EMAIL` must be that address. Free tier: 100 emails a day. Use the `resend` SDK or a plain `httpx` POST to `https://api.resend.com/emails`. This deliberately departs from the brief's "via Gmail" wording; the email still lands in the user's Gmail inbox. |
| Contacts (Step 4) | Apollo by hand into `contacts.csv`, no API | **Hunter.io Domain Search API** (`HUNTER_API_KEY`), free tier of 25 searches a month | `GET https://api.hunter.io/v2/domain-search?domain=X&seniority=senior,executive&api_key=...` returns up to 10 people (name, position, seniority, department, LinkedIn, email, confidence). Call it **only for qualified companies**, cache every response on disk, and re-query only with `--force`. Python role rules by company size pick the person from Hunter's candidates. `contacts.csv` becomes an optional fallback or override, and a company with neither source is `NO_CONTACT`. |
| Send fallback | n/a | An "Open in Gmail" compose link in every `report.md` | Pre-fill `to=` with `TO_EMAIL` (the builder's own address), **never the prospect's**. Label it "Open in Gmail (manual fallback, to yourself)". |

## Executive Summary

Sprinto Outbound Autopilot is a sequential, unattended Python CLI. It turns a list of company domains into evidence-cited qualification decisions and, for each qualified company, a personalised cold email. The email always goes to the builder's own inbox, never to a prospect. Builders of this kind of tool typically use a linear pipeline of typed steps. They keep the LLM to extraction and prose, and move every number (score, threshold, word count, recipient) into deterministic code. The stack is deliberately small:
- `google-genai` 2.x on Python 3.12
- Pydantic 2 schemas
- httpx and BeautifulSoup for scraping
- the Hunter.io API for contacts
- Resend for sending
- a JSON trace plus a `report.md` per company

Four decisions carry the design:
1. **One linear pipeline, one loop.** The only agent loop sits inside qualification, and it is bounded. It gathers evidence into an append-only ledger and never scores.
2. **JSON controller loop.** Each iteration is one schema-validated call that returns a "next action", instead of native Gemini function calling. No request ever combines Google Search grounding with a schema or custom tools.
3. **Grounding stands alone.** Google Search grounding is always a separate, schema-free call, wrapped as a Python tool.
4. **Python computes the score.** The 0–100 score comes from a researched ICP rubric (`config/icp.yaml`), with hard disqualifiers and caps.

The build order is a walking skeleton: a Resend send to self and a Gemini preflight first, then one domain end to end, then depth.

The main risks:
- fabricated personalisation
- unreachable pages read as "no certification", which scores as the strongest ICP signal
- free-tier quotas for Gemini, Gemini grounding and Hunter's 25 searches a month
- an accidental send to a prospect
- deprecated or drifting Gemini model IDs

The mitigations:
- a quote-substring check on every cited fact
- typed fetch outcomes, where `BLOCKED` never counts as `absent`
- model IDs read from env, with a preflight check at startup
- a disk cache with replay for the demo
- a `send()` function with no `to` parameter

**Top open question, to settle at minute 0:** is the Gemini key's project on the free tier, or is billing enabled?

## Key Findings

### Recommended Stack

```
google-genai==2.34.0        # pin <3
pydantic==2.14.2
httpx==0.28.1
beautifulsoup4==4.15.0
lxml==6.1.3
python-dotenv==1.2.4
tenacity==9.1.4             # google-genai 2.34.0 requires tenacity<9.2.0
resend                      # optional; a plain httpx POST works too (pin a version at install)
```

- **Python version:** create the venv with `py -3.12 -m venv .venv`. google-genai 2.x needs Python 3.11 or newer, and plain `python` can resolve to the Windows Store stub.
- **Hunter.io:** a plain `httpx` GET, no SDK.
- **Model IDs come from env:** `GEMINI_MODEL_FAST`, `GEMINI_MODEL_STRONG`, `GEMINI_MODEL_GROUNDING`. Do not hardcode them, and do not use the `gemini-flash-latest` alias.
- **Avoid these models and SDKs:**
  - `google-generativeai` (deprecated)
  - `gemini-2.0-*`
  - `gemini-2.5-flash` (shuts down 2026-12-01 and auto-routes to another model)
  - `gemini-4-argon` (no free tier, and not needed)

**Core technologies:**
- **`google-genai` 2.34.0:** the only supported Gemini SDK. It covers structured output, grounding and retry options.
- **Pydantic 2:** schemas for every LLM step and for the JSON trace. `response_schema` accepts a Pydantic class and returns `response.parsed`.
- **httpx + BeautifulSoup:** keeps `alt` text and footer content, which is where trust badges live. trafilatura is wrong here because it strips footers.
- **Hunter.io Domain Search:** automatic contact lookup. Cache results to protect the 25 searches a month.
- **Resend:** one HTTPS call to send, with no OAuth.
- **`tenacity` 9.1.x:** retries with backoff on 429 and 5xx errors.

### Expected Features

**Must have (table stakes; without these the brief fails):**
- **Domain loop:** runs the whole list with per-domain isolation, so one bad site never kills the batch.
- **Scrape:** homepage plus key paths (`/pricing`, `/security`, `/trust`, `/customers`, `/about`, `/careers`), keeping alt text, link hrefs and image filenames.
- **Extract:** Gemini structured output with evidence quotes and URLs. `unknown` is a first-class value.
- **Scored qualifier:** rubric in YAML, 0–100 score computed in code, a threshold, hard disqualifiers and a stated reason.
- **Agent loop:** three tools (more site pages, grounded web research, job postings), a hard budget, and every result stored as evidence.
- **PoC selection:** Hunter candidates chosen by deterministic role rules, with a stated reason and a `NO_CONTACT` path. Never invent a person.
- **Pain points:** two, each tied to evidence IDs.
- **Draft:** prompt target 80–100 words, validator hard cap 110 (the brief's outer limit is 120), one specific hook, one soft CTA, signed as Sprinto Growth Lead.
- **Send:** via Resend to the builder's own address only.
- **Decision trail:** a JSON trace and `report.md` per company, plus a batch `summary.md` that shows rejections as first-class results.

**Should have (differentiators, pick what fits the 90 minutes):**
- **Evidence ledger and validator:** the draft validator rejects factual claims with no evidence behind them.
- **Trust-center fingerprints:** recognise Sprinto, Vanta, Drata and SafeBase trust centers. A fully certified company is capped at 40 and tagged `switch_or_expand_candidate`.
- **Threshold-aware stopping:** the cheap score-bound check is v1.
- **Expansion tagging:** a company with SOC 2 only gets an ISO 27001 or GDPR angle.
- **Deterministic hook ladder:** compliance signal, then enterprise gap, then funding, then geography.
- **Persona angle:**
  - Founder: deal velocity and cost.
  - CTO: engineering hours.
  - GRC lead: juggling several frameworks at once.
- **Confidence labels:** explicit handling of "unknown".

**Deferred:** follow-up sequences, reply tracking, CRM sync, open and click tracking, email verification, a web UI, Playwright, A/B testing of hooks.

**Anti-features (deliberately not built):**
- sending to prospects
- a dry-run toggle or approval prompt
- scores the LLM assigns with no rubric
- invented personalisation
- LinkedIn scraping
- a vector DB

### Architecture Approach

Data flows strictly forward:

`domain -> RawSite -> CompanyProfile -> (evidence ledger grows) -> QualificationResult -> ContactChoice -> PainPoints -> EmailDraft -> SendResult`

- **When steps 4–7 run:** only when the verdict is `qualified`. That keeps Hunter calls to qualified companies.
- **Step shape:** every step is `run(input_model, ctx) -> output_model`, and steps never import each other.
- **Trace and report:** the orchestrator flushes `trace.json` after every step. `report.md` is rendered from the trace with no LLM calls.

**Major components:**
1. **`run.py` and `orchestrator.py`:** the CLI, the domain loop, per-domain `try/except`, and a status for each company (`sent`, `not_qualified`, `insufficient_data`, `no_contact`, `failed`).
2. **`llm.py`:** the only module that imports `google.genai`. Owns retry, validate-and-retry, the disk cache keyed on model, schema and prompt, usage logging, and `grounded_search()`.
3. **`scrape.py` and `tools.py`:** typed fetch results (`OK`, `NOT_FOUND`, `BLOCKED`, `TIMEOUT`, `EMPTY_SHELL`, `NON_HTML`, `TOO_BIG`), the same-site allow-list, and the three tools. Only these write evidence.
4. **`agent.py`:** the bounded JSON controller loop. Each iteration returns `findings` plus `next_action`; Python runs the tool and decides when to stop.
5. **`qualify.py` and `config/icp.yaml`:** deterministic scoring. A signal counts only if its evidence ID resolves in the ledger.
6. **`contacts.py`:** calls Hunter for qualified domains only, caches responses, and selects by role-priority rules, falling back to the optional `contacts.csv`.
7. **`pains.py`, `draft.py`, `send.py`:**
   - `pains.py` cites evidence IDs.
   - `draft.py` has a validator and one regeneration.
   - `send.py` calls Resend and has no recipient parameter.
8. **`trace.py` and `report.py`:** an append-only trace with the evidence ledger, and a deterministic renderer that includes the compose-link fallback.

**Key patterns:**
- **Gather, then judge:** the LLM says "present, E4", and Python adds the points.
- **Quote verification:** a quote counts only if it appears in the fetched page text. Search-sourced evidence is marked `verified=False`.
- **Typed steps** with an injected context object.
- **Flush after every step.**
- **Prompts live in `prompts/*.md`.**

### Critical Pitfalls

1. **Fabricated personalisation.**
   - Every fact is stored as `{value, quote, source_url}`.
   - A substring check downgrades any quote that isn't in the fetched page.
   - The drafter only receives verified hook candidates and must return a `hook_id` that exists.
   - Funding older than about 18 months counts as stale.
   - Drop grounded answers whose sources don't mention the domain.
2. **An unreachable page read as "no signal".**
   - Fetch outcomes are typed, and only a real 404 counts as `absent`.
   - `BLOCKED`, `TIMEOUT` and `EMPTY_SHELL` mean `unknown`.
   - Detect soft 404s by hashing the page text against the homepage.
   - With too many unknowns, the verdict is `insufficient_data`.
3. **Grounding, structured output and function calling in one request.**
   - Use two calls: grounded free text first, then a separate structured parse.
   - Keep schemas flat, with `Literal` enums.
   - Enforce word counts and score ranges in Python, because the API strips `minLength` and `maxLength`.
   - Store grounding titles and domains when they're captured.
4. **Exhausting the Hunter quota (25 searches a month).**
   - Only qualified companies trigger a search.
   - Cache every response to `cache/hunter/<domain>.json`, and re-query only with `--force`.
   - Record the `meta.results` count in the trace.
   - Startup can call Hunter's free `/v2/account` endpoint to check the calls left and warn when they're low.
5. **Emailing a real prospect.**
   - `send_email(subject, body)` has no `to` parameter, and the recipient comes from `TO_EMAIL` in `.env`.
   - The prospect's address (from Hunter) appears only in the report and an intended-recipient footer, never in the Resend `to` field.
   - A unit test asserts `to == TO_EMAIL` even when the contact data is hostile.

Other pitfalls to watch during the build:
- **Gemini free-tier 429s:** cache everything and pace calls.
- **Agent loop runaway:** hard caps plus dedupe on `(tool, arg)`.
- **Non-determinism:** score in code, render the report from the trace, and keep a replay run.
- **Windows encoding and paths:** `encoding="utf-8"` everywhere, `utf-8-sig` for CSV and `.env`, and `pathlib` anchored on `__file__`. The project path contains a space.
- **Secrets in git:** write `.gitignore` before the first `git add`.
- **Resend sandbox:** sending from `onboarding@resend.dev` to anyone other than the account owner gets rejected.
- **Demo-day failures:** do a golden run, keep `--replay` working, run preflight on the demo network, and have a hotspot ready.

## Cross-Cutting Conflicts and Recommended Resolutions

| # | Topic | Sources disagree | Resolution (adopt this) |
|---|-------|------------------|-------------------------|
| 1 | Agent loop mechanism | STACK: native function calling with AFC disabled. ARCHITECTURE/PITFALLS: a JSON "next action" controller. | **JSON controller loop.** One schema-validated object per iteration; Python executes the tool. Native function calling is only a fallback. |
| 2 | Email word cap | The brief says under 120; FEATURES 60–100; PITFALLS a hard 110. | **Prompt target 80–100; validator hard cap 110** over the whole body. 120 is the outer limit reported in `report.md`. |
| 3 | Agent caps | 3 vs 4 iterations; a 90 s vs 120 s wall clock. | **4 tool calls total (one per iteration), at most 2 grounded searches, one final assess-only call, a 120 s soft wall clock per domain.** Stop early on score bounds or a repeat action. |
| 4 | Gemini model IDs | STACK: `gemini-3.5-flash-lite` fast, 3.8 strong with billing. PITFALLS: 3.6 primary. | **Read from env. Default `GEMINI_MODEL_FAST=gemini-3.5-flash-lite`, fallback `gemini-2.5-flash-lite`; 3.6 or 3.8 only with billing.** Preflight breaks the tie. |
| 5 | Grounding on the free tier | Not free on 3.x; free only on 2.5-flash-lite (500 requests a day). | **Default `GEMINI_MODEL_GROUNDING=gemini-2.5-flash-lite` on the free tier.** Confirm in AI Studio at minute 0. |
| 6 | Sender | Research assumed Gmail OAuth. | **Resend (decided).** No OAuth setup, so no OAuth pitfalls. |
| 7 | Temperature and thinking | ARCHITECTURE: 0.2. PITFALLS/STACK: use the defaults. | **Set neither.** Determinism comes from the cache and replay. Set `max_output_tokens` to 4,000–8,000. |
| 8 | Rubric shape | FEATURES: 14 signals in 4 blocks summing to 100. ARCHITECTURE: an 8-signal example. | **Use the FEATURES Part A rubric** inside the ARCHITECTURE container shape. Thresholds: 60 qualify, 75 priority, 45–59 nurture. Caps: 55 with no upmarket pull, 40 if fully certified. |
| 9 | Contact source | Research: Apollo into `contacts.csv`. | **Hunter.io API (decided)**, with the optional CSV override (`domain,first_name,last_name,title,email,linkedin,source_url`). Greet using `first_name` exactly as returned; never call `.title()` on it. |
| 10 | Jina Reader | STACK recommends it; PITFALLS/ARCHITECTURE don't. | **Off by default, behind `JINA_ENABLED`.** |
| 11 | Cache timing | v1.x vs Phase 1. | **Cache in v1.** It protects both the Gemini and Hunter quotas and enables `--replay`. |
| 12 | Threshold-aware stopping | v1.x vs v1. | **Cheap checks in v1:** score-bound exit, repeat guard, budget. |
| 13 | Subject line | Prefix vs company name; Gmail threads identical subjects together. | **Unique subject per company that includes the company name**, plus an intended-recipient footer. |
| 14 | Compose-link fallback | New decision. | **Pre-fill `to=` with `TO_EMAIL` only.** Build it with `urllib.parse.quote`. |

## Implications for Roadmap

The build is a 90-minute live session, so each phase is time-boxed and ends with something runnable.

### Phase 1: Plumbing and external risk burn-down (about 0:00–0:15)
**Delivers:**
- a Python 3.12 scaffold
- `.gitignore` (`.env`, `.env.*` except `.env.example`, `cache/`, `out/`, `.venv/`, `__pycache__/`, the real `contacts.csv`), written before any secret exists
- a hardcoded "hello" sent to self through Resend
- a preflight that makes one tiny structured Gemini call and one grounded call per configured model, and one Hunter `/v2/account` check
- the free-tier vs billing decision, recorded
- `llm.py` with retry, validate-and-retry, the cache and `grounded_search()`

### Phase 2: Walking skeleton, one domain end to end (about 0:15–0:35)
**Delivers:**
- `models.py`
- homepage-only scraping
- real structured extraction
- single-call qualification with no loop yet
- Hunter lookup plus a simple pick
- one prompt each for pains and draft
- a Resend send
- a trace flushed after every step
- per-domain `try/except`, and the cache from the start

### Phase 3: Defensibility layer (about 0:35–0:50)
**Delivers:**
- typed fetch outcomes and soft-404 detection
- the evidence ledger, with quotes and `unknown`
- the substring check
- `report.md` with the compose link
- a batch `summary.md`
- `model_version` recorded per call

### Phase 4: Real qualification and the agent loop (about 0:50–1:10)
**Delivers:**
- `config/icp.yaml` from the FEATURES Part A rubric
- `score()` in Python
- the assess-and-plan prompt, with untrusted page text wrapped
- the JSON controller loop with the caps above
- tools in this order: `fetch_page` (same-site allow-list), then `web_research` (grounded), then `job_postings` (ATS JSON probe, falling back to search)

### Phase 5: Contacts, pains and writing quality (about 1:10–1:20)
**Delivers:**
- role-priority selection over Hunter candidates (`rule_fired`, `considered[]`, a reason, a `NO_CONTACT` path, the CSV override)
- pains whose `evidence_ids` must resolve
- a `hook_id` drawn from verified candidates
- the validator: 110-word cap, one CTA, no placeholders, no markdown, banned phrases, no unmapped claims
- greeting and sign-off inserted by Python
- a unique subject per company
- the intended-recipient footer
- `sprinto_facts.md`, a whitelist of 3–6 product facts

### Phase 6: Full run, golden run, demo readiness (about 1:20–1:30)
**Delivers:**
- a full run on the test list
- tuning in YAML only
- `--replay` verified offline
- `--only <domain>`
- clean `git check-ignore` and `git ls-files` checks
- a features freeze 15 minutes before the demo
- preflight on the demo network

**Cut line if time slips**, cutting in this order:
1. ATS probing (keep the search fallback)
2. the LLM tie-break in contacts
3. the critic pass
4. parallelism
5. report formatting

**Never cut:** the send guard, evidence citations, per-domain isolation, the tool budget, the cache (it protects Hunter's quota) and the replay run.

### Research Flags
- **Phase 1:** checks to run live:
  - free tier vs billing
  - limits in the AI Studio rate-limit view
  - the shape of `grounding_metadata`
  - that Resend delivers to `TO_EMAIL`
  - Hunter `/v2/account` credits
- **Phase 4:** design depth: lock the ICP wording and what "sufficient data" means before coding. ATS endpoints are unverified. Trust-center fingerprints are heuristic.
- **Phase 5:** prompt iteration dominates, so budget 20 minutes. Check what Hunter returns for small startups; sparse results mean the CSV fallback.
- **Phases 2, 3 and 6:** standard patterns, no extra research needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | SDK version, Python floor and the tenacity conflict were verified (HIGH). Free-tier RPM/RPD numbers come from a third party (LOW-MEDIUM). Resend and Hunter details are from general knowledge, so verify in the Phase 1 preflight. |
| Features | MEDIUM | Sprinto facts are first-party (HIGH). Rubric weights are judgement, not data-fitted. Email benchmarks conflict, so promise no reply rates. |
| Architecture | MEDIUM-HIGH | Standard patterns. The tool-combination feature is Preview, and the design avoids depending on it. |
| Pitfalls | MEDIUM-HIGH | Model deprecations and structured-output rules come from official sources. Free-tier quotas are LOW confidence until read from AI Studio. |

## Gaps to Address

- **Free-tier grounding and quota:** check AI Studio at minute 0. A 10-company run needs roughly 80–120 Gemini calls.
- **Hunter coverage for small startups:** test domains (getmaxim.ai, bolna.ai, nurix.ai, greptile.com) may come back sparse. The CSV fallback covers that.
- **Hunter budget:** with 25 searches a month, about 4 per full run, roughly 6 full runs are possible with no cache. Cache from the first run.
- **Resend sandbox:** `TO_EMAIL` must equal the Resend account owner's address unless a domain is verified.
- **Test list coverage:** add a domain whose trust center is hosted by a competitor and a domain that is blocked or an empty shell (superjoin.ai is a candidate). Verify both before the demo.
- **Badge images:** nurix.ai's footer badges couldn't be read. If the loop can't resolve them, the verdict is `insufficient_data`.
- **Grounding metadata field names:** confirm them in the smoke test.

## Open Questions

1. **Free tier or billing on the Gemini key?** Decide at minute 0. Enabling billing covers grounding for cents.
2. **Resend sender:** is there a verified domain, or `onboarding@resend.dev`? Which address owns the Resend account?
3. **Final test list:** confirm the two added domains.

## Sources

### Primary (HIGH confidence)
- pypi.org/project/google-genai and github.com/googleapis/python-genai
- aistudio.google.com/docs: models, pricing, google-search, structured-output, deprecations, rate-limits
- local `pip install --dry-run` on Python 3.12
- `.planning/PROJECT.md`

### Secondary (MEDIUM confidence)
- sprinto.com and docs.sprinto.com
- TechCrunch, 2024-04-09
- test-domain company sites, fetched 2026-11-03
- ai.google.dev tool-combination docs
- Belkins and other cold-outreach guides, directional only

### Tertiary (LOW confidence; needs validation)
- scriptbyai free-tier limits
- Jina Reader terms of service
- ATS job-board JSON endpoints
- competitor trust-center fingerprints
- Resend and Hunter limits, from general knowledge; verify in preflight

---
*Research completed: 2026-11-03. Updated the same day with the Resend and Hunter.io decisions.*
*Ready for roadmap: yes.*
