"""Batch runner: python run.py domains.txt [--force] [--only DOMAIN]. Never prompts; one status per company."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from config import ConfigError, load_settings
from pipeline import cache, scrape
from pipeline.agent import run_loop
from pipeline.compose import draft, pains
from pipeline.contacts import find_contact
from pipeline.extract import extract
from pipeline.llm import LLM
from pipeline.qualify import load_icp
from pipeline.report import summary, write_report
from pipeline.send import footer, send_email
from pipeline.tools import Tools
from pipeline.trace import OUT, Trace


def read_domains(path: Path) -> list[str]:
    out = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        d = line.split("#")[0].strip().lower().removeprefix("https://").removeprefix("http://").strip("/")
        if d:
            out.append(d.removeprefix("www."))
    return out


def process(domain: str, s, llm, http, icp: dict, out_dir: Path = OUT) -> dict:
    t = Trace(domain, out_dir)
    row, step = {"domain": domain}, "scrape"
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
        c = find_contact(domain, prof.headcount, s.hunter_api_key, http, t)
        if not c["chosen"]:
            t.data["status"] = "no_contact"
            return row
        who = c["chosen"]
        row["contact"] = f"{who['first_name']} {who['last_name']} ({who['position']})"
        step = "pains"
        p = pains(q, who, t, llm)
        step = "draft"
        d = draft(prof.name, q, who, p, t, llm, s.sender_name)
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
        t.flush()
        write_report(t.data, s.to_email, out_dir)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Sprinto outbound autopilot")
    ap.add_argument("domains", type=Path)
    ap.add_argument("--force", action="store_true", help="ignore caches (spends Hunter + Gemini quota)")
    ap.add_argument("--only", help="run a single domain from the list")
    args = ap.parse_args(argv)
    try:
        s = load_settings()
    except ConfigError as e:
        print(f"CONFIG ERROR: {e}")
        return 1
    cache.FORCE = args.force
    domains = [d for d in read_domains(args.domains) if not args.only or d == args.only.lower()]
    llm, http, icp = LLM(s), scrape.client(), load_icp()
    rows = []
    for d in domains:
        print(f"-> {d} ...", flush=True)
        row = process(d, s, llm, http, icp)
        rows.append(row)
        print(f"   {row['status']:<17} {row.get('verdict', '')} {row.get('score', '')}  {row.get('contact', '')}")
    OUT.mkdir(exist_ok=True)
    (OUT / "summary.md").write_text(summary(rows), encoding="utf-8")
    print(f"\nWrote {OUT / 'summary.md'} and out/<domain>/report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
