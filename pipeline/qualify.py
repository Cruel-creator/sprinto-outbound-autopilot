"""Step 3a: deterministic ICP scoring. The LLM picks buckets + cites evidence; Python does the maths."""
from __future__ import annotations

from pathlib import Path

import yaml

from pipeline.models import Assessment, Page

ICP_PATH = Path(__file__).resolve().parents[1] / "config" / "icp.yaml"


def load_icp(path: Path = ICP_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def weight(sig: dict) -> int:
    return max(sig["buckets"].values())


def _counts(eid: str, trace) -> bool:
    """Evidence backs a claim if it exists and is verified on-page, or came from grounded search."""
    e = trace.evidence(eid)
    return bool(e) and (e["verified"] or e["added_by"] == "web_research")


def sprinto_hosted(pages: list[Page], trace) -> str | None:
    for p in pages:
        for h in p.hrefs:
            if ".trust.site" in h or "sprinto.com" in h:
                return trace.add_evidence(p.url, f"link: {h}", True, "scrape")
    return None


def score(icp: dict, a: Assessment, trace, pages: list[Page]) -> dict:
    calls = {c.signal_id: c for c in a.signals}
    signals, lo, unknown_max, block_pts, block_max = [], 0, 0, {}, {}
    for sid, sig in icp["signals"].items():
        c = calls.get(sid)
        bucket = c.bucket if c and c.bucket in sig["buckets"] else "unknown"
        ids = [i for i in (c.evidence_ids if c else []) if _counts(i, trace)]
        pts = sig["buckets"].get(bucket, 0)
        state = "unknown" if bucket == "unknown" else ("present" if pts else "absent")
        if pts and not ids:  # positive points need evidence
            state, pts = "unknown", 0
        w = weight(sig)
        lo += pts
        unknown_max += w if state == "unknown" else 0
        block_pts[sig["block"]] = block_pts.get(sig["block"], 0) + pts
        block_max[sig["block"]] = block_max.get(sig["block"], 0) + (w if state == "unknown" else pts)
        signals.append({"signal_id": sid, "bucket": bucket, "state": state, "points": pts, "max": w,
                        "evidence_ids": ids})
    hi = lo + unknown_max

    disq = None
    gate_ids = [g for g in a.gates if g.hit and g.gate_id in icp["hard_disqualifiers"]
                and any(_counts(i, trace) for i in g.evidence_ids)]
    sprinto = sprinto_hosted(pages, trace)
    if sprinto:
        disq = {"gate_id": "existing_sprinto_customer", "evidence_ids": [sprinto]}
    elif gate_ids:
        disq = {"gate_id": gate_ids[0].gate_id, "evidence_ids": gate_ids[0].evidence_ids}

    caps, tags = [], []
    up = icp["caps"]["no_upmarket_pull"]
    if block_pts.get(up["block"], 0) < up["below"]:
        caps.append("no_upmarket_pull")
        lo = min(lo, up["cap"])
        if block_max.get(up["block"], 0) < up["below"]:
            hi = min(hi, up["cap"])
    fc = icp["caps"]["fully_certified"]
    if next(s for s in signals if s["signal_id"].startswith(fc["signal"]))["bucket"] == fc["bucket"]:
        caps.append("fully_certified")
        tags.append(fc["tag"])
        lo, hi = min(lo, fc["cap"]), min(hi, fc["cap"])
    return {"score": lo, "lo": lo, "hi": hi, "signals": signals, "disqualifier": disq, "caps": caps, "tags": tags,
            "unknown_count": sum(s["state"] == "unknown" for s in signals)}


def needs_more(res: dict, icp: dict) -> bool:
    t = icp["threshold"]["qualify"]
    return res["disqualifier"] is None and res["lo"] < t <= res["hi"]


def verdict(res: dict, icp: dict) -> str:
    t = icp["threshold"]
    if res["disqualifier"]:
        return "DISQUALIFIED"
    if res["lo"] >= t["priority"]:
        return "PRIORITY"
    if res["lo"] >= t["qualify"]:
        return "QUALIFY"
    if res["lo"] >= t["nurture"] and res["hi"] >= t["qualify"]:
        return "INSUFFICIENT_DATA"   # near the bar with unknowns left after the loop
    return "NURTURE" if res["lo"] >= t["nurture"] else "REJECT"


def reason(res: dict, icp: dict, trace) -> str:
    if res["disqualifier"]:
        g = res["disqualifier"]["gate_id"]
        return f"Disqualified ({g}): {icp['hard_disqualifiers'][g]}"
    pos = sorted((s for s in res["signals"] if s["points"]), key=lambda s: -s["points"])[:3]
    neg = [s for s in res["signals"] if s["state"] == "absent"][:2]
    unk = [s["signal_id"] for s in res["signals"] if s["state"] == "unknown"]
    parts = [f"Score {res['score']}/100 (bounds {res['lo']}-{res['hi']})."]
    if pos:
        parts.append("Strongest: " + ", ".join(f"{s['signal_id']}={s['bucket']} (+{s['points']})" for s in pos) + ".")
    if neg:
        parts.append("Missing: " + ", ".join(f"{s['signal_id']}={s['bucket']}" for s in neg) + ".")
    if res["caps"]:
        parts.append("Caps: " + ", ".join(res["caps"]) + ".")
    if unk:
        parts.append(f"Unknown: {', '.join(unk)}.")
    return " ".join(parts)
