# Stack Research

**Domain:** AI-driven B2B cold-outreach pipeline (Python CLI: scrape, extract, qualify with agent loop, pick contact, pain points, draft, send via Gmail API), built for Sprinto
**Researched:** 2026-11-03
**Confidence:** HIGH on SDK, Gmail, scraping choices. MEDIUM on exact free-tier rate numbers (third-party source). One HIGH-impact gotcha below (Google Search grounding is NOT free on Gemini 3+ models).

---

## READ FIRST: three findings that change the plan

1. **Google Search grounding is not available on the free tier for any Gemini 3.x model.** Google's pricing page lists "Not available" in the Free column for `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-4-argon`. On a paid-tier project, 5,000 grounded searches/month are free (shared across Gemini 3+), then $14/1,000. The only free grounding path is the 2.5 family: `gemini-2.5-flash-lite` (free up to 500 RPD, "not deprecated, served until further notice") and `gemini-2.5-flash` (500 RPD free, but deprecated: auto-routes to `gemini-3.5-flash-lite` on 2026-12-01). **Action in minute 0:** check whether the user's key is on a free or paid project. If free: either (a) attach a billing account to the project in AI Studio (cost for this whole build is cents, and the 5,000/month grounding allowance covers it), or (b) set `GEMINI_MODEL_GROUNDING=gemini-2.5-flash-lite` and stay free. Make the grounding model an env var so this is a one-line switch. (HIGH, official pricing page.)
2. **Free-tier request caps are the real bottleneck, not tokens.** Third-party tables (scriptbyai, MEDIUM-LOW; Google's own rate-limit page defers to the per-account AI Studio rate-limit page): `gemini-3.8-flash` 5 RPM / 20 RPD, `gemini-3.6-flash` 5 RPM / 20 RPD, `gemini-3.5-flash-lite` 10 RPM / 500 RPD, `gemini-3.1-flash-lite` 10 RPM / 500 RPD. A 10-company run is roughly 80-120 calls. That fits `gemini-3.5-flash-lite` on free tier but blows through `gemini-3.8-flash` at 20 RPD. Default every step to flash-lite; use the stronger model only where it earns it, and only if billing is on. Verify real numbers at https://aistudio.google.com/rate-limit for the user's project.
3. **`google-genai` is now 2.x, requires Python >= 3.11, and `google-generativeai` is dead.** The machine has Python 3.12 and 3.14 installed (`py --list`). Use 3.12 (`py -3.12 -m venv .venv`). Plain `python` on this machine resolves to a Windows Store shim in some shells, so use `py -3.12` explicitly.

---

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

Env-driven so it is a one-line change: `GEMINI_MODEL_FAST`, `GEMINI_MODEL_STRONG`, `GEMINI_MODEL_GROUNDING`.

Thinking: Gemini 3.x models use `thinking_level` (flash-lite default `minimal`; 3.8-flash default `medium`, no `minimal`), not `thinking_budget`; setting the wrong one for a model family returns an error. **Do not set thinking config at all** in the first version. Defaults are fine. (HIGH for the rule, MEDIUM that `ThinkingConfig(thinking_level=...)` is the right `generate_content` spelling; docs I could reach showed the Interactions-API spelling only.)

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

---

## Requirements (exact, verified to resolve together on Python 3.12)

`requirements.txt`:

```
google-genai==2.34.0
pydantic==2.14.2
google-api-python-client==2.201.0
google-auth-oauthlib==1.5.0
google-auth-httplib2==0.4.4
httpx==0.28.1
beautifulsoup4==4.15.0
lxml==6.1.3
python-dotenv==1.2.4
tenacity==9.1.4
```

`pip install --dry-run -r requirements.txt` on 3.12 resolved cleanly (pulls requests 2.34.2, websockets 17.4 transitively). `tenacity==9.1.4` is the version pip selects anyway; pinned so it cannot drift.

`.env`:

```
GEMINI_API_KEY=...
GEMINI_MODEL_FAST=gemini-3.5-flash-lite
GEMINI_MODEL_STRONG=gemini-3.5-flash-lite
GEMINI_MODEL_GROUNDING=gemini-3.5-flash-lite
RECIPIENT_EMAIL=you@gmail.com
JINA_API_KEY=
```

(Set `GEMINI_MODEL_STRONG=gemini-3.8-flash` and keep grounding on 3.x only after confirming billing is on. If staying free: `GEMINI_MODEL_GROUNDING=gemini-2.5-flash-lite`.)

---

## Copy-paste snippets

### 1. Gemini client, throttle, retry, structured output (Pydantic)

```python
# llm.py
import os, time
from dotenv import load_dotenv
from google import genai
from google.genai import types, errors
from pydantic import BaseModel
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
FAST = os.getenv("GEMINI_MODEL_FAST", "gemini-3.5-flash-lite")
STRONG = os.getenv("GEMINI_MODEL_STRONG", FAST)
GROUND = os.getenv("GEMINI_MODEL_GROUNDING", FAST)

_last = 0.0
def _throttle(min_gap=6.5):          # ~9 RPM, safe under a 10 RPM free cap
    global _last
    wait = min_gap - (time.monotonic() - _last)
    if wait > 0: time.sleep(wait)
    _last = time.monotonic()

def _retryable(e):                    # 429 / 5xx from the API
    return isinstance(e, errors.APIError) and e.code in (429, 500, 503)

@retry(retry=retry_if_exception(_retryable), wait=wait_exponential(multiplier=3, max=60),
       stop=stop_after_attempt(5), reraise=True)
def generate(model, contents, config):
    _throttle()
    return client.models.generate_content(model=model, contents=contents, config=config)

def structured(model, prompt: str, schema: type[BaseModel], system: str | None = None):
    r = generate(model, prompt, types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=schema))                      # Pydantic class
    # r.parsed is a schema instance, but can be None on a malformed reply: validate from text
    return r.parsed or schema.model_validate_json(r.text)
```

Schema rules (official structured-output docs, HIGH): only a subset of JSON Schema is supported. `minLength`, `maxLength`, `uniqueItems` etc. are silently stripped, so re-validate in Pydantic (e.g. the 120-word limit and score range are enforced in Python, not by the API). `minItems`/`maxItems` are enforced. Deeply nested or huge schemas can 400 with `INVALID_ARGUMENT`. Prefer `Literal[...]` enums and flat models. Have the LLM output per-signal evidence plus booleans/sub-scores and **compute the 0-100 total and threshold in Python**, so the number is deterministic and defensible.

### 2. Gemini with Google Search grounding (separate call; returns text + citations)

```python
def grounded(query: str) -> dict:
    r = generate(GROUND, query, types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())]))   # == tools=[{"google_search": {}}]
    gm = r.candidates[0].grounding_metadata if r.candidates else None
    return {
        "text": r.text,
        "queries": list(gm.web_search_queries or []) if gm else [],
        "sources": [{"title": c.web.title, "uri": c.web.uri}
                    for c in (gm.grounding_chunks or []) if c.web] if gm else [],
    }
```

Why a separate call instead of search + JSON schema in one request: Google documents "structured output + built-in tools (Google Search, URL context, function calling)" only for Gemini 3, marked **Preview**, and the docs I could reach demonstrate it only through the new Interactions API. On 2.5 models search and JSON mode do not combine. The two-step pattern (grounded free-text call, then `structured()` over that text) works on every model, keeps the `sources` list for `report.md` citations, and avoids preview behavior. `grounding_metadata` field names (`grounding_chunks[].web.uri/title`, `web_search_queries`) are from SDK types, not the pages I fetched: confirm in the smoke test (MEDIUM). Source URIs are usually Google redirect links with the site domain as title; cite the title plus the URI.

Gemini 3+ bills per search query the model decides to run (multiple per request count separately); keep queries few by asking for one focused thing per call.

### 3. Agent loop (manual function calling, one tool wraps grounding)

```python
FETCH_DECL = {"name": "fetch_page",
  "description": "Fetch text of a page on the company's site, e.g. /security, /trust, /pricing, /careers, /customers, /about.",
  "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}
SEARCH_DECL = {"name": "web_research",
  "description": "Google-grounded search for funding stage, news, compliance mentions, or open GRC/security/compliance job postings.",
  "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}

def run_agent(system: str, task: str, impls: dict, max_steps: int = 4):
    cfg = types.GenerateContentConfig(
        system_instruction=system,
        tools=[types.Tool(function_declarations=[FETCH_DECL, SEARCH_DECL])],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
    contents = [types.Content(role="user", parts=[types.Part(text=task)])]
    trace = []
    for _ in range(max_steps):
        r = generate(FAST, contents, cfg)
        contents.append(r.candidates[0].content)        # append verbatim: keeps thought signatures
        calls = r.function_calls or []
        if not calls:
            break
        parts = []
        for fc in calls:
            out = impls[fc.name](**fc.args)
            trace.append({"tool": fc.name, "args": dict(fc.args), "result": str(out)[:1500]})
            parts.append(types.Part.from_function_response(name=fc.name, response={"result": out}))
        contents.append(types.Content(role="tool", parts=parts))
    return trace     # then feed `trace` into structured(..., QualificationVerdict) for the final scored verdict
```

Why manual with AFC disabled: (a) the decision trail requirement needs every tool call and result logged, which automatic function calling hides; (b) the SDK warns the next major version drops AFC from direct `generate_content` calls anyway; (c) a hard `max_steps` cap keeps free-tier request usage bounded. Why `web_research` is a plain function that internally calls `grounded()`: avoids combining built-in search with custom function declarations in one request (supported on Gemini 3 only, preview, requires `validated` tool mode, Interactions-API docs only). Finish with a separate `structured()` call so the verdict is schema-validated, not free text. Append `r.candidates[0].content` unmodified or Gemini 3 can reject/degrade the next turn (thought signatures).

### 4. Scraping: default httpx + BeautifulSoup, fallback Jina Reader

```python
import httpx, os
from bs4 import BeautifulSoup
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"}

def fetch_text(url: str, min_chars: int = 800, cap: int = 20000) -> tuple[str, str]:
    try:
        r = httpx.get(url, headers=UA, follow_redirects=True, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        for t in soup(["script", "style", "noscript", "svg"]): t.decompose()
        for img in soup.find_all("img", alt=True):           # trust badges: "SOC 2 Type II"
            img.replace_with(f" [img: {img['alt']}] ")
        text = " ".join(soup.get_text(" ", strip=True).split())
        if len(text) >= min_chars:
            return text[:cap], "httpx"
    except httpx.HTTPError:
        pass
    h = {"Authorization": f"Bearer {os.environ['JINA_API_KEY']}"} if os.getenv("JINA_API_KEY") else {}
    r = httpx.get("https://r.jina.ai/" + url, headers=h, follow_redirects=True, timeout=45)
    r.raise_for_status()
    return r.text[:cap], "jina"
```

Treat scraped text as untrusted data: wrap it in clear delimiters in prompts and tell the model not to follow instructions inside it.

### 5. Gmail: OAuth desktop flow + send

```python
# gmail_send.py
import base64, os
from email.message import EmailMessage
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]   # send-only; cannot read the mailbox

def gmail_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)          # opens browser once
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)

def send_email(service, to: str, subject: str, body: str) -> str:
    msg = EmailMessage()
    msg.set_content(body)
    msg["To"] = to                       # ALWAYS RECIPIENT_EMAIL from .env, never a prospect
    msg["Subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return sent["id"]
```

Run `gmail_service()` once by hand (`python -c "import gmail_send; gmail_send.gmail_service()"`) before the demo so the browser consent is done and the unattended pipeline never blocks. `From` is set by Gmail to the authenticated account; no need to set it. Based on Google's official quickstart and sending guide (HIGH). If you ever change `SCOPES`, delete `token.json`.

### Google Cloud console setup (about 8 minutes; do it while code is being written)

1. console.cloud.google.com: create a project (e.g. `sprinto-outbound`).
2. APIs & Services > Library > **Gmail API** > Enable.
3. **Google Auth Platform** (the new name for "OAuth consent screen") > Get started: app name, user support email, contact email, accept policy. Audience: **External** (use **Internal** only if the sending account is on a Google Workspace org you control, which removes the test-user step).
4. Audience > leave Publishing status **Testing** > **Test users > Add users** > add your own Gmail address. (Only listed test users can authorize an unverified app. This step was not on the quickstart page I fetched; it is the standard requirement for External + Testing, MEDIUM-HIGH.)
5. Data Access > Add scope `.../auth/gmail.send` (optional; the client also requests it at runtime).
6. Clients > **Create client** > Application type **Desktop app** > Create > **Download JSON** > save as `credentials.json` in the project root.
7. First run: browser opens, choose the account, click **Advanced > Go to <app> (unsafe)** on the "Google hasn't verified this app" screen (expected in Testing mode), tick the send permission, Continue. `token.json` is written.

Gotchas: in Testing mode refresh tokens expire after 7 days, so if `invalid_grant` appears, delete `token.json` and re-run the consent once. The Gmail quickstart requires Python >=3.10.7. `flow.run_console()` / OOB flow no longer works: use `run_local_server(port=0)`.

---

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

**If the Gemini key's project is on the free tier (most likely):**
- All steps on `gemini-3.5-flash-lite`; `GEMINI_MODEL_GROUNDING=gemini-2.5-flash-lite` (the only free grounding).
- `_throttle(min_gap=6.5)` plus `max_steps=4` in the agent loop. 10 companies finish in roughly 10-15 minutes. Run the full list once the night before and again live, or run live with a pre-warmed list of 8.
- Do not run the final demo while burning the daily quota on retries: 500 RPD resets at midnight Pacific.

**If billing is enabled (recommended if the user is willing; cost is cents):**
- `GEMINI_MODEL_STRONG=gemini-3.8-flash` for qualification verdict and email draft; `GEMINI_MODEL_FAST` and `GEMINI_MODEL_GROUNDING` on flash-lite or 3.8-flash. Raise throttle gap to ~1s. 5,000 grounded searches/month free covers the whole project.

**If a prospect site returns 403 / empty shell:**
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

---
*Stack research for: AI cold-outreach pipeline (Sprinto Outbound Autopilot)*
*Researched: 2026-11-03*
