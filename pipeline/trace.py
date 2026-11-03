"""Per-company trace with an append-only evidence ledger, flushed to out/<domain>/trace.json."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "out"


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


class Trace:
    def __init__(self, domain: str, out_dir: Path = OUT):
        self.path = out_dir / domain / "trace.json"
        self.data = {"domain": domain, "started": datetime.now(timezone.utc).isoformat(),
                     "status": None, "failed_step": None, "steps": {}, "evidence": [], "llm_calls": []}

    def add_evidence(self, source_url: str, quote: str, verified: bool, added_by: str) -> str:
        for e in self.data["evidence"]:
            if e["source_url"] == source_url and e["quote"] == quote:
                return e["id"]
        eid = f"E{len(self.data['evidence']) + 1}"
        self.data["evidence"].append({"id": eid, "source_url": source_url, "quote": quote[:500],
                                      "verified": verified, "added_by": added_by})
        return eid

    def evidence(self, eid: str) -> dict | None:
        return next((e for e in self.data["evidence"] if e["id"] == eid), None)

    def log_llm(self, purpose: str, model: str, model_version: str | None) -> None:
        self.data["llm_calls"].append({"purpose": purpose, "model": model, "model_version": model_version})

    def step(self, name: str, value) -> None:
        self.data["steps"][name] = value
        self.flush()

    def flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
