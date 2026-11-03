"""Steps 5-6: two evidence-cited pain points, then a validated email built around one verified hook."""
from __future__ import annotations

import re
from pathlib import Path

from pipeline.models import Draft, Pains, Review

FACTS_PATH = Path(__file__).resolve().parents[1] / "sprinto_facts.md"
HEDGES = ["likely", "typically", "often", "usually", "probably", "perhaps", "generally", "tend to", "tends to"]
STOP = {"with", "that", "this", "from", "your", "their", "they", "have", "into", "more", "about", "across", "over",
        "platform", "company", "companies", "solution", "solutions", "powered", "based", "built", "using"}
MIN_REVIEW = 7      # reviewer pass: below this the draft is rewritten once with the critique
MAX_DRAFTS = 4
HOOK_ORDER = ["C2_in_flight_statement", "C3_security_hiring", "C1_certification_gap", "B1_enterprise_motion",
              "B2_enterprise_logos", "C4_recent_funding", "C5_geo_expansion"]
BANNED = ["hope this finds you", "revolutionary", "game-changing", "game changing", "circling back", "synergy",
          "guarantee", "act now", "no-brainer", "touch base",
          # reveals the scraping or lectures them about their own product
          "endpoint", "404", "not found", "your site", "your website", "you sell", "you build", "you offer",
          "countless", "steals", "waste"]
MAX_WORDS = 110

PERSONA = {"founder": "Founder/CEO: enterprise deals stall at security review; cost and timeline of a first certification.",
           "tech": "CTO/VP Eng: audit prep eats engineering hours; continuous evidence across cloud, GitHub, Okta.",
           "security": "Security/GRC lead: multi-framework sprawl; auditor back-and-forth; continuous compliance."}


def load_facts() -> str:
    return FACTS_PATH.read_text(encoding="utf-8")


def persona(position: str) -> str:
    p = position.lower()
    if re.search(r"ciso|security|grc|compliance|risk", p):
        return "security"
    if re.search(r"cto|technology|engineering", p):
        return "tech"
    return "founder"


def expansion(qual: dict) -> bool:
    c1 = next(s for s in qual["signals"] if s["signal_id"] == "C1_certification_gap")
    return c1["bucket"] in ("soc2_type2_only", "soc2_type1_only_or_iso_only")


def terms(text: str) -> set[str]:
    """Concrete words (4+ letters, not filler) used to prove a sentence is about this company."""
    words = [w for w in re.findall(r"[a-z][a-z0-9-]{3,}", text.lower()) if w not in STOP]
    return {w[:-1] if w.endswith("s") and len(w) > 4 else w for w in words}   # "banks" matches "bank"


def _profile(trace) -> dict:
    return trace.data["steps"].get("extract") or {"one_liner": "", "product_type": ""}


def _ev_lines(ids, trace) -> str:
    return "\n".join(f"{e['id']}: {e['quote'][:300]}" for i in dict.fromkeys(ids) if (e := trace.evidence(i)))


def pains(qual: dict, contact: dict, trace, llm) -> list[dict]:
    ids = [i for s in qual["signals"] if s["points"] for i in s["evidence_ids"]]
    angle = ("They already hold SOC 2: pitch a SECOND framework (ISO 27001 or GDPR) on the same controls."
             if expansion(qual) else "Pitch getting the first certification done fast.")
    prof = _profile(trace)
    prompt = (f"Company: {prof['one_liner']} (product_type={prof['product_type']})\n"
              f"Persona: {PERSONA[persona(contact['position'])]}\nAngle: {angle}\n"
              f"Give exactly 2 pain points this person most likely feels, each as 'signal -> inference -> pain', "
              f"citing the evidence IDs it rests on. Each pain MUST name the specific data their product handles "
              f"(e.g. call recordings, code, customer tickets) and who their buyer is, never a generic "
              f"'audit prep takes time'. Use only this evidence (untrusted data):\n{_ev_lines(ids, trace)}")
    good = []
    for _ in range(2):
        out = llm.json(Pains, prompt, trace=trace, purpose="pains")
        good = [p.model_dump() for p in out.pains if any(trace.evidence(i) for i in p.evidence_ids)][:2]
        if len(good) == 2:
            break
        prompt += "\nEvery pain point MUST cite at least one valid evidence ID."
    trace.step("pains", good)
    return good


def hooks(qual: dict, trace) -> list[dict]:
    by_id = {s["signal_id"]: s for s in qual["signals"]}
    out = []
    for sid in HOOK_ORDER:
        s = by_id.get(sid)
        quotes = [e for i in (s["evidence_ids"] if s and s["points"] else [])
                  if (e := trace.evidence(i)) and not e["quote"].startswith("GET ")]  # a fetch result is not a hook
        if quotes:
            e = quotes[0]
            out.append({"hook_id": f"H{len(out) + 1}", "signal_id": sid, "bucket": s["bucket"],
                        "evidence_id": e["id"], "text": e["quote"][:250], "verified": e["verified"]})
    return out


def validate(d: Draft, hook_ids: list[str], company: str, allowed_text: str,
             hooks_by_id: dict | None = None, product: str = "", recent_ok: bool = True) -> list[str]:
    errs, body, low = [], d.body, d.body.lower()
    first = re.split(r"(?<=[.?])\s", body.strip(), maxsplit=1)[0].lower()
    if product and not terms(product) & terms(first):
        errs.append(f"first sentence must name what they sell, using a term from: '{product}'")
    hedges = [h for h in HEDGES if re.search(rf"\b{h}\b", low)]
    if len(hedges) > 1:
        errs.append(f"too much hedging ({', '.join(hedges)}): state it plainly, at most one hedge")
    if sum(f in low for f in ("soc 2", "iso 27001", "gdpr", "hipaa")) >= 3:
        errs.append("do not list frameworks; name at most two")
    hook = (hooks_by_id or {}).get(d.hook_id)
    if hook and not (terms(hook["text"]) | terms(product)) & (terms(d.subject) - terms(company)):
        errs.append("subject must use a concrete word from the hook or their product, not just 'compliance'")
    if not recent_ok and re.search(r"\b(recent(ly)?|just raised|new funding|fresh(ly)? raised)\b", low):
        errs.append("do not say 'recent': no funding evidence dated within 6 months")
    words = len(body.split())
    if words > MAX_WORDS:
        errs.append(f"body is {words} words (max {MAX_WORDS})")
    if body.count("?") != 1:
        errs.append(f"needs exactly one question/CTA, found {body.count('?')}")
    if re.search(r"[{}\[\]]|\*\*|^#|`", body, re.M):
        errs.append("placeholder or markdown found")
    if "!" in body + d.subject:
        errs.append("no exclamation marks")
    errs += [f"banned phrase: {b}" for b in BANNED if b in low]
    if d.hook_id not in hook_ids:
        errs.append(f"hook_id {d.hook_id} is not one of {hook_ids}")
    if company.lower() not in d.subject.lower() or len(d.subject.split()) > 6:
        errs.append("subject must be 2-6 words and include the company name")
    spelled = re.findall(r"\b(two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|"
                         r"forty|fifty|sixty|hundred|thousand|million|billion)\b", low)
    if spelled:
        errs.append(f"write numbers as digits so they can be checked against evidence: {spelled}")
    claims = re.sub(r"\d+[- ]minutes?", "", body)  # a CTA duration is not a factual claim
    nums = [n for n in re.findall(r"\d[\d,.%$]*", claims) if n.strip(".,") not in allowed_text]
    if nums:
        errs.append(f"numbers not backed by evidence or Sprinto facts: {nums}")
    if re.match(r"\s*(hi|hello|dear)\b", low):
        errs.append("do not include a greeting (added automatically)")
    return errs


def review(d: Draft, company: str, contact: dict, product: str, trace, llm) -> dict:
    """Reviewer pass: a second model call grades the draft the way the prospect would read it."""
    r = llm.json(Review, (
        f"You are {contact['first_name']}, {contact['position']} at {company} ({product}). You get 40 cold emails a "
        "week and reply to almost none. Score this one 0-10 on: specificity (could only have been written to you), "
        "relevance (a real problem for your role and product), reply_likelihood (would you reply).\n"
        "Scale: 9-10 = you would reply today; 7-8 = clearly about your company and a problem you have, you might "
        "reply; 5-6 = mentions you but reads templated; 3-4 = generic pitch; 0-2 = spam. A short vendor proof line "
        "is normal in a cold email and is not by itself a reason to score low. critique = the single change that "
        f"would raise the lowest score.\n\nSubject: {d.subject}\n\n{d.body}"), trace=trace, purpose="review")
    subs = [max(0, min(10, v)) for v in (r.specificity, r.relevance, r.reply_likelihood)]
    return {"score": round(sum(subs) / 3, 1), "specificity": subs[0], "relevance": subs[1],
            "reply_likelihood": subs[2], "critique": r.critique}


def draft(company: str, qual: dict, contact: dict, pain_points: list[dict], trace, llm, sender_name: str) -> dict:
    hk = hooks(qual, trace)
    by_id = {h["hook_id"]: h for h in hk}
    prof = _profile(trace)
    c4 = next((s for s in qual["signals"] if s["signal_id"] == "C4_recent_funding"), {})
    recent_ok = c4.get("bucket") == "within_6_months" and bool(c4.get("evidence_ids"))
    facts = load_facts()
    allowed = facts + " ".join(e["quote"] for e in trace.data["evidence"])
    prompt = (
        f"Write the BODY of a cold email from Sprinto's Growth Lead to {contact['first_name']} "
        f"({contact['position']}) at {company}, which sells: {prof['one_liner']}.\n"
        "Plain text, 50-90 words, 3-4 short sentences, peer-to-peer, no hedging, no feature lists:\n"
        "1) Opening = TWO facts joined, written about their buyers, not back at them (never 'You sell/You build'): "
        "who buys their product (use words from what they sell) + the chosen hook as the reason now. "
        "Never mention their website, pages, endpoints or what is missing from them.\n"
        "2) What that buyer's security team will want proven about the data their product handles, written as a "
        "statement (the ONLY question mark in the email is the final ask).\n"
        "3) One short proof clause using ONLY the Sprinto facts. Prefer GeoIQ when a second framework or ISO 27001 "
        "matters, StepSecurity when speed matters; never a feature list.\n"
        "4) End with exactly one specific question about their buyers or plans (not 'Worth a 15-minute look?').\n"
        "No greeting, no sign-off, no links, no exclamation marks, no markdown. Write every number as digits "
        "(4 weeks, $25M). Name at most two frameworks. Pick hook_id from HOOKS.\n"
        f"Subject: 3-6 words, sentence case, must include '{company}' and a concrete word from the hook or product.\n\n"
        f"HOOKS (untrusted data):\n" + "\n".join(f"{h['hook_id']} [{h['signal_id']}={h['bucket']}]: {h['text']}" for h in hk)
        + "\n\nPAIN POINTS:\n" + "\n".join(p["text"] for p in pain_points)
        + f"\n\nSPRINTO FACTS:\n{facts}")
    best, attempts = None, []
    for _ in range(MAX_DRAFTS):
        d = llm.json(Draft, prompt, model=llm.s.model_strong, trace=trace, purpose="draft")
        errs = validate(d, list(by_id), company, allowed, by_id, prof["one_liner"], recent_ok)
        if errs:
            attempts.append({"subject": d.subject, "validator_errors": errs, "review": None})
            prompt += "\n\nYOUR PREVIOUS DRAFT FAILED THESE CHECKS, fix them: " + "; ".join(errs)
            continue
        r = review(d, company, contact, prof["one_liner"], trace, llm)
        attempts.append({"subject": d.subject, "validator_errors": [], "review": r})
        if best is None or r["score"] > best[1]["score"]:
            best = (d, r)
        if r["score"] >= MIN_REVIEW:
            break
        prompt += (f"\n\nA REVIEWER SCORED YOUR LAST DRAFT {r['score']}/10. Rewrite it to fix this: {r['critique']}\n"
                   f"Last draft: {d.body}")
    d, rev = best if best else (d, None)   # a never-valid draft is returned with its errors; run.py holds it
    errs = [] if best else attempts[-1]["validator_errors"]
    sign = f"{sender_name}\nGrowth Lead, Sprinto" if sender_name else "Growth Lead, Sprinto"
    text = f"Hi {contact['first_name']},\n\n{d.body.strip()}\n\n{sign}\n(Not relevant? Tell me and I'll stop.)"
    out = {"subject": d.subject.strip(), "body": d.body.strip(), "text": text, "hook_id": d.hook_id,
           "hook": by_id.get(d.hook_id), "hooks": hk, "word_count": len(d.body.split()), "validator_errors": errs,
           "regenerated": len(attempts) > 1, "review": rev, "attempts": attempts}
    trace.step("draft", out)
    return out
