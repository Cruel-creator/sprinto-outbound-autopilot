"""Batch runner: python run.py domains.txt [--force] [--only DOMAIN]. Never prompts; one status per company."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from config import ConfigError, load_settings
from pipeline import cache, scrape
from pipeline.agent import run_loop
from pipeline.compose import draft, pains
from pipeline.contacts import find_contact, leaders
from pipeline.extract import extract
from pipeline.llm import LLM
from pipeline.qualify import load_icp
from pipeline.report import rebuild, write_report
from pipeline.send import footer, send_email
from pipeline.tools import Tools
from pipeline.trace import OUT, Trace


def clean_domain(text: str) -> str:
    d = text.split("#")[0].strip().lower().removeprefix("https://").removeprefix("http://").strip("/")
    return d.removeprefix("www.")


def read_domains(path: Path) -> list[str]:
    return [d for line in path.read_text(encoding="utf-8-sig").splitlines() if (d := clean_domain(line))]


def process(domain: str, s, llm, http, icp: dict, out_dir: Path = OUT) -> dict:
    t = Trace(domain, out_dir)
    row, step, t0 = {"domain": domain}, "scrape", time.monotonic()
    try:
        pages = scrape.scrape(domain, t, http)
        if not any(p.outcome == "OK" for p in pages):
            t.data["status"] = "insufficient_data"
            row["reason"] = "no page could be fetched (blocked/timeout/empty); unknown, not a rejection"
            return row
        step = "extract"
        prof, _ = extract(domain, pages, llm, t)
        step = "qualify"
        q = run_loop(domain, prof, pages, t, llm, icp, Tools(domain, prof.name, pages, t, llm, http))
        row.update(verdict=q["verdict"], score=q["score"], reason=q["reason"])
        if q["verdict"] not in ("QUALIFY", "PRIORITY"):
            t.data["status"] = "insufficient_data" if q["verdict"] == "INSUFFICIENT_DATA" else "not_qualified"
            return row
        step = "contact"
        c = find_contact(domain, prof.headcount, s.hunter_api_key, http, t,
                         lookup=lambda: leaders(prof.name, domain, s.hunter_api_key, http, llm, t))
        if not c["chosen"]:
            t.data["status"] = "no_contact"
            return row
        who = c["chosen"]
        row["contact"] = f"{who['first_name']} {who['last_name']} ({who['position']})"
        step = "pains"
        p = pains(q, who, t, llm)
        step = "draft"
        d = draft(prof.name, q, who, p, t, llm, s.sender_name)
        if d["validator_errors"]:   # kill criterion: an email with unchecked claims never goes out
            t.data["status"] = "held"
            row["reason"] = "email held for review, failed checks: " + "; ".join(d["validator_errors"])
            return row
        step = "send"
        res = send_email(d["subject"], d["text"] + footer(who), s, http)
        t.step("send", res)
        if res["error"]:
            raise RuntimeError(res["error"])
        t.data["status"] = "sent"
        return row
    except Exception as e:  # one bad domain never stops the batch
        msg = f"{type(e).__name__}: {e}"
        for secret in s.secrets:
            msg = msg.replace(secret, "***")
        t.data.update(status="failed", failed_step=step, error=msg[:300])
        row["reason"] = f"failed at {step}: {msg[:120]}"
        return row
    finally:
        row["status"] = t.data["status"]
        t.data.update(reason=row.get("reason", ""), seconds=round(time.monotonic() - t0, 1))
        t.flush()
        write_report(t.data, s.to_email, out_dir)


def load_trace(domain: str, out_dir: Path = OUT) -> Trace:
    t = Trace(domain, out_dir)
    t.data = json.loads(t.path.read_text(encoding="utf-8"))
    return t


def redraft(domain: str, s, llm, note: str = "", out_dir: Path = OUT) -> dict:
    """Rewrite only the email: research, score and contact stay; drafts are asked for fresh; nothing is sent."""
    t = load_trace(domain, out_dir)
    st = t.data["steps"]
    q, who = st.get("qualify"), (st.get("contact") or {}).get("chosen")
    if not q or q["verdict"] not in ("QUALIFY", "PRIORITY") or not who:
        raise ValueError("only a qualified company with a contact can get a new email")
    if st.get("draft"):
        st.setdefault("draft_history", []).append(st["draft"])
    p = pains(q, who, t, llm, fresh=True)
    d = draft(st["extract"]["name"], q, who, p, t, llm, s.sender_name, fresh=True, note=note)
    errs = d["validator_errors"]
    t.data.update(status="held" if errs else "ready",
                  reason=("email held for review, failed checks: " + "; ".join(errs)) if errs else "new draft ready to send")
    t.flush()
    write_report(t.data, s.to_email, out_dir)
    return {"domain": domain, "status": t.data["status"]}


def send_draft(domain: str, s, http=None, out_dir: Path = OUT) -> dict:
    """Send the reviewed draft to your own inbox. Only a draft that passed every check can be sent."""
    t = load_trace(domain, out_dir)
    st = t.data["steps"]
    d, who = st.get("draft"), (st.get("contact") or {}).get("chosen")
    if t.data["status"] != "ready" or not d or d["validator_errors"] or not who:
        raise ValueError("there is no checked draft waiting to be sent")
    res = send_email(d["subject"], d["text"] + footer(who), s, http)
    if res["error"]:
        raise RuntimeError(res["error"])
    if st.get("send"):
        st.setdefault("send_history", []).append(st["send"])
    t.data.update(status="sent", reason="")
    t.step("send", res)
    write_report(t.data, s.to_email, out_dir)
    return res


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Sprinto outbound autopilot")
    ap.add_argument("domains", type=Path)
    ap.add_argument("--force", action="store_true", help="ignore caches (spends Hunter + Gemini quota)")
    ap.add_argument("--only", help="run a single domain from the list")
    ap.add_argument("--report-only", action="store_true", help="re-render reports from out/*/trace.json, no API calls")
    args = ap.parse_args(argv)
    try:
        s = load_settings()
    except ConfigError as e:
        print(f"CONFIG ERROR: {e}")
        return 1
    cache.FORCE = args.force
    domains = [d for d in read_domains(args.domains) if not args.only or d == args.only.lower()]
    if not args.report_only:
        llm, http, icp = LLM(s), scrape.client(), load_icp()
        for d in domains:
            print(f"-> {d} ...", flush=True)
            row = process(d, s, llm, http, icp)
            print(f"   {row['status']:<17} {row.get('verdict', '')} {row.get('score', '')}  {row.get('contact', '')}")
    OUT.mkdir(exist_ok=True)
    rebuild(OUT, s.to_email, read_domains(args.domains))   # whole list, so --only keeps the other rows
    print(f"\nWrote {OUT / 'summary.md'}, {OUT / 'review.csv'} and out/<domain>/report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
