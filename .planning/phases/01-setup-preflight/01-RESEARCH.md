# Phase 1: Setup & Preflight - Research

**Researched:** 2026-11-03
**Domain:** Windows Python 3.12 project bootstrap, git secret hygiene, live preflight of three external APIs (Gemini via `google-genai` 2.x, Hunter.io, Resend)
**Confidence:** HIGH on stack, error shapes and repo/Windows mechanics (probed live and in a scratch venv this session). MEDIUM on Gemini free-tier grounding eligibility (docs conflict; only the live preflight can settle it).

> No CONTEXT.md exists for this phase (the user chose to continue without discuss-phase), so there is no `## User Constraints` block. The binding constraints are the PROJECT.md locked decisions and the CLAUDE.md directives under "Project Constraints" below.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SETUP-01 | Create the environment with one documented command sequence (Python 3.12 venv plus `requirements.txt`), configure through `.env` (`GEMINI_API_KEY`, `RESEND_API_KEY`, `HUNTER_API_KEY`, `TO_EMAIL`, Gemini model IDs), starting from `.env.example` | "Standard Stack" has a pinned `requirements.txt` that installed cleanly with `pip check` clean on Python 3.12.7 inside a path containing a space. "Windows" pitfalls and the README command sequence cover the rest. |
| SETUP-02 | Secrets (`.env`), `cache/`, `out/`, real `contacts.csv` git-ignored before any secret file exists; `git check-ignore` confirms it | Tested `.gitignore` pattern set (incl. `!.env.example`) and the exact `git check-ignore` semantics (single-path `-q`, `-v` shows negation with exit 0). |
| SETUP-03 | Preflight: per Gemini model one structured + one grounded call, Hunter credits left, Resend can send to `TO_EMAIL`; fails fast with a clear message | Reference `config.py` + `preflight.py` (tested: 14 mocked tests pass; real-network failure paths confirmed with fake keys). Verified error shapes for all three services. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

Source: `E:\Sprinto Case\.claude\CLAUDE.md` (read this session). Treat as locked.

- Python 3.12; `google-genai` for Gemini; Resend for sending (`resend` SDK or `httpx` POST); `httpx` plus BeautifulSoup for scraping. Gemini is the only LLM.
- Secrets: `.env` (Gemini, Resend and Hunter keys) and the real `contacts.csv` are never committed (`.gitignore`).
- Email recipient is always the user's own address from `.env` (`TO_EMAIL`). Never a prospect.
- Hunter: free tier, protect quota, cache every response (later phases; Phase 1 only reads the free `/account` endpoint).
- No interactive prompts during a pipeline run.
- GSD workflow enforcement: file edits go through a GSD command (`/gsd-execute-phase` for planned work).
- **WARNING for the planner:** the CLAUDE.md "Technology Stack" block and `research/STACK.md` still list the Gmail stack (`google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`, `auth.py`, `token.json`, `credentials.json`). `research/SUMMARY.md` "Decisions That Override Research" says Gmail is replaced by Resend and Apollo by Hunter. **Do not install or reference any Gmail package.** Also ignore the STACK.md `RECIPIENT_EMAIL` name: the decided name is `TO_EMAIL`.

## Summary

Phase 1 has two halves. The first is pure plumbing: a `.gitignore` committed before any secret exists, a pinned `requirements.txt` that installs on the user's Windows machine, an `.env.example`, and a short README with the command sequence. The second is `preflight.py`, which proves Hunter, Gemini (per configured model) and Resend work before any pipeline code exists, and which turns every failure into a single line naming the failed service. All of it is small: roughly 250 lines of Python plus tests, a 10-line `.gitignore` and a README. The risk is not code volume, it is the external unknowns (is the Gemini key free-tier or paid, does `TO_EMAIL` equal the Resend account email), which only the live run can answer.

I verified most mechanics this session rather than relying on memory. The pinned stack (`google-genai==2.34.0`, `pydantic==2.14.2`, `httpx==0.28.1`, `beautifulsoup4==4.15.0`, `lxml==6.1.3`, `python-dotenv==1.2.4`, `tenacity==9.1.4`) installs with `pip check` clean into a venv under a path with a space. I called the real Gemini, Hunter and Resend endpoints with fake keys to capture the real bad-key error shapes, mocked the Gemini REST layer with `respx` to prove the structured and grounded code paths and the error classes, and tested `.gitignore` patterns and `git check-ignore` exit-code semantics in a throwaway repo. A reference implementation of `config.py`, `preflight.py` and 14 tests lives in the Code Examples section; it passed in the scratch venv.

Four findings change how the planner should write tasks. (1) A bad Gemini key is **HTTP 400 INVALID_ARGUMENT with reason `API_KEY_INVALID`**, not 403, so the "wrong key" branch must key on the reason or message, not the status. (2) The shell this research ran in already had a `GEMINI_API_KEY` environment variable set (value not read); `python-dotenv`'s default `override=False` would silently prefer it over `.env`, and the SDK also prefers `GOOGLE_API_KEY` over `GEMINI_API_KEY`. Load `.env` explicitly and pass `api_key=` to the client. (3) Google's pricing page says Google Search grounding is **not available on the free tier for Gemini 3.x**, only for `gemini-2.5-flash-lite` / `gemini-2.5-flash` (500 RPD), which collides with the literal wording of success criterion 4 ("grounded call for each configured Gemini model"). I recommend only the `GEMINI_MODEL_GROUNDING` model must pass its grounded call; other models report a WARN. (4) `git check-ignore -q` accepts only one path, and `-v` prints negated patterns with exit code 0, so the verification script must loop per path and must not use `-v` for the "not ignored" assertion.

**Primary recommendation:** Task order is `.gitignore` first and committed, then scaffold (`requirements*.txt`, `.env.example`, README), then `config.py` + `preflight.py` with mocked pytest, then a human-action checkpoint where the user creates `.env` with real keys and runs `.venv\Scripts\python.exe preflight.py`, then a human-verify checkpoint that the email is in the Gmail inbox. Use plain `httpx` for Resend and Hunter (one HTTP stack, mockable with `respx`), not the `resend` SDK.

## Architectural Responsibility Map

This is a local CLI, not a web app, so the tiers are adapted.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Secret storage and load order | Local filesystem (`.env`, git-ignored) | Local process (`config.py`) | Secrets never leave the machine except in HTTPS auth headers. `.env` wins over stale OS env vars. |
| Secret protection (ignore rules) | Local git repo (`.gitignore`) | Test suite (`tests/test_repo_hygiene.py`) | The control is a committed file; the test proves it stays true. |
| Environment reproducibility | Local Python runtime (venv + pinned `requirements.txt`) | README | `py -3.12 -m venv .venv`, call `.venv\Scripts\python.exe` directly. |
| Service liveness proof | Local CLI process (`preflight.py`) | External APIs (Gemini, Hunter, Resend) | Each check is one HTTPS call from the CLI; the CLI decides pass, warn, fail. |
| Email delivery to inbox | External API (Resend) | User's Gmail (human verification) | Resend accepts the message; only a human can confirm inbox (not spam) placement. |
| Quota/credit reporting | External API (Hunter `/v2/account`, free call) | Local CLI (formatting) | Hunter is the source of truth for searches left; never hardcode "25". |
| Failure messaging | Local CLI (`PreflightError(service, message)`) | — | One line per failure, secrets scrubbed, no traceback. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12 via `py -3.12` | Runtime | Locked by PROJECT.md. `py -3.12` resolves to `F:\Anaconda\python.exe` (3.12.7) on this machine `[VERIFIED: py -0p]`; venv creation from it worked. |
| google-genai | 2.34.0 (2026-10-29), requires Python >=3.11 | Gemini structured + grounded calls | The supported Gemini SDK `[VERIFIED: PyPI JSON]`. Pin `<3`. |
| pydantic | 2.14.2 | Preflight schema `Ping`; `response.parsed` | Required by google-genai (`pydantic>=2.12.5,<3`) `[VERIFIED: PyPI metadata]`. |
| httpx | 0.28.1 | Hunter `/account`, Resend `/emails`; also the transport inside google-genai | Already in the google-genai tree; one stack means one mock library (`respx`) for all three services `[VERIFIED: probe]`. |
| python-dotenv | 1.2.4 | Parse `.env` (`dotenv_values`) | Standard. Use `dotenv_values(..., encoding="utf-8-sig")` merged over `os.environ`, not bare `load_dotenv()`. |
| tenacity | 9.1.4 | Retry/backoff (used from Phase 2; pinned now so it cannot drift) | **Must stay `<9.2.0`**: google-genai 2.34.0 declares `tenacity<9.2.0`; latest on PyPI is 9.2.1 `[VERIFIED: PyPI metadata]`. |
| beautifulsoup4 + lxml | 4.15.0 + 6.1.3 | Scraping (Phase 3) | Pinned in Phase 1 so the Windows wheel install risk (lxml) is burned down now. Both installed from wheels on 3.12 `[VERIFIED: pip install]`. |

### Supporting (dev only, `requirements-dev.txt`)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.2.0 | Test runner | All tests; `pytest.ini` with `testpaths = tests`, `pythonpath = .` |
| respx | 0.23.1 | Mock `httpx` (covers Hunter, Resend and the Gemini SDK's REST calls) | Preflight failure-path tests `[VERIFIED: mocked google-genai calls in scratch venv]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| plain `httpx` POST to Resend | `resend` SDK 2.50.1 (Python >=3.7, depends on `requests`) | SDK gives `InvalidApiKeyError`, `RateLimitError` etc. but adds a second HTTP stack that `respx` cannot mock. The request is one JSON POST, so plain httpx is simpler to test and has the same one-line error mapping. Revisit only if Phase 9 needs attachments or templates. |
| `dotenv_values` + merge | `load_dotenv(override=True)` | Works, but mutates `os.environ` globally and makes tests leak state. The pure-function merge is easier to unit test. |
| Gemini `client.models.generate_content` | Interactions API (`client.interactions.create`) | Google's docs now lead with Interactions, but `generate_content` is still in SDK 2.34.0 and works (verified against a mock). Phase 2 `llm.py` already plans `generate_content`; stay consistent. |

**Installation (README sequence, PowerShell from the project folder):**
```powershell
cd "E:\Sprinto Case"
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
# edit .env in an editor, save as UTF-8
.\.venv\Scripts\python.exe preflight.py
```
`requirements.txt`:
```
google-genai==2.34.0
pydantic==2.14.2
httpx==0.28.1
beautifulsoup4==4.15.0
lxml==6.1.3
python-dotenv==1.2.4
tenacity==9.1.4
```
`requirements-dev.txt`:
```
-r requirements.txt
pytest==9.2.0
respx==0.23.1
```
Success criterion 1 says "install `requirements.txt`"; `requirements-dev.txt` includes it with `-r`, so either file satisfies the sequence. Document `requirements.txt` as the runtime install and `requirements-dev.txt` as the install for running tests.

**Version verification:** versions and release dates above were read from `https://pypi.org/pypi/<pkg>/json` on 2026-11-03 (`google-genai` 2.34.0 2026-10-29, `pydantic` 2.14.2 2026-10-29, `httpx` 0.28.1 2024-12-06, `python-dotenv` 1.2.4 2026-10-01, `tenacity` latest 9.2.1 but pinned 9.1.4, `respx` 0.23.1 2026-04-08, `pytest` 9.2.0 2026-10-27, `beautifulsoup4` 4.15.0 2026-06-07, `lxml` 6.1.3 2026-09-02, `resend` 2.50.1 2026-10-29). `pip install -r requirements-dev.txt` then `pip check` reported "No broken requirements found." `[VERIFIED: PyPI JSON + local pip]`

## Package Legitimacy Audit

I ran `gsd-tools query package-legitimacy check --ecosystem pypi ...`. Every package came back **SUS**, but only for the two reasons `unknown-downloads` (PyPI's JSON API exposes no download counts, so the seam cannot measure them) and `too-new` (it keys on the latest release date, not package age). No package had `exists: false`, `deprecated: true`, or a `postinstall`. I independently checked first-release dates and source repos below; all nine are long-established packages under their official orgs. Per the protocol the SUS tag stays, so the planner should insert **one** consolidated `checkpoint:human-verify` ("review the pinned `requirements*.txt` list") before the first `pip install`, not one per package.

| Package | Registry | Age (first release) | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|---------------------|-----------|-------------|---------|-------------|
| google-genai | PyPI | 2024-12-10 (135 releases) | unknown (seam) | github.com/googleapis/python-genai | SUS (too-new, unknown-downloads) | Flagged: seam artifact. Named in Google's own docs. One consolidated human-verify. |
| pydantic | PyPI | 2017-05-03 (210 releases) | unknown | github.com/pydantic/pydantic | SUS (too-new, unknown-downloads) | Flagged: seam artifact. |
| httpx | PyPI | 2019-07-19 | unknown | github.com/encode/httpx | SUS (unknown-downloads) | Flagged: seam artifact. |
| beautifulsoup4 | PyPI | 2013-10-02 | unknown | crummy.com/software/BeautifulSoup | SUS (unknown-downloads) | Flagged: seam artifact. |
| lxml | PyPI | 2007-07-03 | unknown | github.com/lxml/lxml | SUS (unknown-downloads) | Flagged: seam artifact. |
| python-dotenv | PyPI | 2014-09-08 | unknown | github.com/theskumar/python-dotenv | SUS (unknown-downloads) | Flagged: seam artifact. |
| tenacity | PyPI | 2016-08-25 | unknown | github.com/jd/tenacity | SUS (too-new, unknown-downloads) | Flagged: seam artifact. |
| pytest | PyPI | 2010-11-25 | unknown | github.com/pytest-dev/pytest | SUS (too-new, unknown-downloads) | Flagged: seam artifact. |
| respx | PyPI | 2019-11-16 | unknown | lundberg.github.io/respx | SUS (unknown-downloads) | Flagged: seam artifact. |
| resend | PyPI | n/a, not recommended | unknown | github.com/resendlabs/resend-python | SUS | Not used (plain httpx chosen). Not in any requirements file. |

**Packages removed due to SLOP verdict:** none
**Packages flagged as suspicious (SUS):** all of the above (seam limitation, see note). Planner inserts a single `checkpoint:human-verify` before `pip install`. All package names above come from the project's own prior research (STACK.md), Google's docs and PyPI metadata; none were found only through WebSearch.

## Architecture Patterns

### System Architecture Diagram

```
 Windows shell (PowerShell, cwd = E:\Sprinto Case, path has a space)
        |
        |  .venv\Scripts\python.exe preflight.py [--no-send]
        v
 +--------------------+     reads      +-------------------+
 | preflight.main()   |--------------->| .env (git-ignored)|   .env values win over OS env
 |  utf-8 stdout      |                +-------------------+
 |  load_settings()   |  ConfigError -> "PREFLIGHT FAILED [config]: ..."  exit 1
 +---------+----------+
           | Settings (frozen, keys + TO_EMAIL + 3 model IDs, scrub list)
           v
 run(settings) -- sequential, fail-fast, each step prints one [PASS]/[WARN] line
   |
   +--1--> Hunter  GET api.hunter.io/v2/account  (X-API-KEY header, FREE call)
   |         401 -> FAIL[hunter]; 200 -> "searches left: N of M (resets D)"
   |
   +--2--> Gemini  client = genai.Client(api_key=explicit, timeout=30s)   (no SDK retries)
   |         for each DISTINCT model id (FAST, STRONG, GROUNDING deduped):
   |           structured call  -> response.parsed is Ping          (required)
   |           grounded call    -> candidates[0].grounding_metadata non-empty
   |                               required only for GEMINI_MODEL_GROUNDING, else WARN
   |         400 API_KEY_INVALID -> FAIL[gemini] key ; 404 -> FAIL[gemini] model ; 429 -> quota
   |
   +--3--> Resend  POST api.resend.com/emails  (Bearer, from onboarding@resend.dev, to [TO_EMAIL])
   |         200+id -> PASS (id printed) ; 401 -> key ; 403 "own email address" -> TO_EMAIL mismatch
   |         (skipped with --no-send)
   v
 PreflightError(service, message) --scrub secrets--> "PREFLIGHT FAILED [svc]: msg"  exit 1
 all steps ok --> "PREFLIGHT OK"  exit 0
                                         |
                                         v  (human, outside the program)
                             Gmail inbox shows the Resend test email (check Spam too)
```

### Recommended Project Structure
```
E:\Sprinto Case\
|-- .gitignore               # FIRST commit of this phase, before any .env exists
|-- .env.example             # tracked template, placeholders only; real .env is git-ignored
|-- requirements.txt         # runtime pins
|-- requirements-dev.txt     # -r requirements.txt + pytest + respx
|-- pytest.ini               # testpaths = tests ; pythonpath = .
|-- README.md                # the documented command sequence (SETUP-01)
|-- config.py                # Settings + load_settings(env_path, environ) -- pure, testable
|-- preflight.py             # PreflightError, check_*(), run(), main()
`-- tests/
    |-- test_preflight.py    # respx-mocked failure + success paths, config tests
    `-- test_repo_hygiene.py # git check-ignore + never-committed assertions
```
Keep modules flat at the root to match the architecture in SUMMARY.md (`run.py`, `llm.py`, `send.py`, ... later). Do **not** create `send.py` or `llm.py` in Phase 1; Phase 2 owns `llm.py` and Phase 9 owns the guarded `send()` with no recipient parameter. `preflight.py` is standalone now; Phase 10 can wire `run.py --preflight` to `preflight.main()`.

### Pattern 1: Pure settings loader, `.env` wins
**What:** `load_settings(env_path, environ)` merges non-empty `.env` values over a copy of the OS environment and validates required keys, placeholders and the `TO_EMAIL` shape. It never mutates `os.environ`, and the Gemini client gets `api_key=` explicitly.
**When to use:** always; this is the only place env is read.
**Why:** `load_dotenv()` defaults to `override=False`, so a stale OS `GEMINI_API_KEY` beats `.env` `[VERIFIED: probe, "override=False -> stale_from_os"]`; and the SDK prefers `GOOGLE_API_KEY` over `GEMINI_API_KEY` when both are set `[VERIFIED: google/genai/_api_client.py get_env_api_key]`.

### Pattern 2: One exception type carrying the service name
**What:** every check raises `PreflightError(service, message)`; `run()` catches it plus a catch-all `Exception`, scrubs secrets, prints one line, returns exit code 1. No traceback is ever printed.
**When to use:** all three services. A `--debug` flag that re-raises is optional.

### Pattern 3: Fail fast in cheap-to-expensive order
Hunter `/account` (free) -> Gemini calls (free-tier quota, a few requests) -> Resend send (spends 1 of 100 daily emails and creates an inbox message) last, so a bad key elsewhere never wastes a send. Offer `--no-send` for re-runs (for example a demo-network check) so repeated preflights do not burn the 100/day cap or clutter the inbox.

### Anti-Patterns to Avoid
- **Reading env in many places or calling bare `load_dotenv()`:** stale OS vars win silently.
- **Putting the Hunter key in the URL (`?api_key=`):** it ends up in logs and exception text. Use the `X-API-KEY` header (documented, accepted).
- **Treating "HTTP 200" as a passing grounded call:** a model may answer without searching; require non-empty `grounding_metadata`.
- **Letting the executor write real secrets:** creating `.env` with real keys is a human action, never an agent task.
- **Using `git check-ignore -v` to assert "not ignored":** with a negated rule it prints the rule and exits 0 `[VERIFIED: probe]`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| `.env` parsing (quotes, CRLF, BOM, comments) | regex/split parser | `dotenv_values(path, encoding="utf-8-sig")` | Probe: CRLF stripped, BOM handled `[VERIFIED: probe]`. |
| Verifying ignore rules | Parsing `.gitignore` yourself | `git check-ignore -q <path>` per path via `subprocess` | Git owns precedence and negation semantics. |
| HTTP mocking for tests | Fake classes around `httpx` | `respx` | Intercepts the Gemini SDK's own httpx traffic too `[VERIFIED: probe]`. |
| Retry/backoff | `time.sleep` loops | `tenacity` (Phase 2) | Not needed in Phase 1: preflight must fail fast, and the Gemini SDK does **not** retry by default `[VERIFIED: mock, calls made = 1]`. |
| RFC email validation | A giant email regex | One sanity regex (`^[^@\s]+@[^@\s]+\.[^@\s]+$`); Resend is the real validator | Resend returns 422/400 `validation_error` for bad addresses. |
| Email delivery | SMTP / Gmail OAuth | Resend HTTPS API | Locked decision (SUMMARY.md override). |

**Key insight:** Phase 1 is mostly glue; the value is in precise failure classification, which the mocks and live fake-key probes pin down.

## Runtime State Inventory

Not a rename/refactor/migration phase. Omitted per the template. (Greenfield: no `.gitignore`, no `.env`, no `.venv` exist yet `[VERIFIED: ls -la of E:\Sprinto Case]`.)

## Common Pitfalls

### Pitfall 1: Stale OS env var shadows `.env`
**What goes wrong:** Preflight reports an old or wrong Gemini key as valid, or a different one than the user pasted.
**Why it happens:** `load_dotenv()` default `override=False`; the SDK prefers `GOOGLE_API_KEY` over `GEMINI_API_KEY`. The shell this research ran in already had `GEMINI_API_KEY` set (value deliberately not read) `[VERIFIED: env | grep, names only]`.
**How to avoid:** `load_settings()` merges `.env` over `os.environ`; pass `api_key=settings.gemini_api_key` to `genai.Client`. Optionally warn when `GOOGLE_API_KEY` is set.
**Warning signs:** the key preflight uses differs from `.env`; the SDK logs "Both GOOGLE_API_KEY and GEMINI_API_KEY are set. Using GOOGLE_API_KEY."

### Pitfall 2: Bad Gemini key is HTTP 400, not 403
**What goes wrong:** Code maps only 401/403 to "bad key", so a wrong key prints as a vague "400 INVALID_ARGUMENT".
**Why it happens:** Google returns 400 with `status: INVALID_ARGUMENT` and `details[0].reason == "API_KEY_INVALID"`.
**How to avoid:** classify on `reason == "API_KEY_INVALID"` or message "API key not valid". Quote `[VERIFIED: live call with a fake key]`: `{"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT", "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "API_KEY_INVALID", ...}]}}`. With an invalid key AND an unknown model, the key error wins (400, not 404) `[VERIFIED: live call]`, so the key is always diagnosed first.

### Pitfall 3: Grounding is not free on Gemini 3.x (criterion 4 tension)
**What goes wrong:** The user's free-tier key passes structured calls on `gemini-3.5-flash-lite` but its grounded call fails, so a literal reading of "grounded call for each configured model" makes preflight fail even though the pipeline never grounds on that model.
**Why it happens:** Google's pricing page lists "Google Search" as "Not available" on the free tier for `gemini-3.5-flash-lite`, `gemini-3.6-flash`, `gemini-3.8-flash`, and "Free of charge, up to 500 RPD" for `gemini-2.5-flash-lite` and `gemini-2.5-flash` `[CITED: aistudio.google.com/docs/pricing]`. The google-search docs page says Gemini 3+ has "5,000 free search requests per month" (a paid-tier allowance) `[CITED: aistudio.google.com/docs/google-search]`, and forum users report "Limit 0" on Gemini 3 grounding `[CITED: discuss.ai.google.dev, community reports]`. The exact error a free key gets is unknown (likely 429 `RESOURCE_EXHAUSTED`) `[ASSUMED]`.
**How to avoid:** make a failed grounded call **required only for `GEMINI_MODEL_GROUNDING`**; for other models print `[WARN] ... (not required)`. Default `.env.example` to `GEMINI_MODEL_GROUNDING=gemini-2.5-flash-lite` (SUMMARY.md conflict #5 resolution). Record the free-vs-billing outcome in STATE.md after the first live run.

### Pitfall 4: A grounded call can "succeed" without searching
**What goes wrong:** HTTP 200 and fluent text, but `grounding_metadata` is `None`; a later phase builds on grounding that never ran.
**How to avoid:** pass only if `candidates[0].grounding_metadata` has non-empty `web_search_queries` or `grounding_chunks` (fields `[VERIFIED: SDK introspection + mock parse]`). Use a prompt that needs current facts ("most recent funding round announced by Sprinto"). Do not add retries; a failure message that says "search did not run" is the right signal.

### Pitfall 5: `.gitignore` committed after the secret, or `git add -A` before it exists
**What goes wrong:** `.env` lands in history; rotation is the only fix.
**How to avoid:** Task 1 of the phase writes and **commits** `.gitignore` while no `.env` exists (`[VERIFIED: no .gitignore or .env exist now; git log --all --name-only shows 11 tracked planning/CLAUDE files, none secret]`). The `.env` is created later by the human. A hygiene test asserts `.env` is ignored and absent from `git ls-files`.
**Pattern set (tested):** `.env`, `.env.*`, `!.env.example`, `/cache/`, `/out/`, `/contacts.csv`, `.venv/`, `__pycache__/`, `*.py[cod]`, `.pytest_cache/`. Tested: `.env`, `.env.local`, `.env.prod`, `cache/a.json`, `out/x.md`, `contacts.csv` ignored; `.env.example` and `contacts.example.csv` not ignored `[VERIFIED: throwaway repo]`.

### Pitfall 6: `git check-ignore` quirks in the verification script
**What goes wrong:** The script crashes (exit 128) or reports false results.
**Why:** `-q` is only valid with a single path (`fatal: --quiet is only valid with a single pathname`), and `-v` on `.env.example` printed `!.env.example` and exited 0 `[VERIFIED: probe]`.
**How to avoid:** loop one `git check-ignore -q <path>` per path (0 = ignored, 1 = not ignored). Pass `cache/` and `out/` with the trailing slash; works even when the dirs do not exist.

### Pitfall 7: Resend sandbox recipient rule
**What goes wrong:** 403 `validation_error`, "You can only send testing emails to your own email address (your-email-address@domain.com). To send emails to other recipients, please verify a domain at resend.com/domains" `[CITED: resend.com/docs/knowledge-base/403-error-resend-dev-domain]`.
**How to avoid:** `TO_EMAIL` must be the email the Resend account was created with. Map this 403 to a one-line fix. Whether plus-aliases (`me+x@gmail.com`) or case differences are accepted is untested `[ASSUMED: use the exact account address]`.

### Pitfall 8: Resend key states return different statuses on different endpoints
**Verified live with a fake key:** `POST /emails` -> `401 {"message":"API key is invalid","name":"validation_error","statusCode":401}`; `GET /domains` -> `400` with the same body; no key -> `401 {"message":"Missing API Key","name":"missing_api_key","statusCode":401}`. The docs list `restricted_api_key` (401, key is send-only) for non-sending endpoints `[CITED: resend.com/docs/api-reference/errors]`. Because the preflight sends an email, the send itself is the key check; no `GET /domains` probe is needed except in `--no-send` mode (optional; a 401 `restricted_api_key` there means the key is valid but send-only `[CITED]`).

### Pitfall 9: Hunter free quota number
The project assumes 25 searches a month; Hunter's pricing page shows **50 credits per month** on Free `[CITED: hunter.io/pricing]`. Domain Search "counts a new query for calls returning at least one result" and on Free `limit + offset` cannot exceed 10 `[CITED: hunter.io/api-documentation/v2]`. **Do not hardcode 25**; print `available`/`used` from `/account`. Prefer `requests.searches`, fall back to `requests.credits` (the documented example shows both; the Free plan's exact shape is unverified `[ASSUMED]`).

### Pitfall 10: Windows console and interpreter traps
`python` on this machine resolves to the Microsoft Store stub ("Python was not found; run without arguments to install from the Microsoft Store") `[VERIFIED]`. Use `py -3.12` to create the venv and `.venv\Scripts\python.exe` thereafter; activation is never needed. The default console encoding is cp1252 (`sys.stdout.encoding: cp1252`, UTF-8 mode off `[VERIFIED: probe]`), so keep preflight output ASCII and call `sys.stdout.reconfigure(encoding="utf-8")` in `main()`. A venv under `E:\Sprinto Case` (space in path) worked with `python -m pip` `[VERIFIED: scratch venv in a "sp ace" folder]`; always invoke `python -m pip`, never `pip.exe`. python-dotenv 1.2.4 parsed a UTF-8-BOM, CRLF `.env` correctly `[VERIFIED: probe]`, but still pass `encoding="utf-8-sig"`.

### Pitfall 11: Thinking tokens eat the output budget
A structured call with a tiny `max_output_tokens` can truncate mid-JSON on thinking-capable models, so `r.parsed` is `None`. Use `max_output_tokens=1024` in the preflight calls `[ASSUMED: from PITFALLS.md #16; unconfirmed live]`. Do not set temperature or thinking config (SUMMARY.md conflict #7).

### Pitfall 12: Inbox placement and Gmail threading
Mail from the shared `onboarding@resend.dev` sender may land in Spam or Promotions `[ASSUMED]`. Put a timestamp in the preflight subject so repeated test emails do not collapse into one Gmail thread (same lesson as PITFALLS.md #12). The human-verify step must say "check Inbox, then Spam".

## Code Examples

Reference implementation, **tested** in a scratch venv (Python 3.12.7, pinned requirements): 14 pytest tests pass in about 9 s, and the real-network failure paths were exercised with fake keys (Hunter 401, Gemini API_KEY_INVALID, Resend 401 validation_error all produced one-line `PREFLIGHT FAILED [...]` messages, exit code 1). The planner should treat these as the target shape, not as a literal file to paste.

### `config.py`
```python
"""Settings loader: .env wins over stale OS env vars; pure function for tests."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
SECRET_KEYS = ("GEMINI_API_KEY", "RESEND_API_KEY", "HUNTER_API_KEY")
REQUIRED = SECRET_KEYS + ("TO_EMAIL", "GEMINI_MODEL_FAST", "GEMINI_MODEL_STRONG", "GEMINI_MODEL_GROUNDING")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    resend_api_key: str
    hunter_api_key: str
    to_email: str
    from_email: str
    model_fast: str
    model_strong: str
    model_grounding: str

    @property
    def models(self) -> list[str]:  # distinct, order-preserving
        return list(dict.fromkeys([self.model_fast, self.model_strong, self.model_grounding]))

    @property
    def secrets(self) -> list[str]:
        return [self.gemini_api_key, self.resend_api_key, self.hunter_api_key]


def load_settings(env_path: Path | None = None, environ: dict | None = None) -> Settings:
    env_path = env_path or ROOT / ".env"
    if not env_path.exists():
        raise ConfigError(f"{env_path.name} not found - copy .env.example to .env and fill it in")
    file_vals = {k: (v or "").strip() for k, v in dotenv_values(env_path, encoding="utf-8-sig").items()}
    base = dict(os.environ if environ is None else environ)
    merged = {**base, **{k: v for k, v in file_vals.items() if v}}  # non-empty .env value wins over OS env
    missing = [k for k in REQUIRED if not merged.get(k, "").strip() or merged[k].lower().startswith("your_")]
    if missing:
        raise ConfigError("missing or placeholder values in .env: " + ", ".join(missing))
    if not _EMAIL.match(merged["TO_EMAIL"].strip()):
        raise ConfigError("TO_EMAIL is not a valid email address")

    def g(k: str) -> str:
        return merged[k].strip()

    return Settings(
        g("GEMINI_API_KEY"), g("RESEND_API_KEY"), g("HUNTER_API_KEY"), g("TO_EMAIL"),
        merged.get("FROM_EMAIL", "").strip() or "Sprinto Autopilot <onboarding@resend.dev>",
        g("GEMINI_MODEL_FAST"), g("GEMINI_MODEL_STRONG"), g("GEMINI_MODEL_GROUNDING"),
    )
```

### `preflight.py`
```python
"""Preflight: prove every external service works. One-line failures, no tracebacks."""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from config import ConfigError, Settings, load_settings

HUNTER_ACCOUNT = "https://api.hunter.io/v2/account"
RESEND_EMAILS = "https://api.resend.com/emails"


class PreflightError(Exception):
    def __init__(self, service: str, message: str):
        super().__init__(message)
        self.service, self.message = service, message


class Ping(BaseModel):
    ok: bool
    word: str


def _scrub(text: str, secrets: list[str]) -> str:
    for s in secrets:
        if s:
            text = text.replace(s, "***")
    return " ".join(text.split())[:200]


# ---------- Hunter ----------
def check_hunter(s: Settings) -> str:
    try:
        r = httpx.get(HUNTER_ACCOUNT, headers={"X-API-KEY": s.hunter_api_key}, timeout=15)
    except httpx.HTTPError as e:
        raise PreflightError("hunter", f"network error: {type(e).__name__}") from e
    if r.status_code == 401:
        raise PreflightError("hunter", "HUNTER_API_KEY rejected (401 authentication_failed)")
    if r.status_code != 200:
        raise PreflightError("hunter", f"/account returned HTTP {r.status_code}")
    try:
        d = r.json()["data"]
        reqs = d["requests"]
        q = reqs.get("searches") or reqs["credits"]  # Free plan may expose only credits (unverified)
        used, avail = int(q["used"]), int(q["available"])
        left = int(q.get("remaining", avail - used))
    except (KeyError, TypeError, ValueError) as e:
        raise PreflightError("hunter", "unexpected /account response shape") from e
    return f"plan={d.get('plan_name', '?')} searches left: {left} of {avail} (resets {d.get('reset_date', '?')})"


# ---------- Gemini ----------
def _gemini_message(model: str, step: str, e: Exception) -> str:
    if isinstance(e, errors.APIError):
        reason = ""
        try:
            reason = e.details["error"]["details"][0].get("reason", "")
        except Exception:
            pass
        msg = e.message or ""
        if reason == "API_KEY_INVALID" or "API key not valid" in msg:
            return "GEMINI_API_KEY rejected (API_KEY_INVALID)"
        if e.code == 404:
            return f"model '{model}' not found - fix GEMINI_MODEL_* in .env"
        if e.code == 429:
            return f"model '{model}' {step}: quota/rate limit hit (429 {e.status})"
        return f"model '{model}' {step}: {e.code} {e.status} {msg[:80]}"
    if isinstance(e, httpx.HTTPError):
        return f"network error: {type(e).__name__}"
    return f"model '{model}' {step}: {type(e).__name__}: {str(e)[:80]}"


def check_gemini_structured(client, model: str) -> str:
    try:
        r = client.models.generate_content(
            model=model,
            contents='Return ok=true and word="pong".',
            config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=Ping, max_output_tokens=1024),
        )
    except Exception as e:
        raise PreflightError("gemini", _gemini_message(model, "structured", e)) from e
    if not isinstance(r.parsed, Ping):
        raise PreflightError("gemini", f"model '{model}' structured: reply did not match schema")
    return "structured OK"


def check_gemini_grounded(client, model: str) -> str:
    try:
        r = client.models.generate_content(
            model=model,
            contents="Use Google Search: what is the most recent funding round announced by Sprinto (sprinto.com)? One sentence.",
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())], max_output_tokens=1024),
        )
    except Exception as e:
        raise PreflightError("gemini", _gemini_message(model, "grounded", e)) from e
    gm = r.candidates[0].grounding_metadata if r.candidates else None
    if gm is None or not (gm.web_search_queries or gm.grounding_chunks):
        raise PreflightError("gemini", f"model '{model}' grounded: call succeeded but no grounding_metadata (search did not run)")
    return f"grounded OK ({len(gm.web_search_queries or [])} queries, {len(gm.grounding_chunks or [])} sources)"


# ---------- Resend ----------
def check_resend(s: Settings) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    payload = {
        "from": s.from_email,
        "to": [s.to_email],
        "subject": f"Sprinto Autopilot preflight {stamp}",
        "text": "Preflight OK. If you can read this in your inbox, Resend delivery works.",
    }
    try:
        r = httpx.post(RESEND_EMAILS, json=payload, timeout=20,
                       headers={"Authorization": f"Bearer {s.resend_api_key}"})
    except httpx.HTTPError as e:
        raise PreflightError("resend", f"network error: {type(e).__name__}") from e
    try:
        body = r.json()
    except ValueError:
        body = {}
    name, msg = body.get("name", ""), body.get("message", "")
    if r.is_success and body.get("id"):
        return f"sent to {s.to_email} (id {body['id']}) - now check Inbox/Spam"
    if name == "missing_api_key" or (r.status_code in (400, 401) and name == "validation_error" and "API key" in msg):
        raise PreflightError("resend", f"RESEND_API_KEY rejected ({r.status_code} {name})")
    if r.status_code == 403 and "own email address" in msg:
        raise PreflightError("resend", "TO_EMAIL must equal your Resend account email when sending from onboarding@resend.dev")
    if r.status_code == 403 and "not verified" in msg:
        raise PreflightError("resend", "FROM_EMAIL domain is not verified in Resend")
    if r.status_code == 429:
        raise PreflightError("resend", f"rate/quota limit ({name or 429})")
    raise PreflightError("resend", f"HTTP {r.status_code} {name}: {msg[:100]}")


# ---------- orchestration ----------
def run(s: Settings, out=print, send: bool = True) -> int:
    def step(label, fn, *a, required=True):
        t0 = time.monotonic()
        try:
            res = fn(*a)
        except PreflightError as e:
            if required:
                raise
            out(f"[WARN] {label:<34} {_scrub(e.message, s.secrets)} (not required)")
            return
        out(f"[PASS] {label:<34} {res} ({time.monotonic() - t0:.1f}s)")

    try:
        step("hunter /account", check_hunter, s)
        client = genai.Client(api_key=s.gemini_api_key, http_options=types.HttpOptions(timeout=30_000))  # ms
        for m in s.models:
            step(f"gemini {m} structured", check_gemini_structured, client, m)
            step(f"gemini {m} grounded", check_gemini_grounded, client, m,
                 required=(m == s.model_grounding))   # only the grounding model MUST ground
        if send:
            step("resend send-to-self", check_resend, s)
    except PreflightError as e:
        out(f"PREFLIGHT FAILED [{e.service}]: {_scrub(e.message, s.secrets)}")
        return 1
    except Exception as e:  # never a traceback
        out(f"PREFLIGHT FAILED [internal]: {type(e).__name__}: {_scrub(str(e), s.secrets)}")
        return 1
    out("PREFLIGHT OK")
    return 0


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-send", action="store_true")
    args = ap.parse_args(argv)
    try:
        s = load_settings()
    except ConfigError as e:
        print(f"PREFLIGHT FAILED [config]: {e}")
        return 1
    return run(s, send=not args.no_send)


if __name__ == "__main__":
    raise SystemExit(main())
```
Suggested additions the reference omits (planner's discretion): a `--env-file PATH` option so the failure paths can be exercised against a throwaway `.env` with bad keys; a hint on 429 grounded failures ("grounding may need billing; use gemini-2.5-flash-lite on the free tier"); a best-effort `GET /emails/{id}` after the send to print `last_event` (documented example value `"delivered"`; do not fail on it `[CITED: resend.com/docs/api-reference/emails/retrieve-email]`); and a "grounded OK on <model>" summary line the executor copies into STATE.md as the recorded free-vs-billing decision.

### Gemini: verified call shapes (mocked REST, SDK 2.34.0)
```python
client = genai.Client(api_key=KEY, http_options=types.HttpOptions(timeout=30_000))   # timeout is milliseconds
r = client.models.generate_content(model=MODEL, contents="...", config=types.GenerateContentConfig(
        response_mime_type="application/json", response_schema=Ping, max_output_tokens=1024))
r.parsed            # -> Ping(ok=True, word='pong')  [VERIFIED: mock]
r.model_version     # recorded per call later (TRCE-01)
g = client.models.generate_content(model=MODEL, contents="...", config=types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())]))      # request body: {'googleSearch': {}}
gm = g.candidates[0].grounding_metadata   # None if no search ran
gm.web_search_queries                     # ['sprinto funding']
gm.grounding_chunks[0].web.{uri,title,domain}
```
Error classes `[VERIFIED: google/genai/errors.py + probes]`: `errors.APIError` (attrs `code`, `status`, `message`, `details`); `ClientError` for 4xx, `ServerError` for 5xx. The API key travels in the `x-goog-api-key` header, not the URL `[VERIFIED: mock]`.

### Repo hygiene test (shape, `tests/test_repo_hygiene.py`)
```python
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)

def test_secret_and_runtime_paths_are_ignored():
    for p in (".env", "cache/", "out/", "contacts.csv"):
        assert _git("check-ignore", "-q", p).returncode == 0, p      # one path per call: -q allows only one

def test_template_is_not_ignored():
    assert _git("check-ignore", "-q", ".env.example").returncode == 1

def test_no_secret_file_is_tracked_or_ever_committed():
    tracked = _git("ls-files").stdout.split()
    assert ".env" not in tracked and "contacts.csv" not in tracked
    history = _git("log", "--all", "--name-only", "--format=").stdout.split()
    assert ".env" not in history and "contacts.csv" not in history
```
(Shape verified for `check-ignore`; run it from the repo root. The "ordering" claim in criterion 2 reduces to: `.gitignore` is committed and `.env` never appears in history.)

### `.gitignore` (tested pattern set)
```
# secrets
.env
.env.*
!.env.example
# runtime artifacts
/cache/
/out/
# real contact data (commit contacts.example.csv instead)
/contacts.csv
# python / tooling
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
```

### `.env.example` (placeholders only, never real values)
```
GEMINI_API_KEY=your_gemini_api_key_here
RESEND_API_KEY=your_resend_api_key_here
HUNTER_API_KEY=your_hunter_api_key_here
# Must equal the email your Resend account was created with (onboarding@resend.dev sandbox rule)
TO_EMAIL=your_email_here@gmail.com
# Optional: sender (default Sprinto Autopilot <onboarding@resend.dev>)
# FROM_EMAIL=Sprinto Autopilot <onboarding@resend.dev>
# Model IDs: do not use gemini-flash-latest or gemini-2.5-flash (shuts down 2026-12-01)
GEMINI_MODEL_FAST=gemini-3.5-flash-lite
GEMINI_MODEL_STRONG=gemini-3.5-flash-lite
# Free tier: gemini-2.5-flash-lite is the only family with free Google Search grounding (500 RPD)
GEMINI_MODEL_GROUNDING=gemini-2.5-flash-lite
```
The variable names come straight from the requirements and summary: SETUP-01 lists "`GEMINI_API_KEY`, `RESEND_API_KEY`, `HUNTER_API_KEY`, `TO_EMAIL`, Gemini model IDs" and SUMMARY.md says "`GEMINI_MODEL_FAST`, `GEMINI_MODEL_STRONG`, `GEMINI_MODEL_GROUNDING`. Do not hardcode them" `[VERIFIED: REQUIREMENTS.md:10, SUMMARY.md:69]`. Model-ID statuses `[CITED: aistudio.google.com/docs/models, fetched this session]`: `gemini-3.5-flash-lite` and `gemini-3.6-flash` Stable, `gemini-3.8-flash` new, `gemini-2.5-flash-lite` "Not deprecated... until further notice", `gemini-2.5-flash` deprecated with routing to `gemini-3.5-flash-lite` from 2026-12-01.

### Service facts (for the Phase 1 code and for later phases)

**Resend** `[CITED: resend.com/docs/api-reference/emails/send-email, /errors, /rate-limit, /pricing]`
- `POST https://api.resend.com/emails`, `Authorization: Bearer re_...`, `Content-Type: application/json`.
- Body: `from` (required, display name allowed), `to` (string or list, up to 50), `subject`, `text` and/or `html` (omit `text` and it is generated from `html`), optional `reply_to`, `headers`, `cc`, `bcc`, `tags`. Success body: `{"id": "49a3999c-0ce1-4ea6-ab68-afcd6dc2e794"}`. The HTTP success status code is not stated on the page; the reference code uses `r.is_success`.
- Errors body shape (live) `{"message": ..., "name": ..., "statusCode": ...}`. 401 `missing_api_key`; 401/400 `validation_error` "API key is invalid"; 401 `restricted_api_key` (send-only key on a non-send endpoint); 403 `validation_error` testing-domain restriction or "domain is not verified"; 422 `missing_required_field` / `invalid_parameter`; 429 `rate_limit_exceeded`, `daily_quota_exceeded`, `monthly_quota_exceeded`; 500 `application_error`; 503 `service_unavailable`.
- Limits: default 10 requests per second per team; free plan 100 emails/day (resets midnight UTC, sent and received both count) and 3,000/month; 3 domains. Headers `ratelimit-*`, `retry-after`, and (free plan) `x-resend-daily-quota`. `Idempotency-Key` header supported (valid 24 h); do not use it on the preflight send, or a repeat within 24 h with the same key would not send.
- `onboarding@resend.dev` can only deliver to the address tied to your Resend account. Sandbox restriction message quoted in Pitfall 7.
- API key permission: `full_access` or `sending_access`; a send-only key is enough for this project.

**Hunter** `[CITED: hunter.io/api-documentation/v2; VERIFIED live for the 401 shape]`
- `GET https://api.hunter.io/v2/account`; auth by `api_key` query param, `X-API-KEY` header or `Authorization: Bearer`. The docs say "This call is free." Response (documented example): `data.plan_name`, `data.plan_level`, `data.reset_date`, `data.requests.credits|searches|verifications` each with `used`, `available`, `remaining`, plus `data.calls`.
- Bad key (live): HTTP 401 `{"errors":[{"id":"authentication_failed","code":401,"details":"No user found for the API key supplied"}]}`. Same for the header form and for `/domain-search`.
- Error codes: 400 bad param, 401 no valid key, 403 rate limit reached, 404, 422, 429 usage limit reached, 451, 5xx. Rate limit: 15 requests/s, 500/min (Domain Search).
- Domain Search (Phase 7 reference): `GET /v2/domain-search?domain=...&seniority=senior,executive&limit=...`; `seniority` values `junior|senior|executive`; `type` `personal|generic`; `department` list; `required_field` `full_name|position|phone_number`; `limit` default 10, max 100, but on Free `limit + offset` must not exceed 10 (else `pagination_error`). Each `data.emails[]` item has `value`, `confidence`, `first_name`, `last_name`, `position`, `seniority`, `department`, `linkedin`, `verification`; `meta.results` is the count.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `google-generativeai` / `GenerativeModel` | `google-genai` 2.x (`from google import genai`) | 2025 (0.8.6 last release 2025-12-16, per STACK.md) | Most online snippets are stale. |
| Gemini docs show `generateContent` examples | Docs now lead with the Interactions API (`client.interactions.create`) | 2026 `[CITED: aistudio.google.com/docs/google-search, /structured-output]` | `generate_content` still ships in SDK 2.34.0 and works; stay on it for stability. |
| `google_search_retrieval` tool | `types.Tool(google_search=types.GoogleSearch())` | Gemini 2+ | Verified request body is `{'googleSearch': {}}`. |
| `gemini-2.5-flash` default | `gemini-3.5-flash-lite` (and 3.6/3.8 flash) | `gemini-2.5-flash` routes to `gemini-3.5-flash-lite` on 2026-12-01 | Do not default to deprecated IDs. |
| Gmail API OAuth sending | Resend HTTPS API | Project decision 2026-11-03 | No OAuth, no Cloud Console. |

**Deprecated/outdated:** `gemini-2.0-flash`, `gemini-2.0-flash-lite`, `gemini-3-pro-preview`, `gemini-3.1-flash-lite-preview` are shut down `[CITED: aistudio.google.com/docs/models]`; `tenacity` 9.2.x conflicts with google-genai 2.34.0.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | An unknown Gemini model ID returns HTTP 404 `NOT_FOUND` (SDK maps 4xx to `ClientError`; the 404 mapping was verified only against a mock) | Pitfall 2, code | A different status prints a generic one-liner instead of "model not found". Low: the generic branch still names model and step. |
| A2 | A free-tier key calling grounding on Gemini 3.x fails with 429 `RESOURCE_EXHAUSTED` (limit 0) | Pitfall 3 | The failure message wording differs; the WARN/FAIL logic is status-agnostic, so low. |
| A3 | Hunter Free-plan `/account` exposes `requests.searches` (else `requests.credits`) | Pitfall 9 | Preflight prints "unexpected /account response shape". Medium: needs the live run; the reference falls back to `credits`. |
| A4 | Resend returns 2xx (200) with `{"id"}` on success; plus-aliases/case variants of `TO_EMAIL` may be rejected | Pitfall 7 | Using the exact account address avoids it. |
| A5 | `max_output_tokens=1024` is enough for the structured preflight call on thinking-capable models | Pitfall 11 | `r.parsed` is `None`; raise the cap. |
| A6 | Mail from `onboarding@resend.dev` reaches the Gmail Inbox (not Spam) | Pitfall 12 | The human-verify step catches this; tell the user to check Spam and mark "Not spam". |
| A7 | `py -3.12` pointing at Anaconda's Python 3.12.7 builds a venv that behaves like a stock one | Environment | Verified working here (install + imports + pytest), so low. |
| A8 | The three configured Gemini models fit free-tier RPM during preflight (about 4 to 6 calls) | Validation | A 429 on the structured call; wait a minute and rerun. Free-tier RPM numbers are third-party (STACK.md) `[LOW]`. |

## Open Questions

1. **Does criterion 4 require a passing grounded call for every configured model, or only the grounding model?**
   - What we know: free-tier Gemini 3.x has no grounding per Google's pricing page; the pipeline only grounds via `GEMINI_MODEL_GROUNDING`.
   - What's unclear: the user's intent behind "each configured Gemini model".
   - Recommendation: required only for `GEMINI_MODEL_GROUNDING`, WARN for others (implemented in the reference). If the user wants strict literal behaviour, set all three env vars to a model that supports grounding on their tier, or enable billing.

2. **Is the Gemini key on the free tier or billing-enabled?**
   - What we know: cannot be read from the API; the grounded-call result on `gemini-3.5-flash-lite` reveals it. I did not use the ambient `GEMINI_API_KEY` for live generation calls (credential not handed over for this research).
   - Recommendation: run the live preflight first thing, record the outcome in STATE.md, and pick defaults accordingly.

3. **Does `TO_EMAIL` equal the email the Resend account was created with?**
   - Recommendation: a `checkpoint:human-action` where the user confirms before the send; the 403 mapping gives a one-line fix if not.

4. **Hunter free allowance: 25 or 50 per month?** The pricing page says 50 credits, the project says 25 searches. Recommendation: report whatever `/account` returns; update PROJECT.md only after seeing the real number.

5. **Preflight invocation:** standalone `preflight.py` now (assumed) vs `run.py --preflight`. Recommendation: standalone; Phase 10 wires `run.py` to it.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 via `py -3.12` | venv (SETUP-01) | ✓ | 3.12.7 (`F:\Anaconda\python.exe`) | — |
| Python 3.14 (py default) | not used | ✓ | 3.14.7 | Never use; wheel risk |
| `python` on PATH | — | ✗ (Microsoft Store stub) | — | Use `py -3.12` / `.venv\Scripts\python.exe` |
| git | SETUP-02 | ✓ | 2.56.0.windows.4; repo at `E:\Sprinto Case`, branch `master`, 8 commits, clean | — |
| Network to PyPI | install | ✓ | pip resolved all pins | — |
| `generativelanguage.googleapis.com`, `api.hunter.io`, `api.resend.com` reachable | preflight | ✓ (HTTP responses received from all three) | — | Phone hotspot (PITFALLS.md #20) |
| Real API keys (Gemini, Resend, Hunter) | SETUP-03 live run | unknown (not read, by design) | — | Human action; mocked tests cover everything else |
| Gmail inbox access | SC3 | user | — | Check Spam; manual |
| `PYTHONUTF8` | console | ✗ unset; console is cp1252 | — | `sys.stdout.reconfigure(encoding="utf-8")` + ASCII output |
| Ambient `GEMINI_API_KEY` OS env var | — | present in the research shell (value not read) | — | `.env`-wins loader (Pattern 1) |

**Missing dependencies with no fallback:** none. Real API keys are a human prerequisite for the live gate only.
**Missing dependencies with fallback:** the `python` command (use the launcher).

Scratch artefacts: this research created a throwaway venv and files under `C:\Users\ROG\gsdprobe\` (outside the project). Safe to delete; the project directory was not modified.

## Validation Architecture

Nyquist validation is enabled (`workflow.nyquist_validation: true` in `.planning/config.json`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.2.0 + respx 0.23.1 (Python 3.12.7) |
| Config file | none yet, Wave 0 creates `pytest.ini` (`testpaths = tests`, `pythonpath = .`) |
| Quick run command | `.\.venv\Scripts\python.exe -m pytest -q` (about 9 s for 14 tests in the scratch run) |
| Full suite command | same, plus the live gate below |

### Phase Requirements -> Test Map
| Req / Criterion | Behavior | Test Type | Automated Command | File Exists? |
|-----------------|----------|-----------|-------------------|-------------|
| SETUP-01 / SC1 | `.env.example` lists the 4 keys and 3 model IDs; `requirements.txt` pins installable; README has the sequence | unit (static) | `.\.venv\Scripts\python.exe -m pytest tests/test_setup_files.py -q` (parse `.env.example` with `dotenv_values`, assert keys present) | ❌ Wave 0 |
| SETUP-01 / SC1 | Documented sequence yields a working env | integration, run once at the phase gate | `py -3.12 -m venv .venv` then `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` then `.\.venv\Scripts\python.exe -m pip check` and `.\.venv\Scripts\python.exe -c "import google.genai, httpx, pydantic, dotenv, bs4, lxml, tenacity"` | n/a (command) |
| SETUP-02 / SC2 | `.env`, `cache/`, `out/`, `contacts.csv` ignored; `.env.example` not ignored; `.env` never tracked or in history | unit | `.\.venv\Scripts\python.exe -m pytest tests/test_repo_hygiene.py -q` | ❌ Wave 0 |
| SETUP-02 / SC2 | `.gitignore` committed before any `.env` existed | manual/git | `git log --diff-filter=A --format=%h -- .gitignore` returns a commit, and the hygiene test asserts no `.env` in history | ❌ Wave 0 |
| SETUP-03 / SC3 | Resend accepts the send to `TO_EMAIL` (200 + id) | live | `.\.venv\Scripts\python.exe preflight.py` shows `[PASS] resend send-to-self` | ❌ Wave 0 |
| SETUP-03 / SC3 | Email visible in the user's Gmail inbox | **manual** (human-verify, `human_verify_mode: end-of-phase`) | User opens Gmail, finds subject "Sprinto Autopilot preflight <timestamp>", checks Inbox then Spam | n/a |
| SETUP-03 / SC4 | Structured + grounded pass per model, Hunter searches left shown | live | `.\.venv\Scripts\python.exe preflight.py --no-send` shows `[PASS] gemini <m> structured`, `[PASS] gemini <grounding-model> grounded`, `[PASS] hunter /account ... searches left: N` | ❌ Wave 0 |
| SETUP-03 / SC4 | Dedupe of identical model IDs, grounded WARN for non-grounding models, happy path | unit (mocked) | `.\.venv\Scripts\python.exe -m pytest tests/test_preflight.py -q -k "all_pass or non_grounding or deduped"` | ❌ Wave 0 |
| SETUP-03 / SC5 | Wrong key or unknown model: one-line `PREFLIGHT FAILED [service]: ...`, no traceback, exit 1 | unit (mocked) | `.\.venv\Scripts\python.exe -m pytest tests/test_preflight.py -q -k "bad_ or unknown_model or network_error or sandbox"` | ❌ Wave 0 |
| SETUP-03 / SC5 | Same against the real services | live, with throwaway fake-key env | run the CLI with an env file holding fake keys (needs `--env-file`): expected `PREFLIGHT FAILED [hunter]: HUNTER_API_KEY rejected (401 authentication_failed)`. I confirmed all three real fake-key messages this session. | ❌ Wave 0 |
| (cross-cut) | `.env` beats stale OS env; BOM/CRLF handled; placeholders rejected | unit | `pytest tests/test_preflight.py -k config` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `.\.venv\Scripts\python.exe -m pytest -q`
- **Per wave merge:** the same, plus a hygiene re-run
- **Phase gate:** full pytest green, then live `preflight.py` (with send), then the human inbox check, then `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `pytest.ini`, `requirements-dev.txt`, `tests/` (framework install: `pip install -r requirements-dev.txt`)
- [ ] `tests/test_preflight.py` (covers SC3 to SC5 logic; reference version passes 14 tests)
- [ ] `tests/test_repo_hygiene.py` (SC2)
- [ ] `tests/test_setup_files.py` (SC1 static checks)
- [ ] The commit of `.gitignore` **before** any of the above (ordering is itself a requirement)

## Security Domain

`security_enforcement` is enabled (`security_asvs_level: 1`, `security_block_on: high` in config).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (no user auth; only outbound API-key use) | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes (config values) | `ConfigError` on missing/placeholder keys; `TO_EMAIL` sanity regex; Resend validates addresses server-side |
| V6 Cryptography | no (TLS only) | httpx default certificate verification; never set `verify=False` |
| V7 Error Handling & Logging | yes | `PreflightError` + `_scrub()` masks the three secret values; no traceback output |
| V8 Data Protection | yes | `.env` git-ignored; keys sent only in `Authorization`/`X-API-KEY`/`x-goog-api-key` headers (SDK verified: key not in URL) |
| V14 Configuration | yes | pinned dependencies, `.env.example` with placeholders only, hygiene test |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret committed to git (`git add -A` after `.env` exists) | Information Disclosure | `.gitignore` committed first; hygiene test; rotate keys if it ever happens |
| API key leaked via logs/exception text | Information Disclosure | keys in headers not URLs; `_scrub()` on every printed message; never print env values |
| Agent or script writes real secrets into tracked files | Information Disclosure | `.env` is created only by the human; `.env.example` holds placeholders; tests reject placeholders in `.env` |
| Preflight emails the wrong recipient | Tampering/Spoofing | `to` is `[settings.to_email]` only; there is no other recipient input (Phase 9 formalises the guarded `send()` with no recipient parameter, SEND-01) |
| Dependency confusion / typosquat | Tampering | exact pins, one consolidated human review of `requirements*.txt` before first install (seam flagged all SUS) |
| Stale or foreign OS env var supplies the wrong key | Spoofing | `.env`-wins merge; explicit `api_key=` to the SDK |

## Sources

### Primary (HIGH confidence)
- Local probes this session (Python 3.12.7 scratch venv): `pip install` + `pip check`; `google/genai/errors.py` and `_api_client.py` source; SDK type introspection (`GroundingMetadata`, `GroundingChunkWeb`, `Candidate`, `HttpOptions`, `ListModelsConfig`); respx-mocked `generate_content` (structured, grounded, ungrounded, 404/429/403/503, retry count); python-dotenv BOM/CRLF/override behaviour; throwaway-repo `.gitignore` and `git check-ignore` tests; 14-test pytest run.
- Live fake-key calls: `generativelanguage.googleapis.com` (400 `API_KEY_INVALID`), `api.hunter.io/v2/account` and `/domain-search` (401 `authentication_failed`), `api.resend.com/emails` and `/domains` (401/400 `validation_error`, 401 `missing_api_key`).
- PyPI JSON for all package versions, release dates, `requires_python`, `requires_dist`.
- `E:\Sprinto Case` files read this session: REQUIREMENTS.md, STATE.md, PROJECT.md, `.claude/CLAUDE.md`, research SUMMARY.md, STACK.md, PITFALLS.md, `.planning/config.json`.

### Secondary (MEDIUM confidence, official docs fetched this session)
- https://resend.com/docs/api-reference/emails/send-email, /errors, /rate-limit, /pricing, /api-reference/domains/list-domains, /api-reference/emails/retrieve-email, /api-reference/api-keys/create-api-key, /docs/send-with-python, /docs/knowledge-base/403-error-resend-dev-domain
- https://hunter.io/api-documentation/v2 (Account, Domain Search, errors, rate limits), https://hunter.io/pricing
- https://aistudio.google.com/docs/models, /pricing, /google-search, /structured-output, /rate-limits

### Tertiary (LOW confidence)
- discuss.ai.google.dev community threads on Gemini 3 grounding quotas ("Limit 0"); third-party free-tier RPM/RPD numbers carried from STACK.md.
- Training knowledge for the unknown-model 404 and Gmail Spam placement (A1, A6).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, installed and `pip check`ed with the exact pins.
- Architecture: HIGH, small and probed; the reference passes 14 tests.
- Error shapes: HIGH for Gemini bad-key, Hunter 401, Resend 401/400/missing-key (live); MEDIUM for the 403 sandbox, 404 model and Hunter Free `/account` shape (docs or mocks only).
- Gemini free-tier grounding: MEDIUM-LOW, docs conflict; the live preflight is the arbiter.
- Pitfalls: HIGH for Windows/git/env items (verified), MEDIUM for inbox placement.

**Research date:** 2026-11-03
**Valid until:** about 7 days for Gemini model IDs and free-tier grounding (fast-moving; Google ships model changes monthly and `gemini-2.5-flash` shuts down 2026-12-01); 30 days for everything else.
