# Sprinto Outbound Autopilot

Give it a list of domains. Without any decisions from you, it scrapes each site, extracts evidence, qualifies the company against Sprinto's ICP (with an agent loop when data is thin), picks the right decision-maker via Hunter.io, works out two pain points, drafts a personalised email and sends it **to your own inbox** via Resend. Every decision is written to `out/<domain>/report.md` with cited evidence.

## Setup (Windows, PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }   # then fill in your real keys
.\.venv\Scripts\python.exe preflight.py          # checks Hunter, Gemini (structured + grounded), sends a test email
.\.venv\Scripts\python.exe -m pytest -q          # 47 offline tests
```

`.env` keys:
- `GEMINI_API_KEY`, `RESEND_API_KEY`, `HUNTER_API_KEY`.
- `TO_EMAIL`: must equal your Resend account email when sending from `onboarding@resend.dev`.
- `GEMINI_MODEL_FAST`, `GEMINI_MODEL_STRONG`, `GEMINI_MODEL_GROUNDING`.
- Optional: `SENDER_NAME`, `FROM_EMAIL`, `GEMINI_MIN_INTERVAL`. The last is the pacing interval: 6.5 s on the free tier, 0 with billing.

## Run

```powershell
.\.venv\Scripts\python.exe run.py domains.txt              # all domains
.\.venv\Scripts\python.exe run.py domains.txt --only bolna.ai
.\.venv\Scripts\python.exe run.py domains.txt --force      # ignore caches (spends Hunter + Gemini quota)
```

Outputs:
- `out/summary.md`: one row per domain.
- `out/<domain>/report.md`: why this company, why this person, why this email, plus an "Open in Gmail" fallback link to yourself.
- `out/<domain>/trace.json`: every step, the evidence ledger, and each model call.

Every company ends with one status: `sent`, `not_qualified`, `insufficient_data`, `no_contact` or `failed`.

## How decisions are made

| Step | Module | Decision logic |
|---|---|---|
| 1 Scrape | `pipeline/scrape.py` | Fetches `/`, `/pricing`, `/security`, `/trust`, `/customers`, `/about` and `/careers`, each with a typed outcome. A blocked page counts as *unknown*, never *absent*. Soft-404s are detected by hash. |
| 2 Extract | `pipeline/extract.py` | Gemini returns facts, each with a verbatim quote. A quote counts as verified only if it actually appears on the page. |
| 3 Qualify | `pipeline/qualify.py` + `config/icp.yaml` | A researched 100-point rubric: firmographic 30, upmarket pull 25, compliance trigger 35, fit 10. **Python computes the score.** Points count only with cited evidence. Hard disqualifiers: not software, already a Sprinto customer, over 2,000 staff, too small. Caps apply for no enterprise pull and for already fully certified. |
| 3 Agent loop | `pipeline/agent.py`, `pipeline/tools.py` | While the 60-point bar sits inside the score bounds, it picks `fetch_page`, `web_research` (Google Search grounding) or `job_postings` (Greenhouse, Lever, Ashby). Limits: 4 tool calls, 2 searches, no repeats, 120 s. |
| 4 PoC | `pipeline/contacts.py` | Hunter domain search, **only for qualified companies**, cached. Role rules: up to 50 staff, the founder/CEO; 51–200, a security/GRC lead, else the CTO; over 200, a security/GRC lead. Sales, marketing and HR titles are dropped. An optional `contacts.csv` overrides Hunter. |
| 5 Pains | `pipeline/compose.py` | Two pain points for that persona, each citing evidence. A SOC 2-only company gets an ISO 27001/GDPR expansion angle. |
| 6 Draft | `pipeline/compose.py` | One hook picked from verified evidence. Python enforces: at most 110 words, one question, no unbacked numbers, no banned phrases, proof lines only from `sprinto_facts.md`. One regeneration if the checks fail. |
| 7 Send | `pipeline/send.py` | Resend. `send_email()` has **no recipient parameter**, so it always sends to `TO_EMAIL`. The intended prospect appears in a footer. |

Planning, research and requirements are in `.planning/`.
