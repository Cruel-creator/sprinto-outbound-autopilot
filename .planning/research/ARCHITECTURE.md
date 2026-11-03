# Architecture Research

**Domain:** AI-driven B2B cold-outreach pipeline (Python CLI, Gemini, Gmail API) for Sprinto
**Researched:** 2026-11-03
**Confidence:** MEDIUM-HIGH. Structure and patterns are HIGH (standard pipeline + bounded agent loop). Gemini tool-combination status is MEDIUM (Preview, model-dependent, verified from Google docs via search only). Exact model IDs and free-tier rate limits are unverified; read them from AI Studio on the day.

## Opinionated Summary (read this first)

1. **One linear pipeline of typed steps, one agent loop inside Step 3 only.** Everything else is a single LLM call. Do not make the whole pipeline "agentic".
2. **Gather, then judge.** The agent loop only *gathers evidence* into an append-only evidence ledger. Scoring is a separate structured call plus deterministic Python arithmetic against `config/icp.yaml`. The LLM never computes the score.
3. **Use a JSON "controller" loop (model returns the next action as a schema-validated object), not native function calling.** Reasons in section 3. The tool registry is shaped so it could be swapped to native function calling later.
4. **`web_search` is a separate grounded `generate_content` call wrapped as a Python tool.** It returns prose plus grounding URLs that enter the ledger as evidence. This works on every Gemini model, so you never depend on the Preview tool-combination feature.
5. **Every claim downstream cites an evidence ID (E1, E2...).** `report.md` is rendered from the trace with zero LLM calls. This is what makes each decision defensible.
6. **The recipient name, email and the `to:` address never come from the LLM.** They come from `contacts.csv` and `.env`. The LLM only writes prose.
7. **Build a walking skeleton first**: 1 domain, every step crude, email in the inbox by roughly minute 35. Then deepen in the order in section 6.

## Standard Architecture

### System Overview

```
                         run.py  (CLI: reads domains.txt, loops, writes batch summary)
                            │  one domain at a time, try/except per domain
                            ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ ORCHESTRATION        pipeline/orchestrator.py :: process_domain(domain, ctx) │
│   wires steps, passes typed models, checkpoints trace after EVERY step       │
└───┬──────────────────────────────────────────────────────────────────────────┘
    │ calls, in order
    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ STEPS (pure-ish functions:  (input_model, ctx) -> output_model)              │
│                                                                              │
│  1 scrape ─► 2 extract ─► 3 qualify ──────────► 4 contacts ─► 5 pains        │
│  RawSite     CompanyProfile   │ ▲                 ContactChoice   PainPoints │
│                               │ │ evidence                           │       │
│                               ▼ │                                    ▼       │
│                          ┌──────────┐                         6 draft ─► 7 send
│                          │ agent.py │ loop (max N)            EmailDraft  SendResult
│                          └────┬─────┘                                        │
│                               │ calls                                        │
│                       ┌───────┴────────────────┐                             │
│                       │ tools.py                │                            │
│                       │ fetch_page / web_search │                            │
│                       │ / job_postings          │                            │
│                       └───────┬────────────────┘                             │
└───────────────────────────────┼──────────────────────────────────────────────┘
                                │ only these modules touch the outside world
    ┌───────────────┬───────────┴─────────┬─────────────────┬──────────────────┐
    ▼               ▼                     ▼                 ▼                  ▼
 http.py/scrape  llm.py                 send.py          contacts.csv     config/icp.yaml
 (httpx + bs4,   (google-genai wrapper: (Gmail API,       (read-only)     prompts/*.md
  disk cache)    retry, disk cache,      OAuth)                           (read-only)
                 call logging)
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ CROSS-CUTTING:  trace.py (append-only per-company trace, flushed each step)  │
│                 evidence ledger (id -> source_url, quote, verified flag)     │
│                 report.py (trace -> report.md, no LLM)                       │
└──────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
         out/<run_id>/<domain>/{trace.json, report.md}     out/<run_id>/summary.md
         cache/pages/*.json     cache/llm/*.json
```

### Component Responsibilities

| Component | Responsibility | Talks to | Must NOT |
|-----------|----------------|----------|----------|
| `run.py` | Parse args, read domains, create `run_id`, loop domains, write `summary.md` | orchestrator, report | contain step logic |
| `orchestrator.py` | Order steps, hand typed outputs forward, catch exceptions per domain, flush trace | all steps, trace | call Gemini or network directly |
| `scrape.py` | Fetch homepage + key paths, strip to clean text, cache to disk | http cache | call an LLM |
| `extract.py` | Pages -> `CompanyProfile` via Gemini JSON schema | `llm.py` | fetch anything |
| `qualify.py` | Run agent, compute score from findings + `icp.yaml`, set verdict | `agent.py`, `llm.py`, icp | let the LLM do arithmetic |
| `agent.py` | Bounded evidence-gathering loop, stopping rules, per-iteration logging | `tools.py`, `llm.py`, ledger | score or decide the verdict |
| `tools.py` | Tool registry: `fetch_page`, `web_search`, `job_postings`, each returns `ToolResult` with `Evidence[]` | `scrape.py`, `llm.py`, httpx | be invoked by anything but `agent.py` |
| `contacts.py` | Load CSV, choose PoC by role-priority rules, return reason | icp (role priorities) | call an LLM for the common path |
| `pains.py` | Profile + signals + contact -> 2 pains citing evidence IDs | `llm.py` | invent facts absent from the ledger |
| `draft.py` | Pains + contact -> email; validate word count and hook citation; one regenerate | `llm.py` | write the recipient name itself (it is injected) |
| `send.py` | Build MIME, assert `to == SELF_ADDRESS`, Gmail send | Gmail API | accept a `to` argument from upstream |
| `llm.py` | The ONLY module importing `google.genai`. Retry/backoff, disk cache, usage + latency logging, JSON-validate-and-retry | Gemini | contain prompts |
| `trace.py` | Append step records, flush `trace.json` after each step | disk | be rewritten at the end only |
| `report.py` | Render `report.md` deterministically from trace + models | trace | call an LLM |
| `models.py` | All Pydantic contracts | nobody | import from steps |

## Recommended Project Structure

```
E:\Sprinto Case\
├── run.py                      # CLI entry: python run.py domains.txt [--force] [--only domain]
├── domains.txt                 # curated 8-10 domains (mix of fits and non-fits)
├── contacts.csv                # hand-filled from Apollo: domain,name,title,email,linkedin
├── .env / .env.example         # GEMINI_API_KEY, GEMINI_MODEL, SELF_ADDRESS, MAX_AGENT_ITERS
├── .gitignore                  # .env, credentials.json, token.json, cache/, out/
├── config/
│   ├── icp.yaml                # gates, weighted signals, threshold, role priorities, agent budget
│   └── settings.py             # loads .env into a frozen Settings object
├── prompts/
│   ├── extract.md              # company data extraction
│   ├── assess_and_plan.md      # per-signal findings + next action (agent loop body)
│   ├── web_search.md           # grounded search query wrapper
│   ├── pains.md
│   └── draft.md                # voice, <120 words, one hook, soft CTA, sign-off
├── pipeline/
│   ├── models.py               # ALL Pydantic contracts (one file; do not split)
│   ├── orchestrator.py         # process_domain()
│   ├── llm.py                  # Gemini wrapper (retry, cache, logging, grounded_search())
│   ├── scrape.py               # step 1 + fetch_page implementation + page cache
│   ├── extract.py              # step 2
│   ├── qualify.py              # step 3 outer: score, verdict
│   ├── agent.py                # step 3 inner: loop
│   ├── tools.py                # tool registry
│   ├── contacts.py             # step 4
│   ├── pains.py                # step 5
│   ├── draft.py                # step 6
│   ├── send.py                 # step 7
│   ├── trace.py                # Trace, EvidenceLedger
│   └── report.py               # trace -> report.md
├── cache/                      # gitignored
│   ├── pages/<sha1(url)>.json  # {url, status, text, fetched_at}
│   └── llm/<sha256>.json       # key = model + prompt + schema name; value = raw response
├── out/<run_id>/               # gitignored except the demo run you submit
│   ├── summary.md              # one row per domain: score, verdict, contact, send status
│   └── <domain>/{trace.json, report.md}
└── tests/                      # 3-4 tiny tests only (scoring math, word count, to-guard, ledger quote check)
```

### Structure Rationale

- **`models.py` in one file:** contracts are the spine of the build. One file means you can read the whole data flow in one screen, and steps import models, never each other.
- **`llm.py` as the only Gemini importer:** model swap, retry policy, caching and call logging live in one place. This is where most 1.5-hour-build time-sinks (429s, malformed JSON) get contained.
- **`prompts/*.md` separate from code:** you will iterate on the draft and extract prompts far more than on code. The LLM cache key includes the rendered prompt, so edits invalidate cache automatically.
- **`config/icp.yaml` as data:** the "researched ICP" becomes a visible deliverable the grader can read, and the qualifier reads weights from it. Changing a weight is a YAML edit, not a code change.
- **`tools.py` separate from `agent.py`:** the loop (policy) and the tools (mechanism) change at different rates. Tools get added; the loop barely moves.

## Data Contracts (Pydantic v2)

Rule: **LLM-facing models (used as `response_schema`) are flat and simple**: no `dict[str, Any]`, minimal nesting, `Literal` enums allowed, `Optional` only where truly needed. Gemini accepts only a subset of JSON Schema; fancy models fail at request time. Internal models can be richer. Test every LLM-facing model against the API once in the skeleton phase.

```python
# pipeline/models.py
from typing import Literal, Optional
from pydantic import BaseModel, Field

# ---- Step 1 -------------------------------------------------------------
class Page(BaseModel):
    url: str
    path: str                      # "/", "/security", ...
    status: Optional[int] = None   # None = network error
    text: str = ""                 # cleaned visible text, truncated to ~12k chars
    from_cache: bool = False
    error: Optional[str] = None

class RawSite(BaseModel):
    domain: str
    pages: list[Page]              # homepage + best-effort key paths that returned 200
    thin: bool = False             # True if homepage text < ~500 chars (JS-rendered SPA)

# ---- Evidence ledger (cross-cutting) -------------------------------------
class Evidence(BaseModel):
    id: str                                        # "E1", "E2", ... unique per company run
    source_type: Literal["page", "search", "jobs"]
    source_url: str
    quote: str                                     # verbatim snippet
    verified: bool                                 # quote found verbatim in source text (page/jobs). Search = False by definition
    added_by: str                                  # "scrape" | "agent:iter2:fetch_page" ...

# ---- Step 2 (LLM-facing) -------------------------------------------------
class CompanyProfile(BaseModel):
    name: str
    one_liner: str
    is_b2b_saas: Literal["yes", "no", "unclear"]
    sells_to: Literal["enterprise", "mid_market", "smb", "consumer", "unclear"]
    customer_logos: list[str]                      # names seen on the page, [] if none
    has_trust_or_security_page: bool
    certifications_mentioned: list[str]            # e.g. ["SOC 2 Type II"], [] if none
    has_enterprise_plan_or_contact_sales: bool
    hiring_signals: list[str]
    funding_or_stage_mentions: list[str]
    geographies: list[str]
    employee_count_hint: Optional[str] = None

# ---- Step 3 --------------------------------------------------------------
class SignalFinding(BaseModel):                    # LLM-facing: one per signal in icp.yaml
    name: str                                      # must match an icp.yaml signal key
    state: Literal["present", "absent", "unknown"]
    evidence_id: Optional[str] = None              # required when present or absent-with-proof
    note: str                                      # <= 1 sentence

class AgentDecision(BaseModel):                    # LLM-facing: next action
    tool: Literal["fetch_page", "web_search", "job_postings", "stop"]
    path: Optional[str] = None                     # for fetch_page, e.g. "/security"
    query: Optional[str] = None                    # for web_search / job_postings
    target_signals: list[str]                      # which UNKNOWN signals this call should resolve
    rationale: str                                 # <= 1 sentence; goes in the trace

class AssessAndPlan(BaseModel):                    # the single LLM-facing loop response
    findings: list[SignalFinding]
    next_action: AgentDecision

class ScoredSignal(BaseModel):                     # internal, computed in Python
    name: str
    points: int                                    # weight if present (negative for negative signals), else 0
    max_points: int
    state: Literal["present", "absent", "unknown"]
    evidence: Optional[str] = None                 # the quote
    evidence_id: Optional[str] = None
    source_url: Optional[str] = None

class QualificationResult(BaseModel):
    score: int                                     # 0-100, sum of points, clamped
    threshold: int
    signals: list[ScoredSignal]
    gates_failed: list[str] = []                   # e.g. ["is_b2b_saas"]
    verdict: Literal["qualified", "not_qualified", "insufficient_data"]
    stop_reason: str                               # "decisive_reject" | "already_qualified" | "no_unknown_signals" | "max_iterations" | "tool_budget" | "controller_stop" | "repeat_action"
    iterations: int
    verdict_reason: str                            # templated string, built in Python

# ---- Step 4 --------------------------------------------------------------
class Contact(BaseModel):
    domain: str
    name: str
    title: str
    email: str                                     # prospect email: NEVER used as `to:`
    linkedin: Optional[str] = None

class ContactChoice(BaseModel):
    contact: Optional[Contact]                     # None => no contact for domain
    rule_fired: str                                # "role_priority:head_of_security", "fallback:founder"
    reason: str                                    # templated: "Chose X (VP Eng) because ... ; considered: A (CEO), B (Sales)"
    considered: list[str]

# ---- Step 5 (LLM-facing) -------------------------------------------------
class Pain(BaseModel):
    title: str
    why_it_hits_this_person: str
    evidence_ids: list[str] = Field(min_length=1)  # must resolve in the ledger

class PainPoints(BaseModel):
    pains: list[Pain] = Field(min_length=2, max_length=2)

# ---- Step 6 (LLM-facing core + computed fields) --------------------------
class EmailDraft(BaseModel):
    subject: str
    body: str                                      # greeting is injected by Python, model writes the rest
    hook_evidence_id: str                          # which evidence the hook is built on
    word_count: int = 0                            # computed in Python, not trusted from model

# ---- Step 7 --------------------------------------------------------------
class SendResult(BaseModel):
    status: Literal["sent", "skipped", "failed"]
    to: str
    gmail_message_id: Optional[str] = None
    error: Optional[str] = None

# ---- Per-company envelope ------------------------------------------------
class CompanyRun(BaseModel):
    domain: str
    status: Literal["sent", "not_qualified", "no_contact", "failed", "insufficient_data"]
    failed_step: Optional[str] = None
    # each step output is also stored in trace.json; this is the lightweight summary row
```

**Data flow direction (strictly forward):**
`domain -> RawSite -> CompanyProfile -> (Evidence ledger grows) -> QualificationResult -> ContactChoice -> PainPoints -> EmailDraft -> SendResult`.
Steps 4-7 run only if `verdict == "qualified"`. Step 5 and 6 read the ledger (to resolve evidence IDs) but never write to it. Only step 1 and step 3's tools add evidence.

## Architectural Patterns

### Pattern 1: Gather-then-judge (separate evidence from scoring)

**What:** The agent loop produces `SignalFinding`s (state + evidence ID) per rubric signal. `qualify.py` then maps findings to points using weights from `icp.yaml`, sums, applies gates and threshold. The LLM says "SOC 2 badge: absent, evidence E4"; Python says "+15 points".
**When to use:** Always here. It makes the 0-100 score reproducible and the arithmetic auditable.
**Trade-offs:** Slightly more code than "ask the model for a score and reasons". Worth it: a reviewer can recompute the score by hand from the report table.

```python
def score(findings: list[SignalFinding], icp: ICP, ledger: Ledger) -> QualificationResult:
    scored, total = [], 0
    for sig in icp.signals:                       # icp.yaml order
        f = next((x for x in findings if x.name == sig.name), None)
        ev = ledger.get(f.evidence_id) if f and f.evidence_id else None
        state = f.state if f else "unknown"
        if state == "present" and (ev is None):   # present without evidence does not count
            state = "unknown"
        pts = sig.weight if state == "present" else 0
        total += pts
        scored.append(ScoredSignal(name=sig.name, points=pts, max_points=abs(sig.weight),
                                   state=state, evidence=ev.quote if ev else None,
                                   evidence_id=ev.id if ev else None,
                                   source_url=ev.source_url if ev else None))
    ...
```

Key rule inside it: **a signal counts only if it cites an evidence ID that resolves in the ledger.** "Present without evidence" is downgraded to unknown. This kills hallucinated signals.

### Pattern 2: Append-only evidence ledger with quote verification

**What:** Every fact enters via `ledger.add(source_type, source_url, quote, added_by)`. For `page` and `jobs` evidence, `verified = quote_normalized in source_text_normalized`. Search-grounded evidence is `verified=False` and rendered in the report with a "search-sourced" tag (the model's paraphrase of a snippet cannot be string-matched).
**When to use:** Steps 2, 3, 5, 6.
**Trade-offs:** Needs the extract/assess prompts to emit quotes. Cheap to implement (about 30 lines). The report can then show a green "verified verbatim" flag vs "search-sourced", which is a strong defensibility signal.

### Pattern 3: Bounded JSON controller loop (details in section 3)

**What:** Each iteration is one schema-validated LLM call returning `findings + next_action`; Python decides whether to stop and executes the tool.
**When to use:** Only Step 3.
**Trade-offs:** Not "native function calling", but strictly more controllable and loggable. See the comparison below.

### Pattern 4: Typed step function with injected context

**What:** Every step has the shape `def run(inp: InModel, ctx: Ctx) -> OutModel`. `Ctx` carries `settings`, `icp`, `llm`, `trace`, `ledger`. The orchestrator wraps each call in a `trace.step(name)` context manager that records input summary, output, duration, and exceptions.
**When to use:** All steps.
**Trade-offs:** Tiny boilerplate; yields uniform tracing and trivial per-step testing.

```python
# orchestrator.py
def process_domain(domain: str, ctx: Ctx) -> CompanyRun:
    tr = ctx.trace_for(domain)
    try:
        with tr.step("scrape") as s:   raw = scrape.run(domain, ctx);        s.out(raw)
        with tr.step("extract") as s:  prof = extract.run(raw, ctx);         s.out(prof)
        with tr.step("qualify") as s:  qual = qualify.run(prof, raw, ctx);   s.out(qual)
        if qual.verdict != "qualified":
            return tr.finish("not_qualified" if qual.verdict == "not_qualified" else "insufficient_data")
        with tr.step("contact") as s:  pick = contacts.run(domain, ctx);     s.out(pick)
        if pick.contact is None:
            return tr.finish("no_contact")
        with tr.step("pains") as s:    pains = pains.run(prof, qual, pick, ctx);  s.out(pains)
        with tr.step("draft") as s:    mail = draft.run(prof, pains, pick, ctx);  s.out(mail)
        with tr.step("send") as s:     res = send.run(mail, pick, ctx);      s.out(res)
        return tr.finish("sent" if res.status == "sent" else "failed")
    except Exception as e:             # one domain never kills the batch
        return tr.finish("failed", error=e)
```

## 3. Agent Loop Design

### Decision: JSON controller loop, not native function calling

| Criterion | Native function calling | JSON "next action" controller (RECOMMENDED) |
|-----------|-------------------------|---------------------------------------------|
| Combine with `response_schema` | Awkward: structured output + tools in one request is not clearly supported; you end up with two kinds of calls anyway | Native: every call is plain schema-validated JSON |
| Google Search grounding in same request | Only on Gemini 3 family, in Preview, needs `include_server_side_tool_invocations`, "validated" tool mode, and (per docs) newer SDK versions. Older models reject the combination | Not needed: `web_search` is a separate grounded call inside the tool |
| Gemini 3 thought-signature round-tripping | You must pass the full response object back in history or risk 400 errors/quality loss; easy to get wrong in a hurry | No conversation history to manage; each iteration is a fresh call with a compact state summary |
| Logging every call | Must reconstruct from `function_call` parts / automatic function calling hides them | The decision object IS the log record |
| Determinism & stopping | Model may keep calling tools or answer early | Python owns stopping; model only proposes |
| Demo story ("agent chooses tools") | Slightly more "native" | Identical from the grader's view: the model chooses tool + args each iteration and the report shows it |

If you *do* use native function calling anywhere, disable automatic function calling so each call is visible and logged (`automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)`; verify against the installed SDK version). Recommendation for this build: don't.

### The Gemini grounding + function-calling limitation (status verified 2026-11-03)

- **Older behaviour (Gemini 2.x, and what Google's Vertex docs still state):** `google_search` cannot be combined with custom function declarations in one request. Multiple tools are allowed only if all are search-type tools. (MEDIUM confidence: Vertex doc via search snippet.)
- **Current behaviour (Gemini 3 family):** Google documents tool combination (built-in tools plus function declarations in one `tools` list) as **Preview**, with "tool context circulation", `include_server_side_tool_invocations=True`, `validated` tool-choice mode (auto not supported), and an SDK-version requirement (examples reference SDK > 2.0.0 and the Interactions API). Docs also warn that conflicting location/time text in system instructions or function descriptions can degrade it. (MEDIUM confidence: Google docs read via search/fetch summaries.)
- **Design consequence:** treat the limitation as real regardless of model. `web_search` = a standalone `generate_content` call with `tools=[Tool(google_search=GoogleSearch())]`, no schema, no function declarations. It returns prose plus grounding metadata. The controller loop never needs both at once. If grounding is later desired inside the same call, it is an optimization, not a rewrite.

### Loop pseudocode

```python
# agent.py
def gather(profile, raw, icp, ctx) -> AgentOutcome:
    ledger = ctx.ledger                                   # pre-seeded by scrape/extract with page evidence
    used: set[tuple] = set()                              # (tool, path_or_query) already executed
    findings: list[SignalFinding] = []
    for i in range(1, icp.agent.max_iterations + 1):      # default 3
        # ONE LLM call: judge current evidence per signal + propose next action
        plan = ctx.llm.structured(
            prompt=render("assess_and_plan.md", signals=icp.signals, ledger=ledger.digest(),
                          unknown_budget=..., tools_used=sorted(used), remaining_iters=icp.agent.max_iterations - i + 1),
            schema=AssessAndPlan, step=f"agent.iter{i}")
        findings = plan.findings
        scored   = qualify.score(findings, icp, ledger)    # deterministic

        stop = stopping_reason(scored, plan.next_action, used, i, icp, ctx)
        if stop:
            return AgentOutcome(findings, i, stop)

        act = plan.next_action
        key = (act.tool, act.path or act.query)
        used.add(key)
        with ctx.trace.tool_call(i, act) as tc:            # records args, result summary, latency, evidence ids added, error
            result = TOOLS[act.tool](act, ctx)             # may add Evidence to ledger
            tc.record(result)
    return AgentOutcome(findings, icp.agent.max_iterations, "max_iterations")
```

Note the last-iteration subtlety: after the loop's final tool call you need one more assessment (no further action). Implement as `for i in range(1, max+1)` where the final pass skips `next_action` execution, or simply run one extra "assess only" call after the loop. Budget: at most `1 + max_iterations` assessment calls.

### Sufficiency check (Python decides, not the model)

A signal is **unknown** when no evidence resolves it either way. Sufficiency is defined against the rubric, not the model's feelings:

```python
def stopping_reason(scored, action, used, i, icp, ctx) -> Optional[str]:
    now      = sum(s.points for s in scored.signals)
    headroom = sum(s.max_points for s in scored.signals if s.state == "unknown" and s.max_points > 0)
    unknown  = [s for s in scored.signals if s.state == "unknown"]
    if scored.gates_failed:                        return "decisive_reject"      # e.g. B2C, not SaaS
    if now + headroom < icp.threshold:             return "decisive_reject"      # cannot reach threshold even if every unknown is present
    if now >= icp.threshold and not _has_high_value_unknown(unknown, icp):
                                                   return "already_qualified"    # score can't drop below threshold unless negatives; keep simple
    if not unknown:                                return "no_unknown_signals"
    if action.tool == "stop":                      return "controller_stop"
    if (action.tool, action.path or action.query) in used:
                                                   return "repeat_action"        # no thrash
    if ctx.budget.tool_calls_left <= 0:            return "tool_budget"
    if i > icp.agent.max_iterations:               return "max_iterations"
    return None
```

The two score-bound rules (`decisive_reject`, `already_qualified`) are the important ones: they make the loop **economical and explainable** ("stopped after iteration 1 because even if all 6 unknown signals were present, max reachable score was 48 < 60"). That sentence goes straight into `report.md`.

If the loop ends with a score within a few points of threshold and signals still unknown, the verdict is `insufficient_data` rather than a confident reject. Report it; do not email.

### Stopping criteria (all enforced in Python)

| Criterion | Default | Rationale |
|-----------|---------|-----------|
| `max_iterations` | 3 | Each iteration = 1 assess call + 1 tool call; 3 keeps per-domain Gemini calls ~10-12 |
| Per-domain tool budget | 4 tool calls | `web_search` is the costly one; cap searches at 2 |
| Repeat-action guard | on | Same `(tool, path/query)` twice = stop |
| Score-bound early exit | on | See above |
| Whole-domain wall clock | 120 s soft limit | Prevents one hung site from eating the demo |
| Valid `fetch_page` paths | allow-list from `icp.yaml` (`/security`, `/trust`, `/pricing`, `/careers`, `/customers`, `/about`) | Same-site only; the model cannot request arbitrary URLs (SSRF/prompt-injection safety) |

### Tool design

All tools return the same shape and add evidence to the ledger themselves:

```python
class ToolResult(BaseModel):
    tool: str
    args: dict                       # internal model; fine here, it is not LLM-facing
    ok: bool
    summary: str                     # 1-2 lines for the report ("Fetched /trust: 2.1k chars, 200")
    evidence_ids: list[str]          # what got added
    error: Optional[str] = None
    from_cache: bool = False
```

| Tool | Implementation | Evidence it adds |
|------|----------------|------------------|
| `fetch_page(path)` | `scrape.fetch(domain, path)`, same disk page cache. 404 is a valid, cheap result and is itself evidence ("no /trust page") | Quote snippets from page text; absent page recorded as `absent` evidence with the URL tried |
| `web_search(query)` | `llm.grounded_search(query)`: standalone `generate_content` with `google_search` tool. Parse `candidates[0].grounding_metadata` (`grounding_chunks[].web.uri/title`, `grounding_supports` for text-to-source mapping). Grounding URIs are typically Google redirect links; store them together with the title and the returned text. | One Evidence per supported text segment: `source_type="search"`, `verified=False` |
| `job_postings(query?)` | Try the public ATS JSON endpoints first (Greenhouse `boards-api.greenhouse.io/v1/boards/<slug>/jobs`, Lever `api.lever.co/v0/postings/<slug>?mode=json`, Ashby `api.ashbyhq.com/posting-api/job-board/<slug>`), with the slug detected from links on the `/careers` page or guessed from the domain. Filter titles by keywords (security, compliance, GRC, risk, privacy, trust). Fall back to `web_search("<company> careers security compliance GRC roles")`. | Title + URL of matching postings, `source_type="jobs"`, verified against the fetched JSON text |

ATS endpoints are from training knowledge (MEDIUM confidence): smoke-test one before relying on them. If it burns time, cut to "careers page + grounded search"; the contract does not change.

**Prompt-injection note:** scraped text is untrusted. In `assess_and_plan.md` wrap page content in explicit delimiters and state that it is data, not instructions. Tool arguments are validated in Python (path allow-list, query length cap), so an injected "fetch http://evil" does nothing.

### Logging each tool call for the trace

`ctx.trace.tool_call(i, act)` is a context manager that writes, into the `qualify` step's `agent_iterations[]`:

```json
{
  "iteration": 2,
  "decision": {"tool": "fetch_page", "path": "/trust", "target_signals": ["compliance_badge_gap"], "rationale": "No cert badge on homepage; check trust page."},
  "unknown_before": ["compliance_badge_gap", "security_hiring"],
  "score_before": 35,
  "tool_result": {"ok": true, "summary": "GET /trust -> 200, 1840 chars", "evidence_ids": ["E7","E8"], "from_cache": false, "latency_ms": 412},
  "llm_call_ref": "llm-0007",
  "score_after": 50,
  "stop_check": null
}
```

`llm_call_ref` points into the trace's `llm_calls[]` list (model, prompt hash, prompt file path, token usage, latency, cache hit, raw response). Prompts themselves are stored once per call in the trace JSON so you can re-run any decision.

## 4. Error Handling and Resilience

### Per-domain isolation

- `process_domain` has one outer `try/except Exception`. On failure it records `failed_step`, the exception type and message, writes the trace and report with whatever exists, returns `CompanyRun(status="failed")`, and `run.py` proceeds to the next domain.
- A failed step never raises out of the orchestrator; `KeyboardInterrupt` is the only thing that aborts a batch (and the partial traces are already on disk because the trace flushes after each step).
- **Not-failures that need distinct statuses:** `not_qualified`, `insufficient_data`, `no_contact`. These are legitimate outcomes, not errors, and each gets its own row in `summary.md`.
- A domain run is **sequential**; the batch is **sequential by default**. Gemini free-tier request-per-minute limits are low (check AI Studio for your key's actual limits) and parallelism mostly buys you 429s. If total runtime hurts, add a `ThreadPoolExecutor(max_workers=2)` over domains later; per-domain state is already isolated (no shared mutable globals, one `Ctx` per domain).

### Retries and backoff for 429s

Two layers, both cheap:

1. **SDK-level (verified):** the `google-genai` Python SDK supports `types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=..., initial_delay=..., max_delay=..., exp_base=..., jitter=..., http_status_codes=[408, 429, 500, 502, 503, 504]))` at client construction. Set this once in `llm.py`. Per docs it retries 429 and 5xx with exponential backoff.
2. **App-level in `llm.py`:**
   - On a 429 that carries a server-suggested retry delay, honour it (cap at about 60 s), then retry up to 3 more times. If still failing, raise `LLMUnavailable`, which fails only that domain.
   - On schema validation failure (`ValidationError`, empty `.parsed`): retry once, appending the validation error to the prompt. Then fail the step.
   - On a safety/blocked response: do not retry; record as step failure.

```python
class LLM:
    def structured(self, prompt, schema, step) -> T:
        key = sha256(f"{self.model}|{schema.__name__}|{prompt}")
        if (hit := self.cache.get(key)): self.trace.llm_call(step, prompt, hit, cache_hit=True); return schema.model_validate_json(hit)
        for attempt in (1, 2):
            t0 = time.time()
            resp = self.client.models.generate_content(model=self.model, contents=prompt,
                       config=types.GenerateContentConfig(response_mime_type="application/json",
                                                          response_schema=schema, temperature=0.2))
            self.trace.llm_call(step, prompt, resp.text, latency=time.time()-t0, usage=resp.usage_metadata)
            try:
                out = schema.model_validate_json(resp.text)
                self.cache.put(key, resp.text)          # cache ONLY validated successes
                return out
            except ValidationError as e:
                prompt += f"\n\nYour previous output failed validation: {e}. Return valid JSON only."
        raise LLMOutputInvalid(step)
```

### Disk caching

| Cache | Key | Value | Why |
|-------|-----|-------|-----|
| Pages | `sha1(final_url)` (normalize: lowercase host, strip fragment and trailing slash) | status, cleaned text, fetched_at | Re-runs and prompt iteration never re-hit sites; also records 404s so "/trust missing" is stable |
| LLM | `sha256(model + schema name + full rendered prompt)` | raw validated JSON text | Saves quota while iterating on later steps; editing a prompt invalidates only that step and its downstream steps (the downstream prompts contain the upstream output) |
| Grounded search | same LLM cache, key includes the query | text + grounding metadata | Search is the most quota-expensive call |

Rules: cache successes only (never errors or 4xx/5xx other than 404); `--force` flag bypasses both caches; the cache is **never** applied to `send`. For idempotency of sending, `send.py` writes `out/<run_id>/<domain>/sent.marker`; re-running the same `run_id` skips the send unless `--force` (prevents duplicate emails while you debug the report). Since "always send" is a decision and recipients are your own inbox, duplicates are annoying rather than harmful, so keep this minimal.

### Scraping resilience

- `httpx.Client(timeout=10, follow_redirects=True, headers={"User-Agent": "...browser-like..."})`, max 2 retries on timeouts/5xx, no retries on 4xx.
- Try `https://domain`, then `https://www.domain` on connect failure.
- Step 1 fetches homepage + a fixed shortlist of paths (`/security`, `/trust`, `/pricing`, `/about`, `/customers`), concurrently is fine (small, one site). A missing path is recorded, not raised.
- **Thin-content flag:** if the homepage text is under about 500 chars (JS-rendered SPA), set `RawSite.thin=True`. The agent loop's first assess call sees this and leans on `web_search`. Do not attempt a headless browser in a 1.5-hour build.
- Truncate each page to about 12k chars and strip nav/footer/script/style before sending to Gemini.

### Step-level guardrails (cheap, high value)

| Guard | Where | Effect |
|-------|-------|--------|
| `to == SETTINGS.SELF_ADDRESS` assert; `send()` has no `to` parameter | `send.py` | Case rule enforced in code, not by discipline |
| Word count < 120 recomputed in Python; one regenerate with "shorten" instruction; else mark `draft_over_limit` and send anyway with a warning in the report | `draft.py` | Meets the 120-word requirement measurably |
| `hook_evidence_id` must resolve in ledger | `draft.py` | No hook without source |
| Greeting `Hi {first_name},` and sign-off injected by Python from `ContactChoice` and config | `draft.py` | Name can never be hallucinated |
| Subject prefixed `[Sprinto test]` and footer line "Intended recipient: Name, Title @ Company (not sent to them)" | `send.py` | Makes the inbox email self-explaining when demoed |
| Pains: each `evidence_ids` must resolve; reject and retry once if not | `pains.py` | Pain points are grounded |

## 5. Trace and Report Design

**Principle:** the trace is the source of truth; the report is a pure function of it. No LLM touches `report.py`. If a decision is not in the trace, it did not happen.

### `trace.json` shape

```json
{
  "run_id": "2026-11-03T10-41-07",
  "domain": "example.com",
  "model": "<GEMINI_MODEL>",
  "status": "sent",
  "started": "...", "ended": "...",
  "steps": [
    {"name": "scrape",   "status": "ok", "duration_ms": 2310, "input": {"domain": "example.com"}, "output": {"...RawSite summary: urls, statuses, char counts..."}},
    {"name": "extract",  "status": "ok", "llm_calls": ["llm-0001"], "output": {"...CompanyProfile..."}},
    {"name": "qualify",  "status": "ok", "llm_calls": ["llm-0002","llm-0004","llm-0006"],
     "agent_iterations": [ {"...see tool-call record above..."} ],
     "output": {"...QualificationResult..."}},
    {"name": "contact",  "status": "ok", "output": {"...ContactChoice incl. considered[] and rule_fired..."}},
    {"name": "pains",    "status": "ok", "output": {"...PainPoints..."}},
    {"name": "draft",    "status": "ok", "output": {"...EmailDraft incl. word_count..."}},
    {"name": "send",     "status": "ok", "output": {"...SendResult..."}}
  ],
  "evidence": [ {"id": "E1", "source_type": "page", "source_url": "...", "quote": "...", "verified": true, "added_by": "scrape"} ],
  "llm_calls": [ {"id": "llm-0001", "step": "extract", "model": "...", "prompt_file": "prompts/extract.md", "prompt": "...", "response": "...", "usage": {"in": 0, "out": 0}, "latency_ms": 0, "cache_hit": false} ],
  "error": null
}
```

Write rules: flush the whole file after **each** step (cheap at this size), so a crash leaves a usable partial trace. UTF-8 explicitly (`open(..., "w", encoding="utf-8")`): this is Windows, and default cp1252 will crash on smart quotes in scraped text.

### `report.md` layout (rendered, deterministic)

1. **Header banner:** domain, verdict, score/threshold, final status (sent / not qualified / ...), run id.
2. **Why this company** (qualification): table `Signal | Weight | Points | Evidence (quote) | Source | Verified?`, a one-line total, then gates, then the stop reason in plain English. Include "what would have changed the verdict" (unknown signals and their weights).
3. **How the agent got there:** one block per iteration: unknown signals before, tool chosen and why (rationale), result summary, score delta. If the loop never ran, say why ("all signals resolved from homepage + key pages").
4. **Why this person:** chosen contact, rule fired, candidates considered with reasons they lost.
5. **Why these pain points:** each pain with its evidence quotes inline (resolved from IDs).
6. **The email:** subject, body, word count (with a pass/fail against 120), hook and its evidence quote, send result with Gmail message ID.
7. **Appendix:** evidence ledger, step timings, LLM calls count and cache hits.

Batch level: `out/<run_id>/summary.md` with one row per domain (score, verdict, stop reason, contact, status, calls used). For the not-qualified domains this is the "filter works" exhibit.

### Why every decision is defensible

| Decision | Defensibility mechanism |
|----------|--------------------------|
| Company qualified/rejected | Points computed in Python from `icp.yaml` weights; each point cites a ledger quote and URL; unverified (search) evidence is flagged |
| Loop took action X | Rationale + target signals per iteration; score-bound stop reasons |
| Loop stopped | Named `stop_reason` + the numbers behind it |
| PoC chosen | `rule_fired` + `considered[]`, all derived from `icp.yaml` role priorities |
| Pain points | Evidence IDs resolved to quotes |
| Email hook | `hook_evidence_id` resolved to a quote |
| Reproducibility | Prompt and raw response stored per call; LLM cache means a re-run reproduces the same output |

## Data Flow

### Request flow (one domain)

```
domains.txt line
    ↓
scrape ──► RawSite ─────────────► ledger seeded with page quotes
    ↓
extract ─► CompanyProfile
    ↓
qualify.run ─► agent.gather ─┬─► LLM assess_and_plan ─► findings + next_action
                             │        ▲                         │
                             │        │ ledger grows            ▼
                             │        └──────────── tools.py (fetch_page | web_search | job_postings)
                             └─► stopping_reason (Python) ─► exit
              score(findings, icp, ledger) ─► QualificationResult
    ↓ (qualified only)
contacts.run ──► ContactChoice (CSV + icp role priorities, no LLM)
    ↓
pains.run ─────► PainPoints (profile + findings + contact role; cites evidence IDs)
    ↓
draft.run ─────► EmailDraft (validated: words, hook id)
    ↓
send.run ──────► SendResult (to = SELF_ADDRESS)
    ↓
trace.json (flushed every step) ──► report.py ──► report.md
```

### Key data flows

1. **Evidence flow:** `scrape/tools -> ledger -> findings -> ScoredSignal -> pains -> draft hook -> report`. The same ID threads end to end.
2. **Config flow:** `icp.yaml` feeds the assess prompt (signal list and definitions), the scorer (weights, threshold, gates), the agent (budget, path allow-list) and contact selection (role priorities). One file defines "right companies".
3. **Identity flow:** `contacts.csv -> ContactChoice -> draft (greeting, hint of role) -> send (footer only)`. The prospect's email never reaches the `to:` header.

## Contact Selection (Step 4) in one paragraph

Deterministic first: normalize titles in `contacts.csv` to role buckets via keyword rules in `icp.yaml` (`security: [ciso, head of security, infosec]`, `compliance: [grc, compliance]`, `engineering: [cto, vp eng, head of eng]`, `exec: [ceo, founder, co-founder]`), then pick the highest-priority bucket present. Priority depends on a company-size hint from the profile: small (under ~50 staff) favours `exec/CTO`, larger favours `security/compliance` then `engineering`. Output a templated `reason` listing who was considered. Use an LLM only as a tie-break when two contacts share the top bucket (optional; skip in the first pass). No matching contact means `no_contact`, no email, reported honestly.

## Suggested `config/icp.yaml` shape

```yaml
threshold: 60
gates:                     # fail any => reject regardless of score
  - name: is_b2b_saas
    must_be: "yes"          # from CompanyProfile.is_b2b_saas ("unclear" is allowed through to the agent)
signals:                   # weights sum to ~100 on positives; negatives subtract
  - {name: no_cert_badge_but_trust_page,  weight: 15, definition: "Has trust/security page but shows no SOC 2/ISO 27001 badge", tool_hint: fetch_page}
  - {name: enterprise_motion,             weight: 15, definition: "Enterprise plan, 'contact sales', or large-logo customers", tool_hint: fetch_page}
  - {name: compliance_security_hiring,    weight: 15, definition: "Open roles in security/GRC/compliance", tool_hint: job_postings}
  - {name: recent_funding_series_a_to_c,  weight: 15, definition: "Funding in last ~18 months at Series A-C", tool_hint: web_search}
  - {name: stated_audit_plans,            weight: 15, definition: "Mentions upcoming SOC 2 / ISO audit or customer-driven requirement", tool_hint: web_search}
  - {name: eu_us_expansion_gdpr,          weight: 10, definition: "EU/US market move creating GDPR exposure", tool_hint: web_search}
  - {name: sized_for_sprinto,             weight: 15, definition: "~20-500 employees", tool_hint: web_search}
  - {name: already_certified_mature_grc,  weight: -25, definition: "Already holds SOC 2 Type II + ISO and has a GRC team", tool_hint: fetch_page}
agent:
  max_iterations: 3
  max_tool_calls: 4
  max_searches: 2
  fetchable_paths: [/security, /trust, /pricing, /careers, /customers, /about]
roles:                     # keyword rules + priority by size bucket
  ...
```

The actual signals and weights are the ICP research deliverable (another researcher's output); this file is only the container. Keep weights in the YAML so rubric tuning after the first test run needs no code change.

## Scaling Considerations

This is a one-shot CLI against 8-15 domains; "scale" means quota and runtime, not users.

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 10 domains (the case) | Sequential, disk caches, about 100-130 Gemini calls total. Free-tier RPM is the only real constraint |
| 100 domains | Add `ThreadPoolExecutor(2-4)` over domains; global token-bucket limiter in `llm.py`; resume by skipping domains with a complete trace |
| 1,000+ | Out of scope: queue, DB-backed ledger, paid-tier quota, ATS/contact APIs |

### Scaling Priorities

1. **First bottleneck:** Gemini RPM/daily quota on the free tier (≈10-12 calls per qualified domain). Mitigate with LLM cache, merged `assess_and_plan` call (one call per iteration, not two), score-bound early exit, and a Flash-class model.
2. **Second bottleneck:** wall-clock from sequential grounded searches. Mitigate by capping searches at 2 per domain.

## Anti-Patterns

### Anti-Pattern 1: Letting the LLM produce the score
**What people do:** "Rate this company 0-100 and explain."
**Why it's wrong:** Non-reproducible, un-auditable, drifts between runs; the point arithmetic can't be defended.
**Do this instead:** LLM emits per-signal state + evidence ID; Python applies weights.

### Anti-Pattern 2: Unbounded or unstructured agent loop
**What people do:** `while not done: model.chat(...)`.
**Why it's wrong:** Quota burn, loops on the same tool, impossible to explain stopping.
**Do this instead:** Python-owned stop rules (iteration cap, tool budget, repeat guard, score-bound exit); model only proposes.

### Anti-Pattern 3: Relying on Google Search + function declarations in one request
**What people do:** Put `google_search` and custom functions in one `tools` list.
**Why it's wrong:** Unsupported on older models; Preview-only and flag-gated on Gemini 3; changes under you.
**Do this instead:** Grounded search as its own call wrapped in a Python tool.

### Anti-Pattern 4: Model-written names, addresses, or recipient
**What people do:** Pass the contact blob to the model and let it produce "Hi Priya,".
**Why it's wrong:** Hallucinated or wrong name = demo-killing failure; `to:` mistakes break the hard case rule.
**Do this instead:** Inject name from CSV; `send()` takes no recipient parameter.

### Anti-Pattern 5: One big trace written at the end
**What people do:** Build a dict and `json.dump` on success.
**Why it's wrong:** A crash loses all evidence of what happened.
**Do this instead:** Flush after every step.

### Anti-Pattern 6: Prompts inline in Python and cache-less iteration
**What people do:** Re-run the whole batch every time the email wording changes.
**Why it's wrong:** Burns scrape time and quota in a 1.5-hour window.
**Do this instead:** `prompts/*.md` plus page cache plus LLM cache; only changed prompts re-call Gemini.

### Anti-Pattern 7: Gold-plating (headless browsers, DB, async, plugin tool system)
**What people do:** Add Playwright, SQLite, asyncio, a registry framework.
**Why it's wrong:** Time budget is 1.5 hours; none of it improves the demo.
**Do this instead:** Plain functions, JSON files, a dict as the tool registry.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Gemini (`google-genai`) | Only via `llm.py`; `structured()` for schema calls, `grounded_search()` for search | Model ID from `GEMINI_MODEL` env var; do not hardcode (names move fast, docs show Gemini 3 preview IDs). Retry options set at client construction |
| Gemini Google Search grounding | Separate call, `tools=[Tool(google_search=GoogleSearch())]`, no schema | Parse `grounding_metadata`; treat output as `verified=False` evidence |
| Gmail API | `google-api-python-client` + `google-auth-oauthlib`; scope `https://www.googleapis.com/auth/gmail.send`; `users().messages().send(userId="me", body={"raw": base64url(MIME)})` | **Do the OAuth browser consent in the first 10 minutes** (writes `token.json`). If the Cloud OAuth consent screen is in "Testing", the refresh token can expire after about 7 days, so run the consent on the day; add your own address as a test user |
| Target websites | `httpx` + BeautifulSoup in `scrape.py` | Polite: timeouts, ~6 requests/domain, cache; some sites will 403 bots: record and continue |
| ATS job boards (Greenhouse/Lever/Ashby) | Public JSON endpoints in `job_postings` | MEDIUM confidence on exact URL shapes: smoke test; fallback to search |
| Apollo | Manual, outside the program | Output is `contacts.csv`, columns `domain,name,title,email,linkedin` |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| orchestrator ↔ steps | Direct function calls with Pydantic models | Steps never import each other |
| qualify ↔ agent | `agent.gather()` returns findings + stop reason; `qualify` scores | Agent never computes a verdict |
| agent ↔ tools | `TOOLS[name](decision, ctx) -> ToolResult` | Args validated in Python against allow-list |
| any step ↔ trace/ledger | via `ctx` | Steps 4-7 read the ledger, only scrape/tools write |
| any step ↔ Gemini | only through `ctx.llm` | Single choke point for retry/cache/logging |
| trace ↔ report | `report.py` reads `trace.json` | One-way; report never mutates trace |

## 6. Suggested Build Order (walking skeleton first)

Time-boxed against the 90-minute session. Each stage ends with something runnable.

### Stage 0: Plumbing and risk burn-down (about 0:00-0:12)
- Project scaffold, `.gitignore` (secrets, cache, out), `.env`, `requirements.txt`.
- **Gmail OAuth consent end to end**: `credentials.json` -> `token.json` -> send a hardcoded "hello" to yourself. This is the highest external-risk item; do it first.
- Gemini smoke test: one `structured()` call with a tiny Pydantic model, to confirm the key, the model ID, and that `response_schema` works with your SDK version.

### Stage 1: Walking skeleton (about 0:12-0:35) -> **email in inbox**
Run for ONE domain, every step crude, all in one pass, with the real interfaces:
- `models.py` with the contracts above (can omit evidence fields at first, but keep the types).
- `scrape.py`: homepage only, `text[:8000]`.
- `extract.py`: real Gemini schema call.
- `qualify.py`: single LLM call, no loop, no rubric; just returns a hardcoded-ish score and `qualified`.
- `contacts.py`: first CSV row for the domain.
- `pains.py` + `draft.py`: one prompt each.
- `send.py`: real Gmail send to `SELF_ADDRESS`.
- `trace.py`: dumb dict appended per step and dumped to `out/<domain>/trace.json`.
- `run.py` + `orchestrator.py` with the per-domain `try/except` already in place.

Exit test: `python run.py domains.txt` with one domain delivers an email. Everything after this is deepening; nothing needs a rewrite because the contracts already match.

### Stage 2: Cheap safety and iteration speed (about 0:35-0:45)
- Page cache and LLM cache (small, saves quota for every later stage).
- `llm.py` retry options and validate-retry.
- Run 3-4 domains through; fix crashes. Per-domain isolation proven by one deliberately bad domain.

### Stage 3: Defensibility layer (about 0:45-0:55)
- Evidence ledger (`Evidence`, IDs, quote verification); extract emits quotes.
- `report.py` rendering from trace; `summary.md`.
- Even before the loop exists, the report can show the page-derived signals. This is the stage that makes the product demo-able.

### Stage 4: Real qualification (about 0:55-1:10)
- `icp.yaml` (from the ICP research), `assess_and_plan` prompt, deterministic `score()`, gates, threshold, verdicts.
- Then the agent loop: `fetch_page` first (simplest tool, uses existing scrape), then `web_search` (grounded call wrapper), then `job_postings` (ATS probe + fallback). Add stop rules before adding tools.
- Verify with one clear fit, one clear non-fit, one data-thin case that the loop fires only for the thin case.

### Stage 5: Contact logic and writing quality (about 1:10-1:20)
- Role-priority selection with templated reason.
- Pains with evidence IDs; draft validation (word count, hook id, injected greeting and sign-off), subject prefix, intended-recipient footer.

### Stage 6: Full run, tune, finalize (about 1:20-1:30)
- Run the curated 8-10 domain list; inspect `summary.md`; adjust weights or threshold in YAML only if the fit/non-fit split looks wrong.
- Commit the demo run's `out/` directory (or its best two reports) for the submission.

### Cut-line if time slips
Cut in this order: ATS probing in `job_postings` (keep search fallback) -> LLM tie-break in contacts -> parallelism -> fancy report formatting. Never cut: Gmail send guard, evidence citations, per-domain isolation, the score-bound stop rule.

### Dependency graph (what blocks what)

```
models ──► llm ──► extract ──► qualify(simple) ──► pains ──► draft ──► send
   │        │                       │
   │        └─ cache/retry           └─► icp.yaml + score() ──► agent + tools
   └─► trace ──► ledger ──► report                  (needs ledger from Stage 3)
scrape ──► (page cache) ──► fetch_page tool
Gmail OAuth ──► send     (independent; do first)
contacts.csv ──► contacts (independent; hand-fill in parallel)
```

## Sources

- Google AI for Developers, "Combine built-in tools and function calling" (tool-combination doc): https://ai.google.dev/gemini-api/docs/tool-combination (Preview; Gemini 3 family; `include_server_side_tool_invocations`; `validated` mode; read via search/fetch summary, MEDIUM)
- Google AI Studio function-calling doc, "Multi-tool use" section: https://aistudio.google.com/docs/function-calling (MEDIUM; says Gemini 3 can combine built-in tools with function calling in the Interactions API)
- Google blog, "Gemini API tooling updates: context circulation, tool combos and Maps grounding for Gemini 3" (2026-03-17): https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-tooling-updates/ (MEDIUM)
- Vertex AI "Grounding with Google Search" doc, statement that search tools cannot be mixed with non-search tools in one request: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/ground-with-google-search (MEDIUM; Vertex-specific, justifies designing around it)
- Vertex AI "Retry strategy" doc for `google-genai` `HttpRetryOptions` (attempts, delays, status codes 408/429/5xx): https://docs.cloud.google.com/vertex-ai/generative-ai/docs/retry-strategy (HIGH for the SDK option names)
- Training knowledge, unverified in this session (LOW-MEDIUM, smoke-test before use): `AutomaticFunctionCallingConfig(disable=True)`; ATS public endpoint URL shapes; Gmail `gmail.send` scope and the 7-day refresh-token expiry for OAuth apps in Testing mode; grounding chunk URIs being Google redirect links; Gemini `response_schema` accepting only a JSON-Schema subset.

---
*Architecture research for: AI-driven B2B cold-outreach pipeline (Sprinto Outbound Autopilot)*
*Researched: 2026-11-03*
