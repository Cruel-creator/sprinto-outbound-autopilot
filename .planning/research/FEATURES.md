# Feature Research

**Domain:** AI-driven B2B cold-outreach pipeline for a compliance-automation vendor (Sprinto: SOC 2 / ISO 27001 / GDPR / HIPAA)
**Researched:** 2026-11-03
**Confidence:** MEDIUM overall (Sprinto facts and test-domain facts HIGH/MEDIUM, fetched live; persona pain points and email benchmarks MEDIUM, mostly vendor-authored sources; competitor trust-center fingerprints LOW-MEDIUM)

> Read order for downstream consumers: Part A (ICP rubric, copy into the qualifier config) -> Part B (PoC + pain points) -> Part C (email rules) -> Part D (test domains) -> Part E (pipeline feature landscape: table stakes / differentiators / anti-features).

---

# PART A. ICP DEFINITION AND QUALIFICATION RUBRIC

## A.1 What Sprinto actually sells, and to whom (evidence for the ICP)

| Fact | Source | Confidence |
|------|--------|------------|
| Positioning today: "Autonomous Trust Platform for Compliance, Risk & GRC". Originally "compliance automation for SaaS companies". | sprinto.com homepage title | HIGH |
| "Trusted by 4,000+ companies worldwide" (was "1,000+" in April 2024). | sprinto.com/customers; TechCrunch 2024-04-09 | HIGH (self-reported) |
| Customers in ~75 countries, **most in the US and Europe**. HQ/engineering in India. | TechCrunch 2024-04-09 | HIGH |
| Founder says the expansion target is "digitally native, tech-enabled" companies, not only tech-first SaaS. So fintech, healthtech, HR-tech etc. are in-ICP. | Girish Redekar quote, TechCrunch | HIGH |
| Series B $20M (Apr 2024, Accel; Elevation, Blume). Series A $10M (Feb 2022). ~200 staff in 2024. Names Vanta and Drata as the key competitors. | TechCrunch; Entrackr; Inc42 | HIGH |
| Plans: **Foundation** (startups pursuing a first certification, 25+ frameworks, 200+ digitised frameworks, guided onboarding), **Growth** (compliance at scale), plus **Enterprise modules** (Continuous Compliance, Enterprise TPRM, ERM, Trust Management) for mature GRC teams. | docs.sprinto.com plans-and-pricing | HIGH |
| Pricing is quote-based. Third-party estimates (low confidence): ~$6-10k/yr single-framework startup; ~$10-15k for 2-3 frameworks; $20-25k+ enterprise; each extra framework adds ~$3-8k. Vanta/Drata are estimated at $15-50k/yr. Audit fees are separate. | Orbiq (competitor-authored), Spendflo, ComplyJet via search | LOW-MEDIUM |
| Proof points Sprinto uses: GeoIQ SOC 2 + ISO 27001 in 3 months; StepSecurity SOC 2 in 4 weeks; Capptions ISO 27001 "3x faster than a consultant"; 160+ integrations (HR, IT, engineering). | sprinto.com customer stories; TechCrunch | MEDIUM (self-reported) |
| Sprinto itself is weaker for: strict EU data-residency buyers, DORA/NIS2-native needs, very small teams that balk at opaque quote-based pricing. (Written by a competitor, so treat as hypothesis.) | Orbiq | LOW |

## A.2 Competitor positioning (so the qualifier can recognise "already using someone")

| Competitor | Positioning (as described in sources) | Implication for qualifier |
|------------|---------------------------------------|---------------------------|
| **Vanta** | Market leader; startup-friendly to mid-market; huge trust-center footprint. G2 reviewer mix ~55% small / 38% mid. ~$15-50k/yr (est). | A live Vanta trust center = already bought. Hard-to-win, treat as DQ-ish. |
| **Drata** | Enterprise-leaning, pricey, deep controls. Trust Center now partly via SafeBase. | Same as Vanta. |
| **Secureframe** | Simple, skews small (G2: ~67% small-business reviews), less customisable. | Same. Often switched from at renewal. |
| **Thoropass** | Bundles software with an in-house audit (from training knowledge, not verified this session). | Same. Switch angle is audit cost/lock-in. |
| **Scrut** | Risk-first, bundles hands-on service, good for lean teams (Sprinto-authored claim). | Same. |
| **Sprinto** | Cost-effective for global SMB and growth-stage; multi-framework; guided onboarding. | An existing Sprinto trust center (Sprinto docs: `<company>.trust.site`, or custom domain) = **existing customer, never email**. |

Sources: sprinto.com/blog/sprinto-competitors, g2.com compare pages, guptadeepak.com, drata.com compare pages (all vendor-authored; framing is self-serving, MEDIUM-LOW).

## A.3 ICP in one paragraph

> A **B2B software company (SaaS, dev-tools, AI, fintech/healthtech infrastructure) of ~20-500 people, seed-extension to Series C**, that is **selling (or starting to sell) to mid-market and enterprise buyers** (enterprise tier, "contact sales", big-logo customers, security/DPA/BAA language), and that shows a **certification gap or in-flight compliance effort** (no SOC 2/ISO badge, SOC 2 "in progress"/Type I only, GRC or security hires, fresh funding, US/EU expansion triggering GDPR). Not already fully certified on a competitor platform, not already a Sprinto customer, not a mega-enterprise, not non-software.

Why the gap + upmarket combination matters: enterprise procurement is the dominant buying trigger for SOC 2; buyers increasingly ask during discovery calls; questionnaires and security reviews add roughly 2-4 weeks to cycles and kill deals when failed; Type 1 is the common stopgap while Type 2 runs. (trycomp.ai/when-to-get-soc-2; Thoropass, Secureframe and Scrut guides; vendor-authored, MEDIUM.) A compliance gap *without* enterprise pull is a weak trigger (e.g., an SMB-focused product has no buyer asking for the report), so the rubric gates on it.

## A.4 Weighted rubric (0-100), copy-pasteable

Four blocks: **A Firmographic (30)**, **B Upmarket pull (25)**, **C Compliance trigger (35)**, **D Fit modifiers (10)**. Hard disqualifiers run first and short-circuit to score 0 with a stated reason. Caps run after scoring.

```yaml
# icp_rubric.yaml  (version 1)
version: 1
threshold:
  qualify: 60        # >= 60 -> proceed to PoC/pain/draft
  a_list: 75         # >= 75 -> tag "priority" in report
  maybe: 45          # 45-59 -> "nurture", do NOT email, show in report
  # < 45 -> reject
unknown_policy: "unknown signals score 0 but widen the [lo,hi] score bounds; agent loop fires only while threshold lies inside [lo,hi] (max 4 tool calls/company)"

hard_disqualifiers:            # any hit -> decision=DISQUALIFIED, score=0
  - id: not_software
    rule: "No software product/platform (D2C brand, services/agency, consultancy, retail, manufacturing, media)."
    detect: "Extraction field product_type not in {saas, platform, api, devtool, ai_software, fintech_infra, healthtech_software}"
  - id: existing_sprinto_customer
    rule: "Trust/security page hosted by Sprinto or mentions Sprinto as compliance partner."
    detect: "Any link/iframe/text matching '*.trust.site', 'sprinto.com' on /trust, /security, footer"
  - id: too_large
    rule: "Headcount >= 2000, or public mega-cap, or Fortune-500-scale brand."
    detect: "Extraction headcount + grounded search (LinkedIn size bucket, Wikipedia)"
  - id: too_small
    rule: "< 8 people AND no paying customers visible (pre-seed / side project)."
    detect: "Headcount < 8 and no pricing page / customers page / logos"

caps:                          # applied after summing
  - id: no_upmarket_pull
    when: "block_B < 8"
    cap: 55
    why: "A certification gap without enterprise buyers is not a trigger (SMB-focused products rarely get asked for SOC 2)."
  - id: fully_certified
    when: "SOC 2 Type II present AND (ISO 27001 present OR competitor trust center listing >=2 frameworks)"
    cap: 40
    tag: "switch_or_expand_candidate"   # only surfaced in report; see A.6
  - id: low_evidence
    when: "count(unknown signals) >= 4 after agent loop"
    effect: "confidence=LOW in report; decision unchanged"

signals:
  # ---------- A. FIRMOGRAPHIC (30) ----------
  - id: A1_b2b_software
    weight: 10
    detect: "Extraction: pricing/demo/login/API docs, 'platform', customers are businesses"
    scoring: {b2b_saas_or_devtool_or_ai: 10, b2b_tech_enabled_fintech_health_hr: 6, mixed_b2b2c: 3, b2c: 0}
  - id: A2_stage
    weight: 10
    detect: "Gemini + Google Search grounding: 'COMPANY funding round stage amount investors'. Cross-check Crunchbase/Tracxn/Inc42/Entrackr snippet."
    scoring: {series_a_to_c: 10, seed_with_top_tier_or_yc_or_>=3M: 6, seed_unknown_or_bootstrapped_with_traction: 4, series_d_plus_or_late: 2, none_found: 0}
  - id: A3_headcount
    weight: 10
    detect: "About/careers page ('We are 120 people'), LinkedIn size bucket via grounded search, count of open roles"
    scoring: {"30-300": 10, "15-29_or_301-600": 6, "8-14_or_601-1500": 3, "other": 0}

  # ---------- B. UPMARKET PULL (25) ----------
  - id: B1_enterprise_motion
    weight: 8
    detect: "/pricing or nav: 'Enterprise' tier, 'Contact sales', 'Talk to sales', SSO/SAML/SCIM/audit-logs/RBAC listed as plan features"
    scoring: {enterprise_tier_plus_contact_sales: 8, one_of_them: 5, demo_only: 2, self_serve_only: 0}
  - id: B2_enterprise_logos
    weight: 8
    detect: "/customers, homepage logo strip, case studies: named large/regulated customers (banks, F500, healthcare, public sector); Gemini reads alt text / filenames"
    scoring: {>=3_enterprise_logos: 8, 1-2: 5, only_smb_or_startup_logos: 1, none_visible: 0}
  - id: B3_sensitive_data_or_regulated_buyers
    weight: 5
    detect: "Handles PII/PHI/financial/HR/LLM prompts data, sells to BFSI/healthcare/gov; 'data residency', 'in-VPC', 'on-prem' offerings"
    scoring: {strong: 5, moderate: 3, weak: 1, none: 0}
  - id: B4_procurement_friction_markers
    weight: 4
    detect: "Footer/legal: DPA, BAA, subprocessor list, 'request security docs', 'security review', 'vendor questionnaire', self-hosted/air-gapped option"
    scoring: {>=2_markers: 4, 1_marker: 2, none: 0}

  # ---------- C. COMPLIANCE TRIGGER (35) ----------
  - id: C1_certification_gap
    weight: 12
    detect: "Fetch /security /trust /compliance /privacy and footer badges. Classify: soc2_type2, soc2_type1, iso27001, gdpr_statement, hipaa, none; also trust-center vendor fingerprint (A.5)."
    scoring:
      no_trust_page_and_no_certs: 12
      trust_page_without_soc2_or_iso: 12          # classic gap: page exists, badge absent
      soc2_type1_only_or_iso_only: 8              # next step Type II / second framework
      soc2_type2_only_no_iso_no_gdpr: 6           # expansion play
      soc2_type2_plus_iso27001: 0
  - id: C2_in_flight_statement
    weight: 5
    detect: "Text on site/blog/press/job posts: 'SOC 2 in progress', 'pursuing ISO 27001', 'audit underway', 'readiness'"
    scoring: {explicit_in_progress: 5, indirect_hint: 2, none: 0}
  - id: C3_compliance_or_security_hiring
    weight: 8
    detect: "Careers page + ATS boards (greenhouse, lever, ashby, workable) + grounded search. Titles: GRC, compliance manager/analyst, security engineer, Head of Security, CISO, IT/security lead; JD text mentioning SOC 2/ISO 27001."
    scoring: {dedicated_grc_or_compliance_role: 8, security_role_mentions_soc2_iso: 6, generic_security_role: 3, none: 0}
  - id: C4_recent_funding
    weight: 5
    detect: "Grounded search: funding announced in last 12 months (investor diligence + new enterprise push)"
    scoring: {"<=6mo": 5, "7-12mo": 3, "13-24mo": 1, older_or_unknown: 0}
  - id: C5_geo_expansion_gdpr_pull
    weight: 5
    detect: "India/other-HQ selling to US/EU; EU customers/offices/languages; GDPR mentioned without evidence of certification/DPA; data residency pages; press on US/EU launch"
    scoring: {explicit_expansion_signal: 5, eu_or_us_customers_plus_gdpr_mention: 3, weak: 1, none: 0}

  # ---------- D. FIT MODIFIERS (10) ----------
  - id: D1_stack_integrates
    weight: 4
    detect: "Cloud-native on AWS/GCP/Azure, GitHub/GitLab, Okta/Google Workspace, Jira (all covered by Sprinto's 160+ integrations)"
    scoring: {clear: 4, partial: 2, unknown: 1}
  - id: D2_multi_framework_pull
    weight: 3
    detect: "Healthcare (HIPAA), payments (PCI), EU customers (GDPR/ISO 27701), public sector hints"
    scoring: {>=2_frameworks_implied: 3, 1: 2, none: 0}
  - id: D3_recent_enterprise_win_or_partnership
    weight: 3
    detect: "Blog/press in last 6 months: new enterprise customer, marketplace listing, partnership with large vendor"
    scoring: {found: 3, none: 0}
```

Weight check: A 10+10+10 = 30; B 8+8+5+4 = 25; C 12+5+8+5+5 = 35; D 4+3+3 = 10; total 100.

**Why these weights:** C (compliance trigger) is the largest block because it determines *timing*; B is second because it determines whether the gap is *painful* (enterprise buyers asking); A mostly gates fit. C1 is the single biggest signal (12) because the trust-page-without-badge is the most reliably observable website signal.

## A.5 How to detect each signal (implementation notes for the agent loop)

| Need | Method | Confidence |
|------|--------|------------|
| Certifications | Scrape `/security`, `/trust`, `/compliance`, `/trust-center`, `/privacy`, footer; look for text `SOC 2`, `SOC2`, `ISO 27001`, `ISO/IEC 27001`, `HIPAA`, `GDPR`, `Type I`, `Type II`, and badge `alt`/filename (many sites show badges as images with no text: pass `alt`, `src` filename and `title` to Gemini; one test fetch only revealed "gdpr-badge", "iso-27701" via filenames). Always record the exact quoted string as evidence. | HIGH |
| Trust-center vendor fingerprint | Check links/iframes/redirects/CNAME on `trust.<domain>`, `security.<domain>`, `<co>.trust.site`. Fingerprint strings: Vanta (`vanta.com`, "Powered by Vanta"), Drata (`drata.com`), SafeBase (`safebase.io`), Secureframe (`secureframe.com`), Thoropass, Scrut (`scrut.io`), Sprinto (`*.trust.site`, `sprinto`), plus Conveyor, Whistic, TrustCloud, Hyperproof, Oneleet, Delve. Only the Sprinto pattern is documented (docs.sprinto.com: `yourcompany.trust.site` or custom domain); Drata confirmed to offer custom public trust URLs and SafeBase integration; **the others are heuristics, so match on page text/script src, not on a guessed hostname.** | Sprinto pattern HIGH; others LOW-MEDIUM |
| Enterprise motion | `/pricing` + nav text: "Enterprise", "Contact sales", "Talk to sales", SSO/SAML/SCIM/audit logs. | HIGH |
| Big-logo customers | `/customers`, homepage logo strip. Logos are usually unlabeled images: send `alt` and filenames; if empty, ask grounded search "who are COMPANY's customers". | MEDIUM |
| Headcount | LinkedIn size bucket via grounded search, About page, open-role count. Ranges not points. | MEDIUM |
| Funding | Gemini + Google Search grounding, query "COMPANY funding round amount stage investors date"; require a dated source. | MEDIUM |
| Hiring | Careers page + ATS domains `boards.greenhouse.io`, `jobs.lever.co`, `jobs.ashbyhq.com`, `apply.workable.com`; keyword list: GRC, compliance, "security engineer", "head of security", CISO, "information security", SOC 2, ISO 27001, audit. Job descriptions mentioning SOC 2/ISO are a stronger signal than titles. | MEDIUM-HIGH |
| In-flight statement | Regex + Gemini on all scraped pages; phrases are not standardised ("SOC 2 in progress", "pursuing", "readiness", "audit underway"). | MEDIUM |

**Agent-loop stopping rule (differentiator, cheap to build):** after each tool call recompute `lo` (unknowns = 0) and `hi` (unknowns = max). Only fetch more while the threshold (60) lies inside `[lo, hi]`; otherwise decide. Cap at 4 tool calls per company. This makes the loop *purposeful and defensible* rather than "fetch everything".

## A.6 The "already certified" nuance

| Situation | Treatment | Why |
|-----------|-----------|-----|
| SOC 2 Type II + ISO 27001 + competitor trust center (Vanta/Drata/Secureframe/SafeBase) | Cap 40, reject, tag `switch_or_expand_candidate` in report only | Locked into a platform mid-contract; low odds on cold first touch. |
| SOC 2 Type II only, no ISO 27001/GDPR evidence, selling to EU/global | C1 = 6 (not 0); email angle = "second framework" (ISO 27001/GDPR) | Expansion is a real trigger: EU deals ask for ISO 27001; one platform covers multiple frameworks. |
| SOC 2 Type I only | C1 = 8; angle = Type II continuous monitoring / observation window | Type I is the stopgap; Type II follows. |
| Certified through a consultant/auditor with no GRC tool visible | Treat as certified (cap applies only with Type II + ISO); angle = "annual audit eats engineering time" | Cannot tell tooling from outside; don't assume Vanta. |
| Trust center present but certifications unlabeled (badge images only) | Score C1 as `unknown` -> trigger agent loop (grounded search "COMPANY SOC 2 report") | Common failure mode: false negatives on image-only badges. |

## A.7 Decision ladder and what the report must say

`DISQUALIFIED (hard rule + evidence) | REJECT (<45) | NURTURE (45-59) | QUALIFY (>=60) | PRIORITY (>=75)`. For every signal the trace stores: `{signal_id, points, max, evidence: [{url, quote, fetched_at}], source: "site|grounded_search|job_board", confidence}`. The report prints the top 3 positive and top 2 negative contributions plus any cap or disqualifier that fired.

---

# PART B. POC SELECTION AND PAIN POINTS

## B.1 Title targeting by company size

| Company size | Primary | Secondary | Fallback | Rationale |
|--------------|---------|-----------|----------|-----------|
| 8-50 | CEO / Founder (if technical founder, still CEO first) | Co-founder CTO / Head of Eng | COO, Head of Ops | Founder owns the enterprise deal and the budget; compliance is a founder problem. Belkins 2025: founders had the highest reply rate (0.57%) vs C-level (0.42%) and VPs (0.32%); smaller companies reply more (0-10 staff 0.72% vs 10k+ 0.22%). |
| 51-200 | CTO / VP Engineering | Head of Security / CISO / Head of IT (if exists, **promote to primary**) | CEO, COO | Engineering owns the control evidence (cloud, GitHub, access); CTO is budget holder or approver. |
| 201-500 | Head of Security / CISO / Head of GRC / Compliance Lead | CTO / VP Eng | Head of IT, CFO/COO | A dedicated owner usually exists; they run audits and feel the multi-framework pain. |
| 500+ (rare, near DQ) | Head of GRC / Director Security & Compliance | CISO | VP Eng | Enterprise-module conversation. |

**Priority-ordering logic (deterministic, goes in the trace):**
1. Hard filter: drop anyone whose title is sales, marketing, HR/recruiting, customer success, intern, or non-decision IC (e.g., "Security Engineer" gets a low authority score, 2/10, but is listed as a possible champion).
2. Score each contact: `title_fit_for_size (0-6)` + `owns_compliance_keyword (0-3: compliance, GRC, security, risk, InfoSec)` + `seniority (0-2)` + `evidence_of_trigger_ownership (0-1: e.g., authored the security post, posted the GRC job)`. Highest wins.
3. Override: at >=50 people, any contact whose title contains GRC/Compliance/Security-and-Compliance outranks CTO/VP Eng.
4. Ties: the more senior; then the earlier row in `contacts.csv`.
5. No eligible contact -> outcome `NO_CONTACT` (company stays qualified, no email drafted, report says why). Never fall back to a random person.
6. Output contract: `{chosen, runner_up, reason: "CTO of a 90-person company; no security/GRC role listed; engineering owns audit evidence"}`.

## B.2 Pain points by persona

Source basis: Sprinto/Vanta/Drata/Secureframe/Thoropass/Scrut and trycomp content, G2-style reviews, standard GRC practice. All MEDIUM confidence: vendor-authored, unmeasured. Use them as *hypotheses grounded by company evidence*, never as claims.

| Persona | Pain 1 (lead with this) | Pain 2 | Pain 3 (reserve) |
|---------|-------------------------|--------|------------------|
| **CEO / Founder (<50)** | Enterprise deals stall or slow at security review: "Do you have SOC 2?" / questionnaires add weeks (reported 2-4 weeks) and can kill the deal. | Cost and calendar of first certification: consultants + auditor + platform, uncertainty about timeline (Type 1 now vs Type 2 later). | Team distracted from product; fear of doing it wrong. |
| **CTO / VP Eng (51-200)** | Audit prep eats engineering time: screenshots, access reviews, evidence chasing, policy writing. | Continuous evidence across AWS/GCP, GitHub, Okta, HRIS, ticketing; fear of controls drifting between audits. | Pressure to unblock sales (security questionnaires land on eng). |
| **Head of Security / GRC (200+)** | Multi-framework sprawl: SOC 2 + ISO 27001 + GDPR + HIPAA with duplicated controls and evidence. | Evidence collection and auditor back-and-forth; moving from point-in-time to continuous compliance. | Vendor risk and questionnaire volume; trust center / customer assurance; auditor cost. |
| **All** | Auditor cost and selection; Type 1 -> Type 2 gap; annual re-audit treadmill. | | |

**Grounding rule for step 5 (anti-hallucination):** each pain point must reference one or more evidence IDs from the trace, in this form: `signal -> inference -> pain`. Example: `B1 Enterprise tier + no SOC 2 badge on trust page (C1) -> procurement will ask for a report -> enterprise deals stalled at security review`. If a pain point has no evidence link, it is dropped and the drafter may not use it.

---

# PART C. COLD EMAIL BEST PRACTICE FOR THIS PERSONA

Evidence is thin and mostly vendor data; treat numbers as directional (MEDIUM-LOW). Belkins 2026: overall strict-cold reply rate was just **0.45%** (replies/total sent); other vendors cite ~3-8% using different denominators; "signal-based 15-25%" is a top-performer vendor claim, not an average. Do not promise numbers in the demo.

| Dimension | Recommendation | Basis |
|-----------|----------------|-------|
| Length | **60-100 words body, hard cap 120.** 3-5 short sentences, 2-3 lines each. | Multiple vendor datasets: sweet spot 50-125 words (one reports 13.5% reply at 50-125 words vs 4.3% above 300). LOW-MEDIUM |
| Format | Plain text, no images, no attachments, no tracking pixels/links, at most one plain URL (or none). | Deliverability norm. MEDIUM |
| Subject | 2-5 words, sentence-case, specific, looks internal. Examples: `SOC 2 at {Company}`, `{Company} security review`, `{Company}'s trust page`, `enterprise deals + SOC 2`. Put the key words in the first ~30 characters (mobile truncation). | Sequenzy/Instantly guidance, LOW-MEDIUM |
| Subject: avoid | ALL CAPS, emoji, "Re:/Fwd:" fakery, "Quick question" (overused), "Free", "Guaranteed", "Act now", exclamation marks, the recipient's first name as the only personalisation. | Spam-filter and credibility norms. MEDIUM |
| Structure | (1) **Specific observable hook**, (2) **bridge to their likely pain**, (3) **one-line proof** (e.g., "Sprinto helped GeoIQ get SOC 2 and ISO 27001 in 3 months": use only vendor-published claims), (4) **soft CTA**. | Standard trigger-based framework. MEDIUM |
| Hook ranking | 1. Explicit compliance signal (SOC 2 in progress, GRC/security hire). 2. Enterprise-motion gap (enterprise tier / big logos but no certification evidence). 3. Funding round (diligence + enterprise push). 4. US/EU expansion (GDPR). 5. Generic role-based (**avoid**). Pick exactly one. | Trigger-based outreach consistently beats generic; vendor datasets. MEDIUM |
| CTA | Low-friction interest question: "Worth a 15-minute look?" or "Want me to send the 1-page checklist?". One CTA only. No calendar links in first touch. | Interest-based CTAs generally outperform meeting asks. MEDIUM |
| Tone | Peer-to-peer, specific, no hype. State the observation, do not accuse ("noticed your trust page doesn't mention SOC 2" -> fine; "you're non-compliant" -> never). | MEDIUM |
| Persona angle | Founder: deal-velocity + cost. CTO: engineering hours. Security/GRC: multi-framework/continuous. | Part B |
| Sign-off | "{Name}, Growth Lead, Sprinto" per brief; include a one-line opt-out ("not relevant? say so and I'll stop"). Costs ~8 words and mirrors real-world opt-out expectations. | Practice; CAN-SPAM-style norms |
| Follow-ups | Out of scope for v1. | PROJECT.md |

**What to avoid (spammy or fake personalisation):**
- "I hope this finds you well", "revolutionary", "game-changing", "just circling back", "synergy".
- Fake familiarity: "loved your recent post" unless a post is in the evidence; compliments with no source; invented quotes or customers.
- Unbacked numbers: "save 80% of time", "certified in 30 days" (only quote Sprinto's published case studies, attributed: "GeoIQ, 3 months").
- Details that reveal scraping ("I saw you have 47 employees and 12 open roles").
- Multiple CTAs, links to a pricing page, attachments, competitor bashing.
- **Guardrail for the drafter (differentiator):** every factual claim about the prospect must map to an evidence ID in the trace; the draft validator rejects any sentence with an unmapped claim, word count > 120, more than one question mark or CTA, or banned phrases.

**Template skeleton (for the drafter prompt):**

```
Subject: SOC 2 at {Company}

Hi {FirstName},

{One-line specific hook from evidence, e.g. "Saw {Company} just opened a GRC role" / "{Company}'s pricing has an Enterprise tier, but the security page doesn't mention SOC 2 or ISO 27001."}

{One-line pain bridge for this persona.}

Sprinto automates SOC 2 / ISO 27001 evidence collection and audit prep; {proof point}.

{Soft CTA question?}

{Sender}
Growth Lead, Sprinto
(Not relevant? Tell me and I'll stop.)
```

---

# PART D. TEST DOMAINS

All facts below were checked in this session (live fetch of the company site and/or funding news on 2026-11-03) unless marked "unverified". **Caveat for the builder:** website content changes, and image-only badges were sometimes unreadable to the fetcher; open each qualifier's `/security` or trust page for 30 seconds before the demo.

**Honest finding:** genuinely *pre-certification* Series A-C SaaS companies are rare; by Series A most have SOC 2 on the site (Composio, Lyzr, Smallest.ai, Windmill, Zluri, Gnani, CodeAnt, Atomicwork all showed SOC 2 and/or ISO 27001 in this session). The best live prospects are young AI/dev-tool companies with an enterprise motion and no certification text. That is exactly the shape of the ICP, but it means the 2-3 clean qualifiers are seed to Series A, and the demo should include "expansion" and "borderline" cases to show the rubric's nuance.

| # | Domain | What it is (verified) | Stage / size (verified) | Observed signals | Expected verdict | Expected score |
|---|--------|-----------------------|-------------------------|------------------|------------------|----------------|
| 1 | **getmaxim.ai** | Maxim AI: LLM eval/observability + Bifrost open-source LLM gateway (legal entity H3 Labs Inc.; Bengaluru + US). | Seed $3M led by Elevation Capital (Jun 2024). Small team (headcount unverified; run the loop). | "Try Bifrost Enterprise", "1,000+ teams use Bifrost", zero-touch in-VPC deployments; **no SOC 2/ISO/trust page found**; "contact us/book a demo" only. | **QUALIFY** (strong gap + enterprise pull; weaker on stage) | ~60-72 |
| 2 | **bolna.ai** | Voice-AI orchestration for Indian languages; Bengaluru. | Seed $6.3M led by General Catalyst (Jan 2026), YC fall 2025. 10+ countries. | "Enterprise Plans" + forward-deployed service; named logos (Physics Wallah, GoKwik, Spinny, Awign); India/US data residency, on-prem; **no certification or trust page mention**; funding <12 months ago. | **QUALIFY** | ~68-75 |
| 3 | **nurix.ai** | Enterprise voice/chat AI agents (Mukesh Bansal); Bengaluru. | $27.5M seed + Series A (Sep 2024, Accel + General Catalyst); Prosus investment reported 2026. "30+ enterprises". | Footer has BAA + DPA links and **unlabeled certificate badges** (could not read which); security page says "Enterprise-grade security". **Unverified: whether a SOC 2/ISO report exists.** | **QUALIFY or MAYBE depending on badge reading** (exercises the "unlabeled badge -> agent loop" path) | ~50-72 |
| 4 | **greptile.com** | AI code review; US (SF), YC. | $25M Series A led by Benchmark (Sep 2025). "22,000+ teams". | "Contact Sales", SSO/audit logs, self-hosted air-gapped option, logos (Nvidia, Brex, Zapier); **SOC 2 listed ("independent audits, reports on request"), no ISO 27001/GDPR mention**. | **QUALIFY (marginal) as "expansion play"**: C1 = 6, angle = ISO 27001/GDPR for EU enterprises | ~58-68 |
| 5 | **gushwork.ai** | AI marketing agents for SMB manufacturers; US/India. | Funded (round not verified here). "1,000+ businesses". | No certs/trust page, but buyers are SMBs ("AI Marketing Agents for SMBs"); logos are small manufacturers; no enterprise tier. | **REJECT / NURTURE**: compliance gap but no upmarket pull; demonstrates the `no_upmarket_pull` cap (55) | ~40-55 |
| 6 | **salesforce.com** | Mega-cap enterprise software. | Public, 70,000+ staff. | Fully certified, huge trust site. | **DISQUALIFIED: too_large** | 0 |
| 7 | **rocketlane.com** | PSA/customer-onboarding SaaS; Chennai + US. | $24M Series B (Jun 2024; 8VC, Matrix, Nexus); ~260-290 staff. | Footer "Trust center" link points to a **Sprinto-hosted page**; "Contact sales" in nav. | **DISQUALIFIED: existing Sprinto customer**. Great proof that the pipeline reads the evidence rather than just scoring "SaaS + Series B = yes". | 0 |
| 8 | **hyperbound.ai** | AI sales-roleplay/coaching SaaS; US. | Funded (round not verified). 30+ logos incl. LinkedIn, Amazon, Workday. | States "SOC 2 Type II and ISO 27001 certified, with support for GDPR and HIPAA"; Security Trust Center; **Vanta is a named customer** (so likely uses Vanta). | **REJECT: fully certified** (cap 40, tag `switch_or_expand_candidate`) | ~30-40 |
| 9 | **atomicwork.com** | AI service-management/ITSM SaaS; US + India. | Funded (round not verified). | FAQ: "SOC 2 Type I and II, ISO 27001, ISO 27017, 27018, 27701, ISO 42001"; own-domain trust center (`trust.atomicwork.com`). | **REJECT: fully certified** | ~25-35 |
| 10 | **wakefit.co** | Indian direct-to-consumer mattress and furniture brand. | Consumer retail, not software. | Not software. | **DISQUALIFIED: not_software** | 0 |

**Contacts to hand-fill in Apollo (keep short):** #1 getmaxim.ai (founder/CEO + CTO), #2 bolna.ai (founder/CEO + CTO), #3 nurix.ai (a CTO or Head of Security), #4 greptile.com (founder/CEO + eng lead). **That is only 4 companies / ~6-8 contacts.** The rest should *not* need contacts; if the pipeline qualifies one without contacts, it must emit `NO_CONTACT` instead of crashing (also a good edge case to show).

If the demo needs more clean qualifiers, swap in the next ones to check during contact lookup (all unverified): superjoin.ai (has a trust center but no certification text on homepage; funding not found), and fresh Series A/B Indian/US B2B SaaS from Entrackr/Inc42 weekly funding roundups (run the pipeline on them live).

**Sources for Part D:** company sites fetched 2026-11-03; techcrunch.com (Bolna Jan 2026); kmworld/Inc42 (Maxim $3M seed); SiliconANGLE/Pulse2 (Greptile Series A); Entrackr/Inc42/Entrepreneur India (Nurix); Entrackr/YourStory (Rocketlane Series B).

---

# PART E. PIPELINE FEATURE LANDSCAPE

## Table Stakes (must have; missing = the case brief fails)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Domain list input and per-company run loop (`python run.py domains.txt`) | Brief requires repeatable, unattended runs | LOW | Isolate failures per domain; one bad site must not kill the run. |
| Scrape homepage + key pages (`/`, `/pricing`, `/security`, `/trust`, `/customers`, `/about`, `/careers`) | Raw signal source | MEDIUM | httpx + BeautifulSoup; polite timeouts; handle 403/404/JS-only pages with graceful "page unavailable" evidence; keep `alt`, `title`, link hrefs and image filenames, not only visible text. |
| Gemini structured extraction (JSON schema) | Step 2 | MEDIUM | Schema = company fields + signal evidence with quote + URL. Validate with pydantic; one repair retry. |
| Scored qualifier: rubric YAML, threshold, reason | Step 3 core; "defend every decision" | MEDIUM | Rubric lives in config (Part A), score computed in code from LLM-extracted facts, not "ask the LLM for a score". |
| Agent loop with tools: more site pages, Gemini + Google Search grounding, job postings | Brief requires it | HIGH | Hard budget (4 calls), stopping rule from A.5, every tool result stored as evidence. |
| Hard disqualifiers (not software, too large, existing Sprinto customer, tiny) | Filter must visibly reject non-fits | LOW | Checked before scoring; cite evidence. |
| PoC selection from `contacts.csv` with stated reason | Step 4 | LOW-MEDIUM | Deterministic scoring from B.1; Gemini only for ambiguous titles. `NO_CONTACT` path. |
| Two pain points grounded in company evidence | Step 5 | MEDIUM | Persona table + evidence IDs (B.2). |
| Draft email: by name, <120 words, one hook, one soft CTA, signed Growth Lead | Step 6 | MEDIUM | Deterministic validator (word count, one CTA, banned phrases, evidence mapping) with up to 2 regenerations. |
| Send via Gmail API to the user's own address only | Step 7 | MEDIUM | OAuth `token.json`; `to:` read from `.env` and asserted; never from CSV. Subject shows target company; body notes intended recipient. |
| Decision trail: per-company JSON trace + `report.md` | Core value | MEDIUM | Trace per step {input, output, evidence, model, timestamp}; report = verdict, score table, evidence quotes, PoC reason, pain points, email. |
| Researched ICP document used by the qualifier | Brief: arrived at through research | LOW | This file, Part A; ship YAML in repo and cite sources. |
| Secrets hygiene (`.env`, `.gitignore`) | Constraint | LOW | |

## Differentiators (make it defensible and impressive in a 1.5-hour demo)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Threshold-aware agent loop (fetch only while the decision could flip) | Shows judgement, not brute force; saves tokens | MEDIUM | `[lo, hi]` score bounds with unknowns. |
| Evidence ledger: every claim has `{url, quote}`; draft validator rejects claims without evidence | "Defend every decision"; kills fake personalisation | MEDIUM | Biggest quality lever for the email. |
| Trust-center vendor fingerprinting (Vanta/Drata/SafeBase/Sprinto...) + "already certified" nuance | Prevents emailing existing customers/locked-in firms | MEDIUM | Heuristic list (A.5). |
| Expansion/switch tagging (SOC 2 only -> ISO 27001/GDPR angle) | Finds extra qualifiers; shows ICP depth | LOW | Tag + angle only. |
| Hook selection ladder (compliance signal > enterprise gap > funding > geo) | Consistently picks the strongest, truthful hook | LOW | Deterministic from qualifier output. |
| Persona-specific angle (founder/CTO/GRC) | Emails differ for the right reasons | LOW | Prompt parameter from B.2. |
| Run summary table (qualified/rejected/why, tool calls, tokens, time) | Success metric: qualified prospects per hour | LOW | `summary.md` or top of report. |
| Confidence labels + "unknown" handling in report | Honest about gaps | LOW | `confidence=LOW` flag. |
| Caching of fetched pages per domain | Faster re-runs during the live demo | LOW | Simple on-disk cache keyed by URL+date. |

## Anti-Features (deliberately NOT build)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Sending to real prospects | "End to end" | Violates case rule; reputational/legal risk | `to:` hardcoded to the user's address, asserted in code. |
| Dry-run toggle or "send approval" prompt | Safety instinct | User chose "always send"; interactive prompts break unattended runs | Safety comes from the recipient lock. |
| Apollo/Hunter API enrichment, email guessing/verification | Automation | Free tier has no API; adds scope; guessing addresses is harmful | Hand-filled `contacts.csv`. |
| Follow-up sequences, reply tracking, CRM sync, open/click tracking | "Real outbound" | Out of scope; tracking pixels hurt deliverability and trust | First-touch only. |
| LLM-assigned score with no rubric ("rate this 0-100") | Fast | Not reproducible or defensible | Code-computed score from extracted signals; LLM only extracts and classifies. |
| Letting the LLM invent personalisation (posts, quotes, "I saw you...") | Makes the email feel personal | Fake personalisation is the #1 reply killer and a credibility risk | Evidence-mapped claims only. |
| LinkedIn scraping / login-gated sites | Richer signal | ToS risk, brittle, time sink | Public pages + grounded search. |
| Web UI/dashboard | Demo polish | Time; CLI is enough for "repeatable" | `report.md` + `summary.md`. |
| Headless browser for every site | Handles JS pages | Slow, brittle, setup time | httpx first; optional single Playwright fallback only if time allows (v1.x). |
| Multi-LLM orchestration or vector DB | "Agentic" look | Constraint says Gemini only; adds nothing | Single Gemini client, plain JSON files. |
| Scoring many weak signals (>15) | Thoroughness | Unexplainable; double-counting | 14 signals in 4 blocks (A.4). |

## Feature Dependencies

```
domains.txt loop
    └──requires──> Scraper (pages + raw HTML signals)
                       └──requires──> Extractor (Gemini JSON schema)
                                          └──requires──> Rubric YAML (ICP) + hard disqualifiers
                                                             └──requires──> Agent loop (more pages / grounded search / jobs)
                                                                                └──produces──> Evidence ledger
Qualify (>=60)
    └──requires──> contacts.csv (hand-filled) ──> PoC selector (B.1)
                                                      └──requires──> Pain-point inference (B.2, needs evidence ledger)
                                                                         └──requires──> Drafter + validator (Part C)
                                                                                            └──requires──> Gmail OAuth sender (to: locked)

Evidence ledger ──feeds──> JSON trace ──feeds──> report.md (every step writes to it)
Trust-center fingerprint ──enhances──> Qualifier (C1, DQ rules)
Threshold-aware stopping ──enhances──> Agent loop
Evidence-mapped drafting ──conflicts──> "free-form LLM personalisation"
Dry-run / approval prompt ──conflicts──> unattended "always send"
```

### Dependency Notes

- **Qualifier requires the evidence ledger:** each signal's points need a quote and URL; design the extraction schema around evidence objects from day one.
- **Pain points require evidence:** pain inference with no evidence reverts to generic persona text, which is what the brief says not to do.
- **Gmail sender is independent of the rest:** build it first (walking skeleton) with a hard-coded test email, then wire real drafts in. This de-risks OAuth early (the brief's #1 "done" criterion).
- **Contacts only block steps 4-7:** companies without contacts still get qualified and reported.

## MVP Definition

### Launch With (v1, order = build order for the 1.5-hour session)

- [ ] Walking skeleton: Gmail OAuth + send a hard-coded email to self (de-risk first)
- [ ] Domain loop + scraper + Gemini extraction to JSON (with evidence quotes)
- [ ] Rubric YAML + scoring code + hard disqualifiers + trace JSON (Part A)
- [ ] PoC selector + `contacts.csv` loader with `NO_CONTACT` path
- [ ] Pain-point + draft prompts with validator (<120 words, one CTA, evidence-mapped)
- [ ] `report.md` generation + run summary table
- [ ] Agent loop with the three tools and the 4-call budget

### Add After Validation (v1.x)

- [ ] Threshold-aware stopping bounds (if not done in v1; simple budget works first)
- [ ] Trust-center vendor fingerprint list expansion
- [ ] Per-domain page cache for faster demo reruns
- [ ] Playwright fallback for JS-only sites

### Future Consideration (v2+)

- [ ] Follow-up sequences and reply classification
- [ ] Apollo API integration for automatic contact lookup
- [ ] CRM sync, A/B testing of hooks, reply-rate learning loop

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Gmail send to self (skeleton) | HIGH | MEDIUM | P1 |
| Scrape + extract with evidence | HIGH | MEDIUM | P1 |
| Rubric + hard DQs + trace | HIGH | MEDIUM | P1 |
| PoC selection + reason | HIGH | LOW | P1 |
| Pain points + draft + validator | HIGH | MEDIUM | P1 |
| report.md + summary | HIGH | LOW | P1 |
| Agent loop (3 tools, budget) | HIGH | HIGH | P1 |
| Trust-center fingerprinting | MEDIUM | MEDIUM | P2 |
| Threshold-aware stopping | MEDIUM | MEDIUM | P2 |
| Expansion/switch tagging | MEDIUM | LOW | P2 |
| Page cache | MEDIUM | LOW | P2 |
| Playwright fallback | LOW | MEDIUM | P3 |

## Competitor Feature Analysis (adjacent AI-SDR / outbound tools; from training knowledge, not re-verified this session, LOW-MEDIUM)

| Feature | Clay / Apollo-style (data + enrichment + sequences) | Autonomous AI-SDR tools | Our Approach |
|---------|------------------------------------------------------|-------------------------|--------------|
| Lead qualification | Filters on firmographics; AI "research agent" columns in Clay | Black-box scoring | Transparent weighted rubric with quoted evidence per signal |
| Contact data | Large databases | Bundled | Apollo by hand to `contacts.csv` (scope cut) |
| Personalisation | Template merge + AI first line | Fully generated, often generic or invented | Evidence-mapped hook; validator rejects unsupported claims |
| Auditability | Row-level, limited reasoning | Minimal | Per-step JSON trace + `report.md` |
| Safety | Real sending | Real sending | Recipient locked to own inbox |

---

## Overall Confidence

| Area | Level | Reason |
|------|-------|--------|
| Sprinto positioning/customers | HIGH | First-party site, docs, TechCrunch |
| Pricing | LOW-MEDIUM | Quote-based; only third-party estimates, some competitor-authored |
| Competitor positioning | MEDIUM | Mostly vendor-authored |
| Rubric weights | MEDIUM | Reasoned from observable signals + buying-trigger sources; **weights are judgement, not fitted to data**; tune after first run |
| Trust-center vendor fingerprints | LOW-MEDIUM | Only Sprinto's pattern documented; others heuristic |
| Persona pain points | MEDIUM | Consistent across vendor sources; no primary survey data |
| Cold-email benchmarks | MEDIUM-LOW | Vendor datasets conflict (0.45% to ~8%); use as direction, not targets |
| Test domains | MEDIUM-HIGH | Fetched live; badge-image reading and headcounts are the weak spots (Nurix flagged) |

## Sources

- sprinto.com homepage and /customers (fetched 2026-11-03); docs.sprinto.com/settings/billing/sprinto-plans-and-pricing; docs.sprinto.com/trust/trust-center/how-it-works (trust.site pattern via search result) (HIGH)
- TechCrunch, "Sprinto funding" 2024-04-09 (HIGH); Entrackr, Inc42, Outlook Business, SecurityWeek on Series B (HIGH)
- Orbiq Sprinto pricing page (competitor-authored, LOW); Spendflo, ComplyJet, SmartSuite, Capterra, G2 via search (LOW-MEDIUM)
- sprinto.com/blog/sprinto-competitors and compare pages; drata.com/learn/compare; guptadeepak.com top-5 GRC; G2 compare pages (MEDIUM-LOW, vendor-authored)
- trycomp.ai/when-to-get-soc-2; Thoropass, Secureframe, Scrut SOC 2 guides; probo.com and tcsa.in on "SOC 2 in progress" wording (MEDIUM, vendor-authored)
- Belkins B2B cold outreach benchmarks (belkins.io/blog/cold-email-response-rates; job-title and company-size findings fetched); Instantly, Lemlist, Folderly, FullEnrich, Prospeo, Sequenzy cold-email guides via search (MEDIUM-LOW)
- Company sites fetched 2026-11-03: getmaxim.ai, bolna.ai, nurix.ai, greptile.com, gushwork.ai, rocketlane.com, hyperbound.ai, atomicwork.com, composio.dev, lyzr.ai, smallest.ai, zluri.com, gnani.ai, codeant.ai, windmill.dev, superjoin.ai, spyne.ai, sharpsell.ai
- Funding: TechCrunch/Entrackr (Bolna $6.3M seed, Jan 2026); KMWorld/Inc42 (Maxim $3M seed, Jun 2024); SiliconANGLE/Pulse2 (Greptile $25M Series A, Sep 2025); Entrackr/Inc42/SiliconANGLE (Nurix $27.5M, Sep 2024; Prosus 2026); Entrackr/YourStory (Rocketlane $24M Series B, Jun 2024)

---
*Feature research for: AI cold-outreach pipeline for Sprinto (compliance automation)*
*Researched: 2026-11-03*
