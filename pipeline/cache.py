"""Tiny JSON disk cache: cache/<kind>/<sha256>.json. FORCE=True bypasses reads."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "cache"
FORCE = False


def key(*parts) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def get(kind: str, k: str):
    p = ROOT / kind / f"{k}.json"
    if FORCE or not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def put(kind: str, k: str, value) -> None:
    p = ROOT / kind / f"{k}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, default=str), encoding="utf-8")
