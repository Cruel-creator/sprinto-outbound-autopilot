<!-- GSD:project-start source:PROJECT.md -->

## Project

**Sprinto Outbound Autopilot**

A Python CLI pipeline that takes a list of company domains and, with no human decisions in the loop, works out which ones fit Sprinto's ICP. For each fit it picks the right decision-maker, works out their two most likely compliance pain points, writes a personalised cold email to them by name with a specific hook, and sends it through the Resend API so it lands in the user's own Gmail inbox. It replaces the Sprinto Growth Lead's manual 15–20 minutes of research and writing per company, where quality slips by the end of a list of 8–15 companies.

Built for MESA PGP Cohort 4, Term 2, AI Case 2 ("Cold Outreach, at Scale"), session on 3 Nov 2026 (1.5 hours).

**Core Value:** Run it on a list of domains and a personalised email that a human would actually reply to lands in the inbox. Every decision behind it (why this company, why this person, why this email) can be defended with cited evidence.

### Constraints

- **Timeline**: Live session on 3 Nov 2026, 1.5 hours. The walking skeleton must deliver an email to the inbox early.
- **Tech stack**: Python 3.12, `google-genai` (Gemini), Resend for sending (`resend` SDK or `httpx` POST), `httpx` plus BeautifulSoup for scraping. Chosen for minimal setup and the quickest path to a working send.
- **LLM**: Google Gemini API only, the user's key in `.env`.
- **PoC source**: the Hunter.io Domain Search API on the free tier, 25 searches a month. Call it only for qualified companies, cache every response, and never re-query a cached domain unless `--force` is passed.
- **Email recipient**: Always the user's own address, from `.env`. Never a prospect.
- **Secrets**: `.env` (Gemini, Resend and Hunter keys) and the real `contacts.csv` are never committed (`.gitignore`).
- **Autonomy**: No interactive prompts during a run. The pipeline must decide every step itself.

<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->

## Technology Stack

## READ FIRST: three findings that change the plan

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12 (installed locally) | Runtime | `google-genai` 2.x needs >=3.11; `google-api-python-client` needs >=3.10. 3.12 has universal wheels for lxml/pydantic-core; 3.14 is also installed but newest = highest wheel risk in a 90-minute window. |
| google-genai | 2.34.0 (released 2026-10-29), pin `<3` | Gemini SDK: extraction, qualification, agent loop, drafting, grounding | The only supported Gemini SDK (`google-generativeai` last released 0.8.6 on 2025-12-16, deprecated). Covers structured output, function calling, Google Search tool in one package. README itself advises pinning `<3.0.0` because the next major changes automatic function calling. |
| pydantic | 2.14.2 | Schemas for every LLM step (company, qualification, contact choice, pain points, email) and the decision trace | google-genai accepts a Pydantic class directly as `response_schema` and returns `response.parsed`. Same models serialize the JSON trace (`model_dump_json`). |
| google-api-python-client | 2.201.0 | Gmail API client (`users.messages.send`) | The official client. Quickstart requires Python >=3.10.7. |
| google-auth-oauthlib | 1.5.0 | Desktop OAuth flow (`InstalledAppFlow.run_local_server`) | Official; produces `token.json`. |
| google-auth-httplib2 | 0.4.4 | Transport glue Google's quickstart installs alongside the above | Listed in the official install command; keep it so `build()` works without surprises. |
| httpx | 0.28.1 | HTTP fetching (site pages, Jina fallback) | Already in the dependency tree (google-genai uses it), so zero extra install cost. Sync client is enough. |
| beautifulsoup4 + lxml | 4.15.0 + 6.1.3 | HTML to text, link discovery | Lets us keep footers and `<img alt>` text, which is exactly where "SOC 2 Type II" badges live. |
| python-dotenv | 1.2.4 | Load `.env` (`GEMINI_API_KEY`, recipient, etc.) | Standard, one line. |
| tenacity | 9.1.4 | Retry/backoff on 429/503 from Gemini | **Pin must be 9.1.x**: `google-genai` 2.34.0 requires `tenacity<9.2.0`; pinning 9.2.1 makes pip fail with ResolutionImpossible (verified with `pip install --dry-run` on 3.12). Already a transitive dep. |

### Gemini model IDs (verified against Google's model page and pricing page, 2026-11-03)

| Role | Model ID | Free tier | Paid price (per 1M in / out) | Use for |
|------|----------|-----------|------------------------------|---------|
| **Default / fast** | `gemini-3.5-flash-lite` | Yes (10 RPM, 500 RPD per 3rd-party table) | $0.30 / $2.50 | Extraction, contact selection, pain points, agent loop turns, grounding (if billing on) |
| **Strong** | `gemini-3.8-flash` ("most intelligent Flash") | Yes (5 RPM, 20 RPD per 3rd-party table, too low for a full run) | $0.75 / $3.75 (rises to $1.50 / $7.50 on 2027-01-01) | Final email draft and qualification verdict, ONLY if billing is on |
| Free grounding fallback | `gemini-2.5-flash-lite` | Grounding free to 500 RPD | n/a | `GEMINI_MODEL_GROUNDING` when staying on free tier |
| Alias (do not hard-code) | `gemini-flash-latest` | n/a | n/a | README uses it; avoid in pipeline so behavior is stable across the session |
| Overkill | `gemini-4-argon` | Not available | $2 / $10 (rises Dec 1) | Do not use. No free tier, not needed for 120-word emails. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `argparse`, `csv`, `json`, `logging`, `pathlib`, `email.message`, `base64`, `time` (stdlib) | n/a | CLI, contacts.csv, traces, logs, MIME, throttle | Always. No typer, pandas, jinja, loguru needed. |
| Jina Reader (`https://r.jina.ai/<url>`) | HTTP service, no package | JS-rendered fallback fetch (headless-browser render, returns markdown) | When httpx returns < ~800 chars of text, a JS shell, or 403. No key: 20 RPM per IP. Free key: higher (sources disagree: 100/200/500 RPM; verify), 10M free tokens per key. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `.env` + `.gitignore` | Secrets | Ignore `.env`, `credentials.json`, `token.json`, `runs/`, `.venv/`. |
| `smoke.py` (write first, 10 min) | Walking skeleton: 1 structured call, 1 grounded call, 1 Gmail send to self | Proves key tier, model IDs, OAuth, and recipient before any pipeline code exists. |

## Requirements (exact, verified to resolve together on Python 3.12)

## Copy-paste snippets

### 1. Gemini client, throttle, retry, structured output (Pydantic)

# llm.py

### 2. Gemini with Google Search grounding (separate call; returns text + citations)

### 3. Agent loop (manual function calling, one tool wraps grounding)

### 4. Scraping: default httpx + BeautifulSoup, fallback Jina Reader

### 5. Gmail: OAuth desktop flow + send

# gmail_send.py

### Google Cloud console setup (about 8 minutes; do it while code is being written)

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `client.models.generate_content` | Interactions API (`client.interactions.create`) | Google now says it recommends Interactions "for all new development" and its docs/examples are written in it (steps, `response_format`, `{"type":"google_search"}`), but also says `generateContent` "remains fully supported". For a stateless 90-minute pipeline `generate_content` has the most stable docs and examples. Revisit if you want server-side tool combining (search + custom function + JSON in one call). |
| Two-step grounding (grounded text, then structured) | Search + JSON schema in a single Gemini 3 call | Only if on Gemini 3 and you accept preview behavior; saves one call per lookup. |
| httpx + BeautifulSoup, Jina fallback | trafilatura | Article/blog extraction. It strips nav/footer boilerplate, which is where trust badges and compliance logos live on SaaS homepages. Wrong tool for ICP signals. |
| Jina Reader fallback | Firecrawl | Needs an account/key; free plan 1,000 credits (sources disagree on monthly vs one-time) and low concurrency. Better output on hard sites, but adds a signup and a dependency. Switch to it only if Jina rate-limits you. |
| Jina Reader fallback | Playwright | A specific must-have site renders nothing even through Jina. Costs ~150 MB+ browser download, install risk on Windows, extra code. Not for a 90-minute build. |
| `argparse` | typer + rich | If you want pretty progress output after everything works. Typer 0.27.3 and rich 15.0.0 are current, but they are polish, not need. |
| `python-dotenv` + `os.environ` | pydantic-settings | Needs Python >=3.11 and adds a layer; five env vars do not justify it. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `google-generativeai` (`import google.generativeai as genai`, `GenerativeModel`) | Deprecated predecessor; last release 0.8.6 (2025-12-16); most tutorials online still show it, so copy-paste from search results will break | `google-genai` 2.34.0 (`from google import genai`) |
| `gemini-2.0-flash`, `gemini-2.0-flash-lite`, `gemini-3-pro-preview`, `gemini-3.1-flash-lite-preview` | Already shut down per Google's model page | `gemini-3.5-flash-lite` / `gemini-3.8-flash` |
| `gemini-2.5-flash`, `gemini-2.5-pro` | Deprecated; auto-route to other models on 2026-12-01 | Same as above. (`gemini-2.5-flash-lite` is the one exception, kept only as free-tier grounding fallback.) |
| `gemini-4-argon` | No free tier, 2x-4x price, no benefit for 120-word emails | `gemini-3.8-flash` |
| `tools=[{"google_search_retrieval": ...}]` | Old tool name for pre-Gemini-2 models; Gemini 3+ uses `google_search` | `types.GoogleSearch()` |
| LangChain, LlamaIndex, CrewAI, ADK | Heavy dependency trees, hide the tool-call trace you must show for the decision trail, extra failure modes in a 90-minute build | ~40 lines of manual loop (snippet 3) |
| Playwright / Selenium as the default scraper | Browser binaries, slow, flaky install on Windows, async complexity | httpx first, Jina Reader on failure |
| `smtplib` / app passwords | The brief and PROJECT.md require Gmail API OAuth | Gmail API as above |
| `oauth2client`, `flow.run_console()`, OOB redirect | Removed or deprecated Google auth paths | `google-auth-oauthlib` `run_local_server(port=0)` |
| `tenacity==9.2.1` (latest) | Conflicts with `google-genai 2.34.0` (`tenacity<9.2.0`) | `tenacity==9.1.4` |
| pandas, Jinja2, SQLite | Not needed for a CSV of a few contacts and a markdown report | `csv.DictReader`, f-strings, JSON files |
| Interactive prompts anywhere in the run | Violates the "no human in the loop" constraint | Do OAuth consent once, ahead of time |

## Stack Patterns by Variant

- All steps on `gemini-3.5-flash-lite`; `GEMINI_MODEL_GROUNDING=gemini-2.5-flash-lite` (the only free grounding).
- `_throttle(min_gap=6.5)` plus `max_steps=4` in the agent loop. 10 companies finish in roughly 10-15 minutes. Run the full list once the night before and again live, or run live with a pre-warmed list of 8.
- Do not run the final demo while burning the daily quota on retries: 500 RPD resets at midnight Pacific.
- `GEMINI_MODEL_STRONG=gemini-3.8-flash` for qualification verdict and email draft; `GEMINI_MODEL_FAST` and `GEMINI_MODEL_GROUNDING` on flash-lite or 3.8-flash. Raise throttle gap to ~1s. 5,000 grounded searches/month free covers the whole project.
- Falls through to Jina automatically (snippet 4). If Jina rate-limits (20 RPM unkeyed), add `JINA_API_KEY` (free key) and a 3s sleep between fetches.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| google-genai==2.34.0 | tenacity>=8.2.3,<9.2.0 | Hard conflict with tenacity 9.2.x. Resolved set verified via `pip install --dry-run` on Python 3.12: pydantic 2.14.2, httpx 0.28.1, requests 2.34.2, websockets 17.4. |
| google-genai 2.x | Python >=3.11 | Python 3.9/3.10 will fail to install. |
| google-api-python-client 2.201.0 | Python >=3.10 | Quickstart says >=3.10.7. |
| google-genai `generate_content` | thinking config | `thinking_level` (Gemini 3.x) and `thinking_budget` (2.5) are not interchangeable; mixing them errors. Leave unset. |
| google-genai 2.x | next major (3.0) | Direct `generate_content` stops doing automatic function calling; we disable AFC and loop manually, so unaffected. Pin `<3`. |

## Confidence Summary

| Recommendation | Confidence | Basis |
|----------------|------------|-------|
| `google-genai==2.34.0`, `google-generativeai` dead | HIGH | PyPI JSON (2026-10-29 release, 0.8.6 last 2025-12-16), PyPI project page, GitHub README |
| Model IDs `gemini-3.5-flash-lite`, `gemini-3.8-flash` and shutdown list | HIGH | Official models page and pricing page fetched 2026-11-03 |
| Search grounding not free on Gemini 3+, free on 2.5 Flash/Flash-Lite 500 RPD | HIGH | Official pricing page, quoted row by row |
| Free-tier RPM/RPD numbers | MEDIUM-LOW | Third-party (scriptbyai), Google defers to the per-project AI Studio page. Verify in smoke test. |
| Pydantic `response_schema` + `response.parsed`, schema-subset caveats | HIGH | Python SDK docs and official structured-output page |
| Manual function-calling loop shape | MEDIUM-HIGH | SDK docs (AFC disable, `Part.from_function_response`); thought-signature note from Gemini 3 docs |
| `grounding_metadata` field names, `ThinkingConfig` spelling | MEDIUM | From SDK types/knowledge; official pages fetched showed Interactions API instead. Confirm in smoke test. |
| Gmail OAuth + send code, scope, setup steps | HIGH (code, steps 1-3, 5-6), MEDIUM-HIGH (test-user step) | Official quickstart and sending guide |
| httpx+BS4 default, Jina fallback | MEDIUM-HIGH | Jina docs (default engine renders JS, 20 RPM unkeyed); choice reasoning is design judgment, validate on the 8-10 test domains |

## Sources

- https://pypi.org/pypi/google-genai/json, pypi.org/project/google-genai (2.34.0, 2026-10-29; Python >=3.11; pin <3.0.0 advice) (HIGH)
- https://github.com/googleapis/python-genai README (generate_content, `response_json_schema`, function calling, AFC deprecation) (HIGH)
- https://googleapis.github.io/python-genai/ (`response_schema=Pydantic`, `response.parsed`, manual FC with `AutomaticFunctionCallingConfig(disable=True)`, `errors.APIError`) (HIGH)
- https://ai.google.dev/gemini-api/docs/models (redirects to aistudio.google.com/docs/models): current IDs, shutdowns, 2026-12-01 routing (HIGH)
- https://aistudio.google.com/docs/pricing: per-model free tier, prices, "Grounding with Google Search" free-tier rows (HIGH)
- https://aistudio.google.com/docs/google-search: Gemini 3+ per-query billing, 5,000 free/month, 1,500 RPD default cap (HIGH)
- https://aistudio.google.com/docs/structured-output: schema subset, tools + structured output on Gemini 3 (Preview) (HIGH)
- https://aistudio.google.com/docs/tool-combination, /function-calling, /thinking: Gemini 3 tool combination, thought signatures, thinking levels (HIGH; examples are Interactions-API only)
- https://aistudio.google.com/docs/migrate-to-interactions: "generateContent remains fully supported"; generateContent `tools=[{"google_search": {}}]` form (HIGH)
- https://aistudio.google.com/docs/rate-limits: per-project limits, defers free-tier numbers to AI Studio (HIGH); https://www.scriptbyai.com/gemini-api-free-tier-limits/: free-tier RPM/RPD table (LOW-MEDIUM)
- https://developers.google.com/workspace/gmail/api/quickstart/python and /guides/sending: install command, Google Auth Platform setup, `run_local_server(port=0)`, MIME + base64url send (HIGH)
- https://jina.ai/reader/ and https://www.firecrawl.dev/pricing: Reader rate limits and JS-rendering default engine; Firecrawl free credits (MEDIUM; sources conflict on exact RPM and monthly-vs-one-time credits)
- Local verification: `pip install --dry-run -r requirements.txt` on Python 3.12 (exposed the tenacity conflict); PyPI JSON for all versions (HIGH)

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-fast` for a trivial task inline, with no subagents and no PLAN.md
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
