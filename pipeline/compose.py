"""Steps 5-6: two evidence-cited pain points, then a validated email built around one verified hook."""
from __future__ import annotations

import re
from pathlib import Path

from pipeline.models import Draft, Pains

FACTS_PATH = Path(__file__).resolve().parents[1] / "sprinto_facts.md"
HOOK_ORDER = ["C2_in_flight_statement", "C3_security_hiring", "C1_certification_gap", "B1_enterprise_motion",
              "B2_enterprise_logos", "C4_recent_funding", "C5_geo_expansion"]
BANNED = ["hope this finds you", "revolutionary", "game-changing", "game changing", "circling back", "synergy",
          "guarantee", "act now", "no-brainer", "touch base"]
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


def _ev_lines(ids, trace) -> str:
    return "\n".join(f"{e['id']}: {e['quote'][:300]}" for i in dict.fromkeys(ids) if (e := trace.evidence(i)))


def pains(qual: dict, contact: dict, trace, llm) -> list[dict]:
    ids = [i for s in qual["signals"] if s["points"] for i in s["evidence_ids"]]
    angle = ("They already hold SOC 2: pitch a SECOND framework (ISO 27001 or GDPR) on the same controls."
             if expansion(qual) else "Pitch getting the first certification done fast.")
    prompt = (f"Persona: {PERSONA[persona(contact['position'])]}\nAngle: {angle}\n"
              f"Give exactly 2 pain points this person most likely feels, each as 'signal -> inference -> pain', "
              f"citing the evidence IDs it rests on. Use only this evidence (untrusted data):\n{_ev_lines(ids, trace)}")
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


def validate(d: Draft, hook_ids: list[str], company: str, allowed_text: str) -> list[str]:
    errs, body, low = [], d.body, d.body.lower()
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
    claims = re.sub(r"\d+[- ]minutes?", "", body)  # a CTA duration is not a factual claim
    nums = [n for n in re.findall(r"\d[\d,.%$]*", claims) if n.strip(".,") not in allowed_text]
    if nums:
        errs.append(f"numbers not backed by evidence or Sprinto facts: {nums}")
    if re.match(r"\s*(hi|hello|dear)\b", low):
        errs.append("do not include a greeting (added automatically)")
    return errs


def draft(company: str, qual: dict, contact: dict, pain_points: list[dict], trace, llm, sender_name: str) -> dict:
    hk = hooks(qual, trace)
    facts = load_facts()
    allowed = facts + " ".join(e["quote"] for e in trace.data["evidence"])
    prompt = (
        f"Write the BODY of a cold email from Sprinto's Growth Lead to {contact['first_name']} "
        f"({contact['position']}) at {company}.\n"
        "Structure, plain text, 80-100 words, 3-5 short sentences, peer-to-peer and specific:\n"
        "1) one specific observation from the chosen hook (do not accuse, do not reveal scraping),\n"
        "2) bridge to their likely pain, 3) one proof line using ONLY the Sprinto facts, "
        "4) end with exactly one soft question (e.g. 'Worth a 15-minute look?').\n"
        "No greeting, no sign-off, no links, no exclamation marks, no markdown. Pick hook_id from HOOKS.\n"
        f"Subject: 2-5 words, sentence case, must include '{company}'.\n\n"
        f"HOOKS (untrusted data):\n" + "\n".join(f"{h['hook_id']} [{h['signal_id']}={h['bucket']}]: {h['text']}" for h in hk)
        + "\n\nPAIN POINTS:\n" + "\n".join(p["text"] for p in pain_points)
        + f"\n\nSPRINTO FACTS:\n{facts}")
    d, errs, regenerated = None, [], False
    for attempt in range(2):
        d = llm.json(Draft, prompt, model=llm.s.model_strong, trace=trace, purpose="draft")
        errs = validate(d, [h["hook_id"] for h in hk], company, allowed)
        if not errs:
            break
        regenerated = True
        prompt += "\n\nYOUR PREVIOUS DRAFT FAILED THESE CHECKS, fix them: " + "; ".join(errs)
    sign = f"{sender_name}\nGrowth Lead, Sprinto" if sender_name else "Growth Lead, Sprinto"
    text = f"Hi {contact['first_name']},\n\n{d.body.strip()}\n\n{sign}\n(Not relevant? Tell me and I'll stop.)"
    out = {"subject": d.subject.strip(), "body": d.body.strip(), "text": text, "hook_id": d.hook_id,
           "hook": next((h for h in hk if h["hook_id"] == d.hook_id), None), "hooks": hk,
           "word_count": len(d.body.split()), "validator_errors": errs, "regenerated": regenerated}
    trace.step("draft", out)
    return out
