"""report.md, summary.md and review.csv rendered from the traces. No LLM calls."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from urllib.parse import quote

from pipeline.qualify import load_icp, verdict

REVIEW_COLS = ["domain", "status", "verdict", "contact", "subject", "sent_at", "ai_score",
               "stage", "lead_agrees", "edit_level", "replied", "notes"]
MACHINE_COLS, HUMAN_COLS = REVIEW_COLS[:7], REVIEW_COLS[7:]   # human columns are never overwritten
STAGES = ["contacted", "replied", "meeting", "won", "lost"]   # set by the Growth Lead in the CRM


def first_pass(q: dict, icp: dict) -> tuple[str, int]:
    """What a fixed pipeline (no agent loop) would have decided: the first assessment, before any tool call."""
    if not q["iterations"]:
        return q["verdict"], q["score"]
    it = q["iterations"][0]
    return verdict({"disqualifier": None, "lo": it["lo"], "hi": it["hi"]}, icp), it["score_before"]


def _ev(data: dict, eid: str) -> str:
    e = next((x for x in data["evidence"] if x["id"] == eid), None)
    if not e:
        return f"{eid} (missing)"
    mark = "verified" if e["verified"] else "unverified, from search"
    return f'{eid} "{e["quote"][:160]}" ({e["source_url"]}, {mark})'


def gmail_link(to_email: str, subject: str, text: str) -> str:
    return f"https://mail.google.com/mail/?view=cm&to={quote(to_email)}&su={quote(subject)}&body={quote(text)}"


def render(data: dict, to_email: str, icp: dict | None = None) -> str:
    icp = icp or load_icp()
    st = data["steps"]
    q, c, d = st.get("qualify"), st.get("contact"), st.get("draft")
    lines = [f"# {data['domain']}: {data['status']}" + (f" (failed at {data['failed_step']})" if data["failed_step"] else "")]
    if data.get("error"):
        lines.append(f"\nError: {data['error']}")
    if "extract" in st:
        x = st["extract"]
        lines.append(f"\n**{x['name']}**: {x['one_liner']} (product_type={x['product_type']}, headcount={x['headcount']})")
    if q:
        lines += [f"\n## Why this company: {q['verdict']}, score {q['score']}/100",
                  q["reason"]]
        fv, fs = first_pass(q, icp)
        lines.append(f"\nFixed pipeline (scrape, extract, qualify once): **{fv}** at {fs}/100. "
                     f"Agent loop: **{q['verdict']}** at {q['score']}/100 after {len(q['iterations'])} tool calls."
                     + (" Thin signal: the loop changed the verdict." if fv != q["verdict"] else ""))
        lines += ["", "| Signal | Bucket | Points | Evidence |", "|---|---|---|---|"]
        for s in q["signals"]:
            ev = "<br>".join(_ev(data, i) for i in s["evidence_ids"]) or s["state"]
            lines.append(f"| {s['signal_id']} | {s['bucket']} | {s['points']}/{s['max']} | {ev} |")
        if q["disqualifier"]:
            dq = q["disqualifier"]
            lines.append(f"\nDisqualifier: **{dq['gate_id']}**, " + "; ".join(_ev(data, i) for i in dq["evidence_ids"]))
        if q["caps"]:
            lines.append(f"\nCaps fired: {', '.join(q['caps'])}. Tags: {', '.join(q['tags']) or 'none'}")
        lines.append(f"\n### Agent loop ({len(q['iterations'])} tool calls, stopped: {q['stop_reason']})")
        for it in q["iterations"]:
            lines.append(f"{it['n']}. `{it['tool']}({it['arg']})` for {it['target_signals']}: {it['rationale']} "
                         f"-> {it['result']} (score {it['score_before']} -> {it.get('score_after', '?')})")
    if c:
        lines.append("\n## Why this person")
        ch = c["chosen"]
        lines.append(f"**{ch['first_name']} {ch['last_name']}**, {ch['position']}" if ch else "No contact chosen.")
        lines += [f"Rule: {c['rule_fired']}", f"Reason: {c['reason']}"] + ([c["fallback"]] if c.get("fallback") else []) + [
                  f"Considered: {'; '.join(c['considered']) or 'none'}" + (f" (error: {c['error']})" if c.get("error") else "")]
    if "pains" in st:
        lines.append("\n## Pain points")
        lines += [f"- {p['text']} [{', '.join(p['evidence_ids'])}]" for p in st["pains"]]
    if d:
        h = d["hook"]
        lines.append("\n## Why this email")
        lines.append(f"Hook {d['hook_id']}: {h['signal_id']}={h['bucket']}, {_ev(data, h['evidence_id'])}" if h
                     else f"Hook {d['hook_id']} not in candidates.")
        lines.append(f"Words: {d['word_count']}. Validator: {'; '.join(d['validator_errors']) or 'passed'}."
                     + (f" ({len(d.get('attempts', [])) or 2} drafts)" if d["regenerated"] else ""))
        if d.get("review"):
            rv = d["review"]
            lines.append(f"Reviewer: **{rv['score']}/10** (specificity {rv['specificity']}, relevance {rv['relevance']}, "
                         f"reply {rv['reply_likelihood']}). {rv['critique']}")
        lines += ["\n### Email as sent", f"**Subject:** {d['subject']}", "", "```", d["text"], "```",
                  f"\n[Open in Gmail (manual fallback, to yourself)]({gmail_link(to_email, d['subject'], d['text'])})"]
    if "send" in st:
        s = st["send"]
        lines.append(f"\nSend: {'id ' + s['id'] + ' to ' + s['to'] if s['id'] else 'FAILED ' + str(s['error'])}")
    return "\n".join(lines) + "\n"


def write_report(data: dict, to_email: str, out_dir: Path, icp: dict | None = None) -> None:
    p = out_dir / data["domain"] / "report.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(data, to_email, icp), encoding="utf-8")


def row(data: dict, icp: dict) -> dict:
    st = data["steps"]
    q, who = st.get("qualify"), (st.get("contact") or {}).get("chosen")
    r = {"domain": data["domain"], "status": data["status"], "seconds": data.get("seconds"),
         "llm_calls": len(data["llm_calls"]),
         "reason": data.get("reason") or (q or {}).get("reason") or data.get("error") or ""}
    if q:
        fv, fs = first_pass(q, icp)
        r.update(verdict=q["verdict"], score=q["score"], fixed=fv, fixed_score=fs, tool_calls=len(q["iterations"]))
    if who:
        r["contact"] = f"{who['first_name']} {who['last_name']} ({who['position']})"
    if (st.get("send") or {}).get("id"):
        r.update(subject=st["draft"]["subject"], sent_at=st["send"]["sent_at"])
    if (st.get("draft") or {}).get("review"):
        r["ai_score"] = st["draft"]["review"]["score"]
    return r


def read_review(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {r["domain"]: r for r in csv.DictReader(f)}


def update_review(path: Path, domain: str, fields: dict) -> dict:
    """Save the Growth Lead's columns for one company (used by the CRM app)."""
    rows = read_review(path)
    if domain not in rows:
        raise KeyError(domain)
    rows[domain].update({k: str(v).strip()[:500] for k, v in fields.items() if k in HUMAN_COLS})
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=REVIEW_COLS)
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in REVIEW_COLS} for r in rows.values())
    return rows[domain]


def write_review(rows: list[dict], path: Path) -> list[dict]:
    """One row per company for the Growth Lead; their columns survive re-runs."""
    old = read_review(path)
    for r in rows:
        keep = old.get(r["domain"], {})
        old[r["domain"]] = {**{k: r.get(k) or "" for k in MACHINE_COLS}, **{k: keep.get(k, "") for k in HUMAN_COLS}}
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=REVIEW_COLS)
        w.writeheader()
        w.writerows(old.values())
    return list(old.values())


def _pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n // d}%)" if d else "n/a"


def metrics(rows: list[dict], review: list[dict]) -> list[str]:
    n, secs = len(rows), [r["seconds"] for r in rows if r.get("seconds")]
    looped = [r for r in rows if r.get("tool_calls")]
    changed = [r for r in rows if r.get("fixed") and r["fixed"] != r["verdict"]]
    out = ["", "## Run metrics (DECISIONS.md: baseline 15-20 min per company, by hand)",
           f"- Companies: {n}. Emails sent: {_pct(sum(r['status'] == 'sent' for r in rows), n)}.",
           f"- Pipeline time: {sum(secs) / len(secs):.0f} s per company on average." if secs else "- Pipeline time: n/a",
           f"- Agent loop ran on {len(looped)} thin-signal companies and changed the verdict on {len(changed)}"
           + (f": {', '.join(r['domain'] + ' ' + r['fixed'] + ' -> ' + r['verdict'] for r in changed)}." if changed else "."),
           f"- Gemini calls: {sum(r.get('llm_calls', 0) for r in rows)}."]
    scores = [r["ai_score"] for r in rows if r.get("ai_score") is not None]
    if scores:
        out.append(f"- Reviewer score: {sum(scores) / len(scores):.1f}/10 average over {len(scores)} emails.")
    done = [r for r in review if r["edit_level"].strip()]
    out.append("\n## Growth Lead review (out/review.csv)")
    if not done:
        return out + ["- Nothing reviewed yet: fill lead_agrees (y/n), edit_level (none/light/rewrite), replied (y/n)."]
    agree = sum(r["lead_agrees"].strip().lower().startswith("y") for r in done)
    rewrite = sum(r["edit_level"].strip().lower() == "rewrite" for r in done)
    replied = sum(r["replied"].strip().lower().startswith("y") for r in done)
    kill = [m for m, hit in [("rewrite share > 50%", rewrite * 2 > len(done)),
                             ("agreement < 60%", agree * 10 < 6 * len(done))] if hit]
    return out + [f"- Reviewed: {len(done)}. Lead agrees: {_pct(agree, len(done))}. "
                  f"Rewritten: {_pct(rewrite, len(done))}. Replies: {_pct(replied, len(done))}.",
                  f"- Kill criterion: {'HIT: ' + ', '.join(kill) if kill else 'not hit'}."]


def summary(rows: list[dict], review: list[dict] | None = None) -> str:
    out = ["# Run summary", "", "| Domain | Status | Fixed pipeline -> Agent loop | Score | Contact | Reason |",
           "|---|---|---|---|---|---|"]
    for r in rows:
        fx = f"{r['fixed']} -> {r['verdict']}" if r.get("fixed") else r.get("verdict", "")
        out.append(f"| {r['domain']} | {r['status']} | {fx} | {r.get('score', '')} | "
                   f"{r.get('contact', '')} | {r.get('reason', '')[:160]} |")
    return "\n".join(out + metrics(rows, review or [])) + "\n"


def rebuild(out_dir: Path, to_email: str, domains: list[str] | None = None) -> list[dict]:
    """Re-render every report, summary.md and review.csv from trace.json files. No API calls."""
    icp, rows = load_icp(), []
    paths = [out_dir / d / "trace.json" for d in domains] if domains else sorted(out_dir.glob("*/trace.json"))
    for p in paths:
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            write_report(data, to_email, out_dir, icp)
            rows.append(row(data, icp))
    review = write_review(rows, out_dir / "review.csv")
    (out_dir / "summary.md").write_text(summary(rows, review), encoding="utf-8")
    return rows
