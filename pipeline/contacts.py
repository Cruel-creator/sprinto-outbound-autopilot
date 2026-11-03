"""Step 4: Hunter domain search (qualified companies only, cached) + deterministic role rules."""
from __future__ import annotations

import csv
import re
from pathlib import Path

import httpx

from pipeline import cache
from pipeline.models import Candidate

HUNTER_SEARCH = "https://api.hunter.io/v2/domain-search"
CSV_PATH = Path(__file__).resolve().parents[1] / "contacts.csv"

DROP = re.compile(r"\b(sales|marketing|growth|recruit\w*|talent|hr|people|customer|account|intern|support|"
                  r"partnerships?|business development|bdr|sdr|community|content)\b", re.I)
FOUNDER = re.compile(r"\b(ceo|founder|co-?founder|chief executive)\b", re.I)
TECH = re.compile(r"\b(cto|chief technology|vp,? (of )?engineering|head of engineering|engineering director)\b", re.I)
SECURITY = re.compile(r"\b(ciso|chief information security|head of (information )?security|grc|compliance|"
                      r"(director|vp|head),? (of )?(security|risk|it))\b", re.I)


def hunter(domain: str, api_key: str, http: httpx.Client) -> tuple[list[Candidate], str]:
    k = cache.key("hunter", domain)
    data = cache.get("hunter", k)
    if data is None:
        r = http.get(HUNTER_SEARCH, params={"domain": domain, "seniority": "senior,executive", "type": "personal",
                                            "limit": 10}, headers={"X-API-KEY": api_key}, timeout=20)
        if r.status_code != 200:
            return [], f"hunter HTTP {r.status_code}"
        data = r.json()
        cache.put("hunter", k, data)
    emails = data.get("data", {}).get("emails", [])
    return [Candidate(first_name=e.get("first_name") or "", last_name=e.get("last_name") or "",
                      position=e.get("position") or "", seniority=e.get("seniority") or "",
                      email=e.get("value") or "", linkedin=e.get("linkedin") or "") for e in emails], ""


def load_csv(domain: str, path: Path | None = None) -> list[Candidate]:
    path = path or CSV_PATH
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [Candidate(first_name=r["first_name"].strip(), last_name=r.get("last_name", "").strip(),
                          position=r.get("title", "").strip(), email=r.get("email", "").strip(),
                          linkedin=r.get("linkedin", "").strip(), source="csv")
                for r in csv.DictReader(f) if r["domain"].strip().lower() == domain]


def choose(cands: list[Candidate], headcount: int | None) -> dict:
    eligible = [c for c in cands if c.first_name and c.email and not DROP.search(c.position)]
    if headcount is not None and headcount <= 50:
        rule, order = "8-50 people: founder/CEO, then CTO", [FOUNDER, TECH]
    elif headcount is not None and headcount > 200:
        rule, order = "201+ people: security/GRC lead, then CTO", [SECURITY, TECH, FOUNDER]
    else:
        size = "51-200 people" if headcount else "headcount unknown (treated as 51-200)"
        rule, order = f"{size}: security/GRC lead promoted, else CTO/VP Eng, else founder", [SECURITY, TECH, FOUNDER]
    ranked = []  # rule priority, then listed order; each person once
    for pat in order:
        ranked += [c for c in eligible if pat.search(c.position) and c not in ranked]
    considered = [f"{c.first_name} {c.last_name} ({c.position or 'no title'}, {c.source})" for c in cands]
    if not ranked:
        return {"chosen": None, "runner_up": None, "rule_fired": rule, "considered": considered,
                "reason": "No eligible decision-maker (dropped sales/marketing/HR/CS titles); nobody invented."}
    c = ranked[0]
    return {"chosen": c.model_dump(), "runner_up": ranked[1].model_dump() if len(ranked) > 1 else None,
            "rule_fired": rule, "considered": considered,
            "reason": f"{c.first_name} {c.last_name} is {c.position} at a company where rule '{rule}' applies; "
                      f"this role owns the compliance/enterprise-deal problem. Source: {c.source}."}


def find_contact(domain: str, headcount: int | None, api_key: str, http: httpx.Client, trace) -> dict:
    cands, err = load_csv(domain), ""
    if not cands:
        cands, err = hunter(domain, api_key, http)
    out = choose(cands, headcount)
    out["error"] = err
    trace.step("contact", out)
    return out
