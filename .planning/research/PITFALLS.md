# Pitfalls Research

**Domain:** AI-driven B2B cold-outreach pipeline (Python CLI, Gemini extraction/qualification/drafting with agent loop + Google Search grounding, Gmail API send, hand-filled Apollo contacts.csv) for Sprinto (compliance automation SaaS)
**Researched:** 2026-11-03
**Confidence:** MEDIUM-HIGH. Gemini model IDs, deprecations, and grounding/structured-output rules come from official docs fetched today (HIGH on the facts, but Google changes these monthly, so verify at build time; items marked VERIFY). Gmail OAuth, scraping, and Windows items are well-established (HIGH). Free-tier numeric quotas could not be confirmed from the official page (LOW; read them from the AI Studio rate-limit view).

> Build-time budget is 1.5 hours. Pitfalls are ordered by "will it kill the demo or the credibility of the decisions", not by theoretical severity. Items tagged **[DAY-ZERO]** should be handled in the first 15 minutes.

---

## Critical Pitfalls

### Pitfall 1: Fabricated personalization (hallucinated hooks, funding stages, facts)

**What goes wrong:**
The draft says "Congrats on your Series B" or "saw your recent SOC 2 push" when the extracted data said nothing of the sort. The model fills gaps with plausible fluff. Funding stage and dates are the worst offenders: grounded search returns stale rounds, or the model confuses the company with a same-named entity. A prospect who sees one wrong fact stops reading; a reviewer who sees one unsupported claim in `report.md` stops trusting every decision.

**Why it happens:**
LLMs are rewarded for completing a "personalised" template. The extraction schema has no way to say "unknown", so the model guesses. The email prompt receives the whole company blob, not a list of vetted facts. Nothing checks the output against the sources.

**How to avoid:**
- Every extracted field is `{value, evidence_quote, source_url}` with `value = "unknown"` as a first-class enum member (`funding_stage: Literal["pre-seed","seed","series-a","series-b","series-c","series-d+","bootstrapped","public","unknown"]`).
- **Programmatic quote check:** after extraction, assert `evidence_quote` is a substring (whitespace-normalised) of the fetched page text. Quote not found = value is downgraded to `unknown` and the downgrade is logged. This is ~10 lines of Python and is the single highest-leverage defensibility feature.
- The drafting step receives only a short list of **verified hook candidates** (each with id, fact, source_url). The email JSON must return `hook_id`; code rejects any `hook_id` not in the list. The model cannot invent a hook, only pick and phrase one.
- Funding/news from grounding: require a date and a source domain. Treat anything older than ~18 months (relative to 2026-11-03; inject today's date in the prompt) as "stale: do not use as hook". Never put a funding amount in the email unless it came with a cited source.
- Disambiguate in grounded queries: always use `"<company name>" "<domain>"`, and drop grounded answers whose cited sources do not mention the domain or company name.

**Warning signs:**
Hook mentions something not found by grep of the saved page text; every company is "Series B"; hook text is vague ("your impressive growth", "your leadership in X"); `unknown` never appears in any trace.

**Phase to address:** Phase 2 (extract schema + quote verification), Phase 5 (hook-id constrained drafting).

---

### Pitfall 2: Unreachable page treated as "no signal" (absence of evidence != evidence of absence)

**What goes wrong:**
`/security` returns 403 (Cloudflare), times out, or the SPA returns an empty shell. The pipeline concludes "no trust page, no certification badge", which is the *strongest ICP signal*, and scores the company as a hot lead. Or the opposite: an unreachable site is scored 0 and silently rejected. Either way the decision is indefensible.

**Why it happens:**
Scrape failures collapse to `""`. The extractor then reports "no SOC 2 mention found" and the rubric rewards it.

**How to avoid:**
- Every fetch returns a typed result: `{url, final_url, status, outcome: OK|NOT_FOUND|BLOCKED|TIMEOUT|EMPTY_SHELL|NON_HTML|TOO_BIG, text_len, content_hash}`. Only `NOT_FOUND` (a real 404 on a path) counts as evidence of absence. `BLOCKED/TIMEOUT/EMPTY_SHELL` produce `signal = "unknown"`, not `false`.
- The rubric treats `unknown` as 0 points plus lowers a separate **data_confidence** number. If data_confidence is below a floor, the verdict is `INSUFFICIENT_DATA` (not "no fit") and this triggers the agent loop (Pitfall 6) or the grounded-search fallback.
- Detect **soft 404s**: many SPAs return 200 with the homepage for `/security`. Hash the text; if `/security` text hash equals homepage hash (or the title is identical), classify as `NOT_FOUND`/`EMPTY_SHELL`, not as a page.
- The report must show the fetch-outcome table per company so a reviewer can see what was actually seen.

**Warning signs:**
Score for a blocked site is suspiciously high or exactly 0; trace shows `text_len` of a few hundred characters on a company that is obviously large; `security` and `home` hashes are identical.

**Phase to address:** Phase 2 (typed fetch result), Phase 3 (rubric handles unknown).

---

### Pitfall 3: Gemini grounding + structured output + function calling combination errors **[VERIFY at build time]**

**What goes wrong:**
You enable `google_search` and also set `response_mime_type="application/json"` / `response_schema`, or also pass Python functions for the agent loop, and either get `400 INVALID_ARGUMENT` ("controlled generation is not supported with google_search tool" on older models), silently empty `groundingMetadata`, or JSON that starts mid-sentence.

**Why it happens:**
Per official docs fetched today, combining structured output with built-in tools (Google Search, URL context, code execution, function calling) is **preview and Gemini 3-series only**. Community reports (forum, 2026) say grounded responses on Gemini 3.5/3.6 Flash can drop the start of the text so JSON is truncated at the front, and that grounding metadata can be empty when structured output is combined with `google_search`. Older models (2.x) reject the combination outright. The same docs also say `minLength/maxLength/uniqueItems` etc. are stripped from the schema, not enforced.

**How to avoid (opinionated):**
- **Two-call pattern, always.** Call A: grounded search with `tools=[google_search]`, **free text out, no schema**. Call B: a separate non-tool call that converts Call A's text (plus the `groundingChunks` URLs you captured from metadata in code) into your Pydantic schema. This works on every model, is trivially cacheable, and each call is separately traceable (which suits "defend every decision").
- **Do not use Gemini-native function calling for the agent loop.** Implement the loop as: model returns a structured `next_action` JSON (`{action: "fetch_page"|"search"|"jobs"|"finish", arg, reason}`), Python executes the tool, appends the result to the transcript. This avoids the tool-mixing matrix entirely and makes every step a plain loggable dict.
- Validate with Pydantic after parsing; do not trust `maxLength`/`minLength` (enforce word counts in code, Pitfall 12).
- Keep schemas flat: lists of small objects, `Literal` enums, no `dict[str, str]`, no deep unions. Large or deeply nested schemas get `400 INVALID_ARGUMENT`.
- Capture `response.candidates[0].grounding_metadata` (`web_search_queries`, `grounding_chunks[].web.uri/title`, `grounding_supports`) into the trace verbatim. Grounding URIs are `vertexaisearch.cloud.google.com/grounding-api-redirect/...` redirect links whose `title` is typically only the source domain; store both and treat the domain as the human-readable citation. Redirect links may not be long-lived (MEDIUM confidence), so store the title/domain at capture time.

**Warning signs:**
400 on first grounded call; `grounding_metadata` is `None` on a response that clearly used search; JSON parse errors that begin "Expected property name" at char 0; response begins with lowercase mid-sentence.

**Phase to address:** Phase 1 (smoke-test one grounded call and one structured call with the exact model ID before building anything), Phase 3.

---

### Pitfall 4: Model ID deprecation / wrong model name mid-build

**What goes wrong:**
The code hardcodes `gemini-2.5-flash` (what every tutorial and model-memory says). Per the official deprecations page fetched 2026-11-03: `gemini-2.5-flash` is **deprecated, no longer selectable in AI Studio, shutdown Dec 1 2026 with auto-routing to `gemini-3.5-flash-lite`** (behaviour changes under you); `gemini-3.5-flash` and `gemini-3.7-flash` are aliases now routed to 3.6 / 3.8; current listed models are `gemini-3.6-flash` and `gemini-3.8-flash`; `gemini-3-flash-preview` is preview; `gemini-2.5-flash-lite` has no announced shutdown. Third-party blogs contradict each other on dates, so do not trust them.

**Why it happens:**
LLM-written code and old docs reference stale IDs; preview models are also more prone to 503 and tighter quotas.

**How to avoid:**
- `GEMINI_MODEL` and `GEMINI_FALLBACK_MODELS` in `.env`, read in one place. Default recommendation: `gemini-3.6-flash` primary (stable, non-preview), `gemini-3.8-flash` as an alternate, `gemini-2.5-flash-lite` as the last-resort cheap fallback. Confirm with `client.models.list()` at startup.
- Preflight (`python run.py --preflight`, or automatic at start): one tiny call per model ID, print which works. Takes 5 seconds and catches 404 "model not found" before the demo, not during it.
- Log the exact model ID and `response.model_version` in every trace entry. Gemini 3.x reportedly prefers default temperature (VERIFY in the model card); do **not** rely on `temperature=0` for determinism (see Pitfall 7).

**Warning signs:**
`404 models/... is not found for API version`; different answer quality between morning and demo because an alias re-routed.

**Phase to address:** Phase 1.

---

### Pitfall 5: Free-tier 429s and quota exhausted before the demo

**What goes wrong:**
Dev iteration burns the daily request quota; during the live run you get `429 RESOURCE_EXHAUSTED`. The agent loop multiplies calls (each company = extract + N loop steps + grounded search + 2-3 drafting calls), so 10 companies can be 100-200 calls. Grounded search has its own per-project daily cap (official rate-limits page: Gemini 3+ grounding is "subject to a default limit of 1,500 RPD per project"; whether this applies to the free tier is unclear).

**Why it happens:**
Limits are per **project**, not per key, and RPD resets at **midnight Pacific**. Today is Tue 3 Nov 2026, US DST ended 1 Nov, so midnight PST = 08:00 UTC = **13:30 IST**. A 10:30 IST session therefore spends all of this morning's build-time experiments against the same bucket as the live demo, and the reset is after the demo. Exact free-tier RPM/RPD/TPM numbers differ by model and change often; the official page does not state them in text (read them in the AI Studio rate-limit view now).

**How to avoid:**
- Check AI Studio's rate-limit view for the chosen model **now**, write RPM and RPD in `config`, and compute budget: `companies x calls_per_company` must be well under RPD with a 2x margin.
- A **disk cache** keyed on `sha256(model + prompt + schema)` and on URL fetches. Re-runs during build and the demo cost zero calls. This is also the replay mechanism for demo safety (Pitfall 20).
- Retry wrapper: exponential backoff with jitter on 429/500/503 (honour `retryDelay` in the error body), max 3 tries, then model fallback chain, then record `LLM_UNAVAILABLE` for that step and continue with the next company.
- Cap calls per company (hard budget, Pitfall 6). Run companies sequentially or at concurrency 2; do not `asyncio.gather` all of them (RPM spikes).
- If available, enabling billing on the project (a few cents for this volume) removes the free-tier ceiling. Decide this early. It is the cheapest insurance.

**Warning signs:**
First 429 during build; quota graph near the cap before lunch; run time per company growing (backoff sleeps).

**Phase to address:** Phase 1 (cache + retry wrapper + preflight), Phase 7 (batch pacing).

---

### Pitfall 6: Agent loop with no stopping criterion (loops, re-fetches, cost blow-up)

**What goes wrong:**
The model keeps asking for "one more page" or re-requests `/security` it already saw, or alternates between search and fetch; the run never ends or ends only on timeout. Each iteration re-sends the growing transcript, so token cost is quadratic.

**Why it happens:**
"Fetch more info if insufficient" has no definition of "sufficient". Nothing deduplicates tool calls. The model has no budget awareness.

**How to avoid:**
- **Hard caps in code:** `MAX_STEPS = 4` tool calls per company, `MAX_GROUNDED_SEARCHES = 2`, wall-clock cap per company (e.g., 90 s), total-token cap. On cap, force a final `finish` step; the verdict is then computed from whatever evidence exists with data_confidence lowered.
- **Visited set:** key tool calls on `(tool, normalised_arg)`. A duplicate call returns "already fetched, see step N" and counts against the budget, so the model gets a loud signal.
- **Explicit sufficiency checklist** driving the loop instead of the LLM's vibes: a list of required signals (`compliance_status`, `funding_stage`, `team_size_band`, `enterprise_motion`, `security_hiring`). The loop's first prompt tells the model which are `unknown`; it may only pick tools that could fill one of them (`reason` must name the missing signal). Loop ends when the unknown list is empty or the budget is exhausted.
- Keep the transcript compact: pass the *structured signal table* plus the latest tool result summary, not all raw pages (Pitfall 15).
- Log each iteration as `{step, action, arg, reason, targets_signal, result_summary, tokens}`.

**Warning signs:**
Same URL twice in a trace; run times vary 10x between companies; `MAX_STEPS` reached for most companies (means the sufficiency definition is wrong, not that the cap is too low).

**Phase to address:** Phase 3.

---

### Pitfall 7: Non-determinism makes decisions impossible to defend

**What goes wrong:**
Run it twice, company X scores 72 then 58. The LLM also does arithmetic ("total: 85") wrongly. A reviewer re-running the demo gets a different verdict than the report in front of them.

**Why it happens:**
LLM outputs sampled; LLM asked to produce the final score; no record of exact inputs.

**How to avoid:**
- **The LLM extracts signals; Python computes the score.** Rubric weights live in a `rubric.yaml`/dict in code. The LLM returns per-signal `{present: true|false|unknown, evidence_quote, url, confidence}`; code multiplies by weights, sums, and applies **hard gates** separately (see Pitfall 8). Same signals in = same score out, every time.
- Record-and-replay: cache every LLM response and fetch result on disk (Pitfall 5). `--replay` serves from cache so the demo run equals the golden run.
- Keep sampling parameters at the model's recommended defaults but record them; store model ID, prompt hash, timestamp in every trace entry.
- `report.md` is generated **by code from the trace** (templates), never by asking the LLM to summarise the run; an LLM summary is a fresh opportunity to hallucinate.

**Warning signs:**
Score deltas between identical runs; report text that mentions facts absent from the trace.

**Phase to address:** Phase 3 (scoring in code), Phase 7 (report from trace).

---

### Pitfall 8: Qualification false positives and misread "SOC 2" mentions

**What goes wrong:**
Typical misreads that make the filter look dumb in front of the Growth Lead:
- Company is **already certified** ("SOC 2 Type II" badge, trust center) and is scored as a prospect.
- Company uses a **competitor** (trust center hosted on Vanta, Drata, SafeBase, Secureframe, Thoropass, Scrut, Sprinto itself) and is scored as a prospect. Hosted trust-center links in the footer are a strong signal.
- "Our infrastructure is hosted on AWS, which is SOC 2 compliant", or a vendor-subprocessor list, is read as "the company has SOC 2".
- Blog post *about* SOC 2 (they sell compliance, or it is a thought-leadership post) counted as a need.
- Companies that are not ICP: non-SaaS agency, enterprise (Series D+, in-house GRC team of 10), tiny pre-product, or a **compliance competitor's own domain** in the list.
- Score inflation: LLM-assigned scores cluster at 70-85 so everything passes.
- Signals with no citation.

**Why it happens:**
Keyword-level reasoning; one overloaded "mentions SOC 2" boolean; LLM total scores; no negative examples in the test list.

**How to avoid:**
- Replace "mentions SOC 2" with a **compliance-state enum**: `none_visible | in_progress/planning (hot) | iso_only_needs_soc2 | soc2_type1 (upsell to Type II) | soc2_type2_current | multi_framework_mature | uses_competitor`. The extractor must also output `claim_scope: company_itself | infrastructure_vendor | unrelated_content`; only `company_itself` counts.
- **Hard gates before scoring**, recorded as the reason string in the report: competitor/compliance-vendor domain, not software/SaaS, `uses_competitor`, `soc2_type2_current + iso27001_current` (nothing left to sell), enterprise-scale headcount. Gate failure = `DISQUALIFIED: <gate>` regardless of score.
- Calibrate thresholds against the **test list**: it must contain at least 2 clear fits, 2 already-certified, 1 competitor/vendor, 1 too-big, 1 non-SaaS, 1 blocked-site. If the fits don't score clearly above the rest, adjust weights; don't ship a scorer that passes everything.
- Every `present: true` signal requires quote + url, verified by substring check (Pitfall 1); points awarded only for verified evidence. The report prints "points from verified evidence: X / unverified (ignored): Y".

**Warning signs:**
All test domains qualify; the competitor domain qualifies; the report cites a vendor-hosting sentence as the SOC 2 evidence; no company scores below 40.

**Phase to address:** Phase 3 (ICP definition + rubric + gates + test list design, ideally written before coding the loop).

---

### Pitfall 9: Gmail OAuth consent-screen traps (Testing mode, test users, token expiry) **[DAY-ZERO]**

**What goes wrong:**
Hours spent on `Error 403: access_denied` ("app has not completed Google verification / developer has not given you access"), `redirect_uri_mismatch`, `accessNotConfigured`, or a `token.json` that worked yesterday and now fails with `invalid_grant`.

**Why it happens (all HIGH confidence unless noted):**
- With publishing status **Testing**, only listed **test users** can consent: add your own Gmail address under Audience > Test users. Otherwise 403 access_denied.
- In Testing, **refresh tokens expire after 7 days.** A `token.json` minted last Tuesday is dead today. Generate it on demo day (today) and re-check the morning of the demo.
- The OAuth client type must be **Desktop app**; "Web application" gives `redirect_uri_mismatch` with `run_local_server`.
- The **Gmail API must be enabled** in the same Cloud project (`accessNotConfigured` 403 otherwise).
- Scope change (e.g., adding `gmail.readonly` later) with an old `token.json` = `insufficient authentication scopes` (403). Delete `token.json` and re-consent.
- Consent screen warns "Google hasn't verified this app": click Advanced > Go to app (unsafe). Normal for self-use. Unverified apps are capped at 100 users (irrelevant here). `gmail.send` is a *sensitive* (not restricted) scope. Publishing to "In production" without verification is an acceptable alternative for a self-only demo (removes the 7-day expiry for new tokens; you must re-consent after switching, per community reports).
- Windows Defender Firewall may prompt for Python the first time `run_local_server` opens a localhost listener; allow it.

**How to avoid:**
- Do the Cloud project, Gmail API enable, consent screen, test user, Desktop client, and a **standalone `auth.py`** that performs consent and writes `token.json`, as the very first task in Phase 1, in parallel with other work (it is the longest-lead item and the only one needing browser clicks).
- Request exactly one scope: `https://www.googleapis.com/auth/gmail.send`.
- `run.py` never opens a browser. It loads `token.json`, calls `creds.refresh(Request())` if expired, and on `RefreshError` **fails fast in preflight** with a clear message ("run `python auth.py`"), consistent with "no interactive prompts during a run".
- After any refresh, re-write `token.json` (`creds.to_json()`).

**Warning signs:**
403 with `access_denied` in the browser; `invalid_grant: Token has been expired or revoked`; works on one laptop, not another.

**Phase to address:** Phase 1 (consent + auth.py + first send), Phase 6 (preflight check).

---

### Pitfall 10: Accidentally emailing a real prospect

**What goes wrong:**
`contacts.csv` has real emails; a refactor, a copy-paste, or an LLM-generated "to" field sends cold email to an actual person from the user's real Gmail account. Irreversible and reputationally ugly.

**Why it happens:**
The recipient is read from the same row used for the greeting; the send function accepts an arbitrary `to`.

**How to avoid:**
- `send_email(subject, body)` takes **no `to` parameter**. Inside: `to = os.environ["SELF_EMAIL"]`; assert it equals the authenticated profile address (`users().getProfile(userId="me")` returns `emailAddress`); refuse to run if `SELF_EMAIL` unset.
- The prospect's address is used only in the report ("intended recipient") and optionally in a custom `X-Intended-Recipient` header or a one-line footer below the signature. It never goes in `To/Cc/Bcc`.
- Unit-test the send function with a mock to confirm the `To` header always equals self even when the contact row is hostile.
- Put `.env` example with `SELF_EMAIL=` and fail startup if the CSV's domain list contains the sender's own domain by mistake (optional).

**Warning signs:**
Any code path where the CSV email reaches a MIME header.

**Phase to address:** Phase 1 (design the signature of send), Phase 6 (assertions + test).

---

### Pitfall 11: Wrong PoC (contact missing, wrong seniority, stale, misspelled greeting)

**What goes wrong:**
- Domain has no row in `contacts.csv`: pipeline crashes, or the LLM invents a plausible name ("Hi Sarah").
- A 30-person startup gets the VP of Compliance (doesn't exist) or a 2,000-person company gets the CEO.
- The Apollo row is stale (person left; title outdated).
- Greeting wrong: "Hi CHIRAG," "Hi Dr.", "Hi John Smith," or mojibake ("Jos\u00e9" shown as "JosÃ©") from CSV encoding.
- Domain join fails: CSV has `https://www.acme.com`, input list has `acme.com`.

**Why it happens:**
Nobody defined the no-contact outcome; role logic left to the LLM; names derived from full strings; Excel/Notepad CSV encodings.

**How to avoid:**
- Explicit outcome `NO_CONTACT`: company can still qualify, report says "qualified, no contact in contacts.csv, email not drafted/sent", and the run continues. Never let the model produce a person not in the CSV.
- **LLM picks only a row id** from the candidate rows for that normalised domain; code validates the id exists. Prompt includes headcount band + a role priority table: `<50 staff: CEO/Founder, CTO` / `50-200: CTO, VP Eng, Head of Security` / `200+: Head of Security/InfoSec, GRC/Compliance lead, then VP Eng`. Reason string stored. Deterministic fallback in code if the model call fails (priority table order).
- `contacts.csv` columns: `domain, first_name, last_name, title, email, source_url, last_verified`. Use a **separate `first_name` column**; greeting = `first_name.strip()` as typed. Do not `.title()` (breaks "McDonald", "de la Cruz", "DeShawn"). Empty/initial-only first name = fall back to "Hi there" and flag in report.
- Read CSVs with `encoding="utf-8-sig"` (strips Excel BOM) and `newline=""`; normalise domains with one `normalise_domain()` used for both lists (strip scheme, `www.`, path, trailing dot, lowercase, `urlparse`, BOM, blank/`#` lines).
- Report shows `last_verified` and a "verify on LinkedIn before sending" flag if older than 90 days.

**Warning signs:**
Greeting in the sent email has a weird character; contact chosen for tiny company is "VP Engineering"; KeyError on a domain.

**Phase to address:** Phase 4.

---

### Pitfall 12: Generic, long, spammy, over-claiming email copy

**What goes wrong:**
The draft opens with "I hope this email finds you well", is 160 words, has three CTAs, bold text, an emoji, "Quick question!!!" as subject, a made-up stat ("we cut audit time by 80%"), or claims Sprinto can do things it cannot ("guaranteed SOC 2 in 2 weeks"). It names a hook that is a non-event ("I see you have a website"). LLM-isms ("I came across", "I noticed that", "streamline", "leverage", em-dash rhythm) make it read as machine-written. Placeholders leak (`[Your Name]`, `{{first_name}}`).

**Why it happens:**
Word limits in the prompt are advisory. The model is free to invent social proof. No validator.

**How to avoid:**
- **Validator in code, with up to 2 regeneration attempts that feed back the specific violations:** word count (body incl. sign-off) **hard cap 110 words, target 80-100** (the brief says under 120; leave margin because different counters disagree); exactly one question mark or one CTA sentence; no URLs/attachments/images/markdown (`**`, `#`, backticks, code fences); no `[` `]` `{{` `}}` placeholders; banned-phrase regex list (hope this finds you well, I came across, reaching out, touch base, synergy, leverage, game-changer, revolutionary, guarantee, 100%, free, act now, urgent); no exclamation marks; no emoji; first word after greeting is not "I".
- **Claims whitelist:** a `sprinto_facts.md` (3-6 facts copied from sprinto.com during ICP research: what it automates, which frameworks, typical value prop) is the only source of product claims in the prompt; instruct "no statistics, no customer names, no timeframes unless in the facts file". No competitor bashing.
- Subject: 3-7 words, sentence case, specific and non-clicky (e.g. "SOC 2 for {Company}'s enterprise deals"), no ALL CAPS, no `$`, `!`, "Re:/Fwd:" fakery, "Quick question". **Make subjects unique per company** (also avoids Gmail collapsing self-sent mails with identical subjects into one conversation thread in the inbox, which hides most of the demo emails).
- Hook rules: must be a specific, verifiable fact tied to a compliance consequence (hiring a Security Engineer, a new EU page implies GDPR, "Contact sales" enterprise tier plus no trust page). Pain points are phrased as likely/hypothesis ("teams at your stage often...") not assertions about their internals ("you are struggling with...").
- Signature is configured text (e.g., name from env + "Growth Lead, Sprinto"), appended by code, never generated.
- Optional but cheap: a second LLM "critic" pass that must quote the sentence in the email supporting each factual claim from the hook list; any unquoted claim = fail.
- Note in report that a production send would need unsubscribe and sender identity compliance (CAN-SPAM/GDPR/DPDP); out of scope because the recipient is always self.

**Warning signs:**
Word counts at 115+; hook line could be pasted into any company's email; two emails in a batch share the same opening sentence.

**Phase to address:** Phase 5 (drafting + validator), Phase 7 (spot-check batch for sameness).

---

### Pitfall 13: Gmail send mechanics (base64url, MIME, From, threading)

**What goes wrong:**
`400 Invalid value for ByteString`, "Invalid To header", mojibake in subject, body arrives blank, or the email sends but shows odd "From".

**How to avoid:**
- Use `email.message.EmailMessage`, set `To/From/Subject`, `msg.set_content(body)` (UTF-8 handled automatically, including non-ASCII subjects), then `raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()` and `service.users().messages().send(userId="me", body={"raw": raw}).execute()`. Standard base64 (not url-safe) or passing `bytes` instead of `str` are the usual errors.
- Gmail overwrites `From` with the authenticated account unless a verified send-as alias exists, so set `From` to the same address or omit it. A different From is silently rewritten or rejected.
- Send plain text only. HTML/links/tracking pixels raise spam scoring and are not needed.
- Log the returned message `id` and `threadId` in the trace as proof of send.
- After the first send, confirm it lands in **Inbox** (self-sent messages normally appear in both Sent and Inbox, but check once; if filtered, search `in:anywhere` / check All Mail).

**Warning signs:**
HttpError 400 on send; email in Sent but not Inbox; 10 emails collapsed into one conversation.

**Phase to address:** Phase 1 (send a hardcoded string end to end first), Phase 6.

---

### Pitfall 14: Scraping failures (SPA shells, bot blocks, redirects, cookie walls) and no graceful degradation

**What goes wrong:**
- JS-rendered SPA: `httpx.get` returns `<div id="root"></div>` plus a bundle; BeautifulSoup text is ~0 chars.
- Cloudflare/Akamai/Vercel challenge pages return 403/503 or 200 with "Just a moment...", which the extractor then "reads" as company content.
- `httpx` does **not follow redirects by default** (`follow_redirects=False`), so `acme.com` -> `www.acme.com` returns a 301 with an empty body.
- Cookie-consent overlays contribute their own text to the extraction; consent-only pages (EU).
- Trust content lives off-domain: `trust.acme.com`, `acme.safebase.io`, `app.vanta.com/acme/trust`, `trust.drata.com/...`. Pages at `/security` just link there.
- Careers pages are JS widgets (Greenhouse, Lever, Ashby, Workable).
- Non-HTML responses (PDFs, huge downloads), invalid TLS certificates, redirects to a parked or acquired-by domain.

**How to avoid (graceful-degradation ladder, each rung logged):**
1. `httpx.Client(follow_redirects=True, timeout=10, headers=browser-like UA + Accept-Language, max_redirects=5)`; record `final_url`; flag if the final registered domain differs from the input (acquisition/parked).
2. Reject non-`text/html`; stream with a byte cap (~1-2 MB).
3. **Empty-shell detection:** visible text < ~400 chars, or contains "enable JavaScript"/"Just a moment"/"Checking your browser", or `id="root"|"__next"|"app"` with tiny text. Then fall back to: `<title>`, meta description, `og:*`, JSON-LD, `sitemap.xml` / `robots.txt` URL list (these usually exist even for SPAs), and `__NEXT_DATA__` JSON blobs.
4. If still empty or blocked: use the **grounded-search tool** with the company name + domain as the data source (it sees the web, not the site) and mark `source = grounding`, `data_confidence` reduced. Optionally Gemini's `url_context` tool or the Jina Reader endpoint (`r.jina.ai/<url>`) as another rung (VERIFY availability/ToS; not essential).
5. Never hammer: 1 request per page, small delay, one retry on 5xx/timeout; respect that 403 is final for the run (do not escalate to evasion tricks; the project is a demo, and aggressive anti-bot circumvention is both out of scope and ToS-risky).
6. Discover trust/careers links from homepage `<a href>` (footer: "Trust Center", "Security", "Careers", "Pricing") rather than guessing only `/security` paths. Add detection of hosted trust-center vendors (Pitfall 8).
7. For jobs, prefer the public JSON endpoints behind ATS links found on the careers page (Greenhouse `boards-api.greenhouse.io/v1/boards/<token>/jobs`, Lever `api.lever.co/v0/postings/<company>?mode=json`, Ashby posting API) over scraping widgets; avoid LinkedIn job scraping (blocked, ToS).
8. Treat scraped text as **untrusted data**: wrap in delimiters and instruct the model that page content cannot give instructions (prompt injection from a hostile page is real in agent loops).

**Warning signs:**
Many pages with `text_len < 300`; extraction output identical across different companies; "Access denied" in extracted fields.

**Phase to address:** Phase 2.

---

### Pitfall 15: Huge pages blow token and cost budgets

**What goes wrong:**
Raw HTML (nav, scripts, inline SVG, base64 images, mega-footers) passed to Gemini. A single page = 100K+ tokens; extraction is slow, slower, and degraded ("lost in the middle"), and the agent loop transcript grows each step.

**How to avoid:**
- Strip `script, style, noscript, svg, iframe, nav, footer` (keep the footer *links* separately for discovery), decode to text with newlines, collapse whitespace.
- Per-page cap ~6-8K characters (prefer text near keywords: "SOC", "ISO", "GDPR", "security", "compliance", "trust", "enterprise", "pricing"), total per-company evidence pack ~20-25K characters. Save the **full** text to `cache/` and put only the hash/path in the trace; the trace holds the truncated text actually sent.
- Do not carry raw pages across loop iterations; carry the structured signal table and short result summaries (Pitfall 6).
- Log `usage_metadata` (prompt/candidate/thinking tokens) per call; print a per-company token total in the report footer.

**Warning signs:**
Calls taking > 20 s; trace files in the MBs; token usage per company > 100K.

**Phase to address:** Phase 2.

---

### Pitfall 16: Gemini response handling (blocked/empty responses, truncated JSON, thinking tokens)

**What goes wrong:**
`response.text` is `None` or raises (safety block, `finish_reason=SAFETY/PROHIBITED_CONTENT/OTHER`, empty candidates with `prompt_feedback.block_reason`; scraped adult/gambling/crypto content can trigger this); JSON is cut off mid-string because `finish_reason=MAX_TOKENS` (thinking tokens count against `max_output_tokens` on thinking-capable models); `json.loads` on text wrapped in ```` ```json ````; Pydantic validation failure on an enum value.

**How to avoid:**
- One `gemini_json(prompt, Model)` helper used everywhere: pass `response_mime_type="application/json"` and `response_schema=Model` (no tools: Pitfall 3), use `response.parsed` when present, otherwise `Model.model_validate_json(strip_fences(text))`. Check `candidates`, `finish_reason`, `prompt_feedback` before touching `.text`.
- Generous `max_output_tokens` (e.g., 4-8K) and the lowest sensible thinking setting for extraction (thinking is not needed for field extraction; keep some for qualification/drafting).
- On parse/validation error: one repair retry that includes the validation error text; on second failure, record `step_failed` with raw response in trace and continue the batch.
- Treat `finish_reason != STOP` as failure for that step, logged distinctly (`LLM_BLOCKED`, `LLM_TRUNCATED`).

**Warning signs:**
`AttributeError: 'NoneType'`, `JSONDecodeError: Unterminated string`, sporadic failures on specific companies only.

**Phase to address:** Phase 1 (helper), reused by Phases 2-5.

---

### Pitfall 17: Secrets leaked to git (credentials.json, token.json, .env, traces)

**What goes wrong:**
`git add .` commits `.env` (Gemini key), `credentials.json` / `client_secret_*.json` (OAuth client secret), `token.json` (refresh token granting send-as-you on Gmail). The repo already has `.git` initialised in `E:\Sprinto Case` with commits, so a later `git add .` is one keystroke from disaster. Secondary leaks: API key embedded in exception text/URL logged to the trace; real contacts' emails and Apollo-sourced PII committed in `contacts.csv` and traces.

**How to avoid:**
- First action in Phase 1, before creating any secret file: write `.gitignore` containing `.env`, `.env.*` (but allow `!.env.example`), `credentials.json`, `client_secret*.json`, `token.json`, `*.pem`, `.venv/`, `__pycache__/`, `cache/`, and decide explicitly whether `contacts.csv` and `runs/` are ignored (recommended: ignore real `contacts.csv`, commit `contacts.example.csv`; commit one golden sanitised run if the case wants it submitted).
- Verify with `git check-ignore -v .env credentials.json token.json` and `git status` before the first `git add`.
- Download the OAuth JSON into the project folder immediately under the ignored name; delete it from `Downloads\`.
- Redact in logging: never log request headers/URLs containing `key=`; wrap exceptions through a `redact()` that masks the key value from env.
- If a secret is committed: rotate the Gemini key, delete and recreate the OAuth client, revoke the token at myaccount.google.com/permissions; history rewrite alone is not enough.

**Warning signs:**
`git status` shows `.env`/`token.json` as untracked-not-ignored; a trace file containing "AIza".

**Phase to address:** Phase 1.

---

### Pitfall 18: Windows environment traps (encoding, console, paths, venv)

**What goes wrong:**
- `UnicodeEncodeError: 'charmap' codec can't encode character` when printing names/emoji or writing the report: Windows defaults to cp1252 for console and for `open()` without `encoding`.
- Report/trace shows mojibake when opened (written in cp1252, read as UTF-8 or vice versa); `json.dump` with `ensure_ascii=True` hides it in traces but makes quotes unreadable.
- Notepad-saved `.env` with BOM breaks the first key (`\ufeffGEMINI_API_KEY`); CRLF inside values.
- `Activate.ps1` blocked by execution policy; `python` resolves to the Microsoft Store stub; `pip` mismatched with `python`.
- Project path `E:\Sprinto Case` contains a **space**: unquoted paths in subprocess calls break; hard-coded `/` or `\` string concatenation.
- Long LLM/HTTP waits and a console that shows nothing for 60 s looks like a hang in the demo.

**How to avoid:**
- Set `PYTHONUTF8=1` (and `PYTHONIOENCODING=utf-8`) in the shell, and in code `sys.stdout.reconfigure(encoding="utf-8")` at the top of `run.py`; **always** pass `encoding="utf-8"` to `open()`/`Path.read_text/write_text`; `json.dump(..., ensure_ascii=False, indent=2)`.
- `load_dotenv(encoding="utf-8-sig")` or create `.env` in an editor as UTF-8 without BOM; strip values.
- Use `pathlib.Path` everywhere, anchored on `Path(__file__).parent`, not the CWD (the demo may be run from another directory).
- Call `.\.venv\Scripts\python.exe -m pip ...` / `python -m ...` directly instead of activating; or `Set-ExecutionPolicy -Scope Process Bypass`. Prefer `py -3` over `python` if the Store alias interferes.
- Per-step progress lines printed with ASCII-safe prefixes (`[1/10] acme.com: scrape ok (4 pages)`), flushed, so the demo audience sees movement; use `rich` only if it already works on this terminal.
- Avoid emoji in output.

**Warning signs:**
Crash only when a company name has an accent; works in VS Code terminal, fails when run from Task Scheduler/cmd.

**Phase to address:** Phase 1.

---

### Pitfall 19: A single failure kills the batch; traces lost on crash; unattended run stalls

**What goes wrong:**
Company 4 raises an exception; companies 5-10 never run and the trace for 1-3 is only written at the end (lost). An uncaught `input()` or auth prompt blocks "unattended". A network blip in the live demo shows a traceback.

**How to avoid:**
- Per-company `try/except` at the pipeline boundary; any failure becomes `outcome = ERROR(step, message)` in the trace and the report, and the loop continues. The CLI exits nonzero only for preflight failures.
- Write the trace **incrementally** (append/overwrite JSON after each step) so partial runs are inspectable.
- Per-company outcomes enumerated: `SENT`, `DISQUALIFIED(gate)`, `BELOW_THRESHOLD`, `INSUFFICIENT_DATA`, `NO_CONTACT`, `ERROR(step)`. The report has a one-table summary at the top so the "filter works" story is visible in 10 seconds.
- Sent ledger (`runs/sent.jsonl` keyed by `run_id+domain`): on `--resume`, skip already-sent domains so a crash-and-rerun does not send duplicates. (Duplicates only hit the user's own inbox, so this is convenience, not safety.)
- No `input()` anywhere in `run.py`.

**Warning signs:**
`report.md` only exists if everything succeeded.

**Phase to address:** Phase 7 (but code the try/except boundary in Phase 1's skeleton).

---

### Pitfall 20: Demo-day failures (network, quota, token expiry, cold cache, over-scoping)

**What goes wrong:**
Live-run risk list: classroom Wi-Fi blocks/slow-rolls requests (TLS interception shows up as `CERTIFICATE_VERIFY_FAILED`); Gemini 503/429; token expired; a target site changed overnight and now blocks; the agent takes 8 minutes for 10 companies; the live send arrives in the inbox but the audience cannot see it because Gmail grouped it into one thread; a feature half-built in the last 10 minutes breaks the previously working skeleton.

**How to avoid / pre-cache checklist (do the evening before / 30 minutes before):**
- Run the full pipeline end-to-end once on the final test list; commit/keep the result as `runs/golden/` (trace + report.md + the sent email in the inbox). The cache dir (`cache/`) from that run lets `--replay` reproduce the exact output offline in seconds.
- `--preflight`: Gemini model ping (primary + fallback), Gmail token refresh + `getProfile`, contacts.csv covers all domains, `.env` keys present, network reachable. Run it on the demo network, not just at home. Have a phone hotspot ready.
- Regenerate `token.json` on demo day (Pitfall 9) and check it.
- Keep the working skeleton on a git branch/tag (`walking-skeleton-ok`); freeze features 15 minutes before the session.
- Demo script: show `report.md` (rejections and reasons first), one trace JSON, the email in the inbox; run 1-2 domains live with cache warm, the rest from the golden run.
- Do not demo the free-tier quota edge: use cache and the pre-run.

**Phase to address:** Phase 7, with the skeleton discipline starting in Phase 1.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| LLM returns the final score | Skips rubric code | Unreproducible, un-auditable; inflated scores | Never (code computes score) |
| Passing raw HTML to Gemini | No parser code | Token blow-up, junk extraction | Never |
| One mega-prompt for steps 2-6 | Fastest to write | Can't trace which step caused an error; no per-step caching | Only inside Phase 1's skeleton, split before Phase 3 |
| Hardcoding `gemini-2.5-flash` | Works from memory | Deprecated, shuts down 2026-12-01 | Never; use env var |
| Skipping disk cache | Less code | Burns free-tier quota, slow reruns, non-deterministic demo | Never (cache is ~30 lines) |
| Ignoring unknown/blocked as "false" | Simpler schema | False positives on hot-lead score | Never |
| `.title()` on names | Pretty greetings | Breaks McDonald/de la Cruz | Never; use the CSV value as typed |
| Gemini-native function calling for the loop | "Idiomatic" | Tool-mixing constraints, hard-to-log steps | Only if verified on the chosen model AND time allows (not for this build) |
| Skipping unit tests for validators | Saves 10 minutes | Silent regressions in copy and recipient safety | Acceptable for everything except `send_email` recipient and word-count validator, which get tests |
| Committing `contacts.csv` with real names/emails | Easy to submit | PII in repo history | Only a sanitised example |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Gemini grounding | Combining `google_search` with schema/functions on a model that doesn't support it | Two-call pattern (grounded text then structured parse); verify model support with preflight |
| Gemini structured output | Relying on `maxLength`/`minLength`; deep or union-heavy schemas | Flat Pydantic with enums; enforce lengths in code |
| Gemini SDK (`google-genai`) | Reading `response.text` without checking finish reason; thinking tokens eating `max_output_tokens` | Central helper; generous output budget; check `candidates` |
| Gemini quotas | Treating limits as per-key; assuming reset at local midnight | Per-project; resets at midnight Pacific = 13:30 IST today |
| Gmail API | Wrong client type, API not enabled, test user not added, `token.json` older than 7 days in Testing mode | Desktop client, enable API, add test user, mint token on demo day |
| Gmail API | Standard base64 / bytes in `raw` | `urlsafe_b64encode(msg.as_bytes()).decode()` |
| Gmail inbox | Identical subjects collapse into one thread | Unique subject per company |
| httpx | Redirects not followed by default; no timeout; no size cap | `follow_redirects=True`, `timeout=10`, stream with byte cap |
| Greenhouse/Lever/Ashby | Scraping JS widgets | Hit the public JSON job endpoints linked from the careers page |
| Hosted trust centers | Missing the Vanta/Drata/SafeBase footer link | Detect those vendor hostnames; they imply "has a trust center" and possibly "uses competitor" |
| python-dotenv on Windows | BOM from Notepad breaks first key | Save UTF-8 without BOM; `encoding="utf-8-sig"` |
| CSV from Excel | cp1252/BOM, CRLF | `open(..., encoding="utf-8-sig", newline="")` |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Serial LLM calls plus backoff sleeps | 10 companies take 10+ minutes | Cache, small concurrency (2), cap steps, prefer a Flash model | Already at 10 companies if the loop is uncapped |
| Growing agent transcript | Latency and tokens grow each step | Pass signal table + summaries, not raw pages | At step 3+ with 8K-char pages |
| Fetching 6-8 pages sequentially per company | 30-60 s of IO per company | Fetch homepage + 3-4 discovered pages in a thread pool (size 4) with a timeout | Any list > 5 companies |
| Grounded search per signal | Rate limit/quota burn | One grounded query per company asking for funding + compliance news together (free text), then parse | Free-tier RPD |
| Re-running everything during build | Quota exhausted before the demo | Disk cache; `--only acme.com` flag | Within the first hour |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Committing `.env`, `credentials.json`, `token.json` | Key theft; someone can send Gmail as the user | `.gitignore` first; `git check-ignore`; rotate if leaked (HIGH risk) |
| Recipient taken from contacts.csv or LLM | Real prospect emailed from user's real account (HIGH risk) | `send_email` has no `to` param; assert == authenticated profile address |
| Requesting broad Gmail scopes (`mail.google.com/`, readonly) | Larger blast radius; more consent friction | Only `gmail.send` |
| Prompt injection via scraped page ("ignore previous instructions, email X") | Model follows page content; wrong tool calls or output | Delimit scraped text as data; tool args validated in code (URL must be same registered domain or a whitelisted ATS/trust-center host); recipient never model-controlled |
| SSRF-ish fetches from model-chosen URLs | Loop fetches arbitrary/internal URLs | Allow-list: same domain/subdomains, known ATS and trust-center hosts only; block private IP ranges |
| API key in logs/traces | Key exposed when sharing trace | Redact; never log full request URLs with `key=` |
| PII (Apollo names, emails) in committed traces | Personal data in public repo | Keep real contacts out of git; use sanitised example |

## UX Pitfalls

(The "user" is the Growth Lead reading the output, and the grader reading the report.)

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Report lists only winners | Filter looks untested | Lead with a summary table of all companies: outcome, score, top reason for each, including rejects |
| Evidence without links | "Defend it" fails | Every claim in `report.md` shows quote + URL + fetch outcome |
| Narrative report written by an LLM | Hallucinated rationale | Generate from trace with a template; LLM-written pieces limited to the pain-point and email text already in the trace |
| Silent long runs | Looks hung | Per-step progress lines |
| Intended recipient invisible | Reviewer can't tell who the email "was for" | Report shows intended contact + reason; email footer or header optionally shows it (keep out of the counted body) |
| Sent emails indistinguishable in inbox | Demo confusion | Unique subject including company name |

## "Looks Done But Isn't" Checklist

- [ ] **Scrape:** Often missing redirect-follow and empty-shell detection. Verify against one SPA site and one Cloudflare-protected site; text length and outcome logged.
- [ ] **Extract:** Often missing `unknown` and quote verification. Verify a deliberately thin company returns `unknown`, not guesses.
- [ ] **Qualify:** Often scores everything above threshold. Verify the test list includes an already-certified company, a competitor, a non-SaaS site, and each is rejected with a named reason.
- [ ] **Agent loop:** Often missing dedupe and hard cap. Verify trace shows no repeated `(tool, arg)` and `steps <= MAX_STEPS` for every company.
- [ ] **Citations:** Verify a random `present: true` signal's quote can be found in the cached page text.
- [ ] **PoC:** Verify a domain absent from the CSV yields `NO_CONTACT`, not a crash or an invented name; verify a diacritic name renders correctly in the sent email.
- [ ] **Draft:** Verify word count <= 110 (by code), one CTA, no placeholders, no unsupported stats, subject unique, signature from config.
- [ ] **Send:** Verify `To` header equals self for every sent message even with a hostile CSV email; verify message in Inbox, not only Sent.
- [ ] **Gmail auth:** Verify a fresh process with an existing `token.json` sends without opening a browser; verify token age (< 7 days if Testing).
- [ ] **Secrets:** `git ls-files | findstr /i "env token credentials client_secret"` returns nothing.
- [ ] **Trace/report:** Verify a deliberately failing company appears in the report as `ERROR(step)` and the batch continued; verify report generated from trace deterministically (re-generate = identical).
- [ ] **Windows:** Run once from a fresh PowerShell in a different CWD with a non-ASCII name in contacts.csv.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| `token.json` expired / invalid_grant | LOW | Delete `token.json`, run `auth.py`, re-consent (needs browser, 1 min). If in Testing, consider publishing to production for self-use |
| 429 mid-demo | LOW | Backoff then fallback model; else `--replay` from cache/golden run |
| Model ID 404 | LOW | Change `GEMINI_MODEL` in `.env`; rerun preflight |
| Grounded call returns truncated/garbled JSON | LOW | Already isolated by two-call pattern; reparse in Call B |
| Site blocked live | LOW | Cache/golden run; mark `BLOCKED` and use grounded fallback |
| Secret committed | HIGH | Rotate Gemini key; delete/recreate OAuth client; revoke token in Google account; then purge history |
| Email sent with fabricated hook | MEDIUM | Add the failing claim to the validator/hook-id constraint; regenerate; only self-inbox affected in this project |
| Everything qualifies / nothing qualifies | MEDIUM | Re-tune weights using the test list; check unknown-handling and gates first |
| Wrong contact picked | LOW | Fix priority table; re-run Phase 4 step from cache |
| Time overrun | MEDIUM | Cut scope in this order: job-postings tool, critic pass, concurrency; never cut the cache, hard caps, or send assertion |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1 Fabricated personalization | Phase 2 (schema, quote check), Phase 5 (hook ids) | Substring check passes for all `present` signals; hook_id always in candidate list |
| 2 Unreachable = no signal | Phase 2, Phase 3 | Fetch outcome table in report; blocked site yields `INSUFFICIENT_DATA`/low confidence |
| 3 Grounding/structured/function-calling mix | Phase 1 (smoke test), Phase 3 | Two-call pattern in code; grounded call has no schema |
| 4 Model ID deprecation | Phase 1 | Preflight passes for primary and fallback |
| 5 Quota / 429 | Phase 1 (cache, retry), Phase 7 (pacing) | Second identical run makes 0 API calls |
| 6 Agent loop runaway | Phase 3 | Every trace: steps <= cap, no duplicate tool calls |
| 7 Non-determinism | Phase 3 (score in code), Phase 7 (report from trace) | Replay run yields byte-identical report |
| 8 Qualification false positives | Phase 3 | Test list rejects certified/competitor/non-SaaS with named gates |
| 9 Gmail OAuth traps | Phase 1, Phase 6 | `auth.py` run on demo day; preflight refresh OK |
| 10 Emailing real prospects | Phase 1 (API shape), Phase 6 (test) | Unit test: To == self regardless of CSV |
| 11 Wrong PoC / greeting | Phase 4 | NO_CONTACT path tested; diacritic name renders correctly |
| 12 Spammy/over-claiming copy | Phase 5 | Validator passes; facts whitelist enforced; subjects unique |
| 13 Gmail send mechanics | Phase 1, Phase 6 | First send arrives in Inbox, `messageId` logged |
| 14 Scraping failures | Phase 2 | Fixtures: SPA, Cloudflare, redirect, soft-404 all degrade as designed |
| 15 Token/cost blow-up from pages | Phase 2 | Per-company token total printed; below budget |
| 16 Gemini response handling | Phase 1 (helper) | Forced-failure test (bad schema) produces logged `step_failed`, batch continues |
| 17 Secrets in git | Phase 1 (before first commit) | `git check-ignore` + `git ls-files` checks clean |
| 18 Windows encoding/path | Phase 1 | Run from different CWD with non-ASCII name |
| 19 Batch resilience | Phase 1 (try/except skeleton), Phase 7 | Injected failure on one domain; others complete; partial trace preserved |
| 20 Demo-day failure | Phase 7 | Golden run saved; preflight on demo network; hotspot ready |

## Phase-Specific Warnings (for roadmap flags)

| Phase | Research flag | Note |
|-------|---------------|------|
| 1 Walking skeleton | Do OAuth consent setup + `.gitignore` + model preflight first; send one hardcoded email | Gmail setup is on the critical path and is not "Phase 6" work; only the production-quality send logic is |
| 2 Scrape/extract | Standard patterns; test on 3 fixtures (SPA, Cloudflare, normal) | Typed fetch outcomes and quote verification are the key designs |
| 3 ICP + qualify loop | Needs deeper thought on ICP wording and gates, not library research | Write ICP and rubric before coding the loop; include negatives in the test list |
| 4 PoC | Standard | Define NO_CONTACT and role-by-size table |
| 5 Pain points + draft | Prompt iteration time; budget 20 min | Validator with regenerate-on-violation |
| 6 Gmail send | Mostly done in Phase 1 | Add recipient assertion, ledger, unique subjects |
| 7 Batch/trace/report | Report-from-trace, golden run, replay | Reserve the last 20 minutes for the golden run and preflight |

## Sources

- Gemini API deprecations page (official, fetched 2026-11-03 via `aistudio.google.com/docs/deprecations`): `gemini-2.5-flash` deprecated, shutdown 2026-12-01; current IDs `gemini-3.6-flash`, `gemini-3.8-flash`; alias routing for 3.5/3.7. Confidence MEDIUM-HIGH (summarised page; confirm in AI Studio).
- Gemini structured output docs (official, fetched 2026-11-03 via `aistudio.google.com/docs/structured-output`): structured output + built-in tools (Google Search, URL context, code execution, file search, function calling) combinable on Gemini 3-series (preview); `minLength/maxLength/uniqueItems` stripped; large/nested schemas rejected with 400.
- Gemini rate-limits docs (official, fetched 2026-11-03): limits per project; RPD reset at midnight Pacific; Gemini 3+ Search grounding default 1,500 RPD per project; free-tier numeric limits not in the page text (use AI Studio rate-limit view).
- Google AI developers forum threads on grounding + JSON incompatibility (older models), Gemini 3.5/3.6 Flash grounded JSON starting mid-sentence, empty grounding metadata with structured output (community reports, MEDIUM/LOW; two-call workaround confirmed in thread): discuss.ai.google.dev (tag: grounding).
- Vercel AI SDK issue on Gemini 3 structured output + tools support: github.com/vercel/ai/issues/11599 (LOW-MEDIUM).
- Google OAuth docs/community on Testing mode: refresh tokens expire after 7 days; publishing to In production removes this; unverified apps capped at 100 users (HIGH, widely documented; confirmed via search 2026-11-03).
- Domain knowledge (HIGH): Gmail `users.messages.send` raw base64url; Desktop-app OAuth client for `InstalledAppFlow`; httpx `follow_redirects=False` default; Windows cp1252 default encoding for console/`open()`; Greenhouse/Lever/Ashby public job-board endpoints.
- Reasoning (flagged as derived): midnight Pacific = 13:30 IST on 3 Nov 2026 (US DST ended 1 Nov 2026).

---
*Pitfalls research for: AI-driven B2B cold-outreach pipeline (Sprinto Outbound Autopilot)*
*Researched: 2026-11-03*
