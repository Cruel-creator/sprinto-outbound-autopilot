"""report.md + summary.md rendered from the trace. No LLM calls."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote


def _ev(data: dict, eid: str) -> str:
    e = next((x for x in data["evidence"] if x["id"] == eid), None)
    if not e:
        return f"{eid} (missing)"
    mark = "verified" if e["verified"] else "unverified, from search"
    return f'{eid} "{e["quote"][:160]}" ({e["source_url"]}, {mark})'


def gmail_link(to_email: str, subject: str, text: str) -> str:
    return f"https://mail.google.com/mail/?view=cm&to={quote(to_email)}&su={quote(subject)}&body={quote(text)}"


def render(data: dict, to_email: str) -> str:
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
                  q["reason"], "", "| Signal | Bucket | Points | Evidence |", "|---|---|---|---|"]
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
        lines += [f"Rule: {c['rule_fired']}", f"Reason: {c['reason']}",
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
                     + (" (regenerated once)" if d["regenerated"] else ""))
        lines += ["\n### Email as sent", f"**Subject:** {d['subject']}", "", "```", d["text"], "```",
                  f"\n[Open in Gmail (manual fallback, to yourself)]({gmail_link(to_email, d['subject'], d['text'])})"]
    if "send" in st:
        s = st["send"]
        lines.append(f"\nSend: {'id ' + s['id'] + ' to ' + s['to'] if s['id'] else 'FAILED ' + str(s['error'])}")
    return "\n".join(lines) + "\n"


def write_report(data: dict, to_email: str, out_dir: Path) -> None:
    p = out_dir / data["domain"] / "report.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(data, to_email), encoding="utf-8")


def summary(rows: list[dict]) -> str:
    out = ["# Run summary", "", "| Domain | Status | Verdict | Score | Contact | Reason |", "|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['domain']} | {r['status']} | {r.get('verdict', '')} | {r.get('score', '')} | "
                   f"{r.get('contact', '')} | {r.get('reason', '')[:160]} |")
    return "\n".join(out) + "\n"
