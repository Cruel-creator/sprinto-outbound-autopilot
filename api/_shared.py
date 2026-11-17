"""Shared helpers for the public demo's two Vercel functions (redraft, send).

No passcode, by the owner's choice. Safety comes from three things instead:
- keys live only in Vercel's encrypted environment variables, never in a response;
- a draft can be sent only if this server wrote it (HMAC-signed, 1 hour), so nobody can mail arbitrary text;
- per-visitor hourly limits, and sending always goes to the owner's own inbox (TO_EMAIL).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import Settings          # noqa: E402
from pipeline import cache           # noqa: E402

cache.ROOT = Path("/tmp/outbound-cache")   # the deployment file system is read-only
DATA = ROOT / "site" / "data" / "account"
TMP_OUT = Path("/tmp/outbound-out")
DOMAIN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9-]{1,63})+$")
LIMITS = {"redraft": 3, "send": 5}   # per visitor per hour, per warm instance
SIGNED_FOR = 3600
_hits: dict[tuple[str, str], list[float]] = {}


def settings() -> Settings:
    env = os.environ
    missing = [k for k in ("GEMINI_API_KEY", "RESEND_API_KEY", "TO_EMAIL", "DRAFT_SIGNING_KEY") if not env.get(k)]
    if missing:
        raise RuntimeError(f"the live demo is missing settings: {', '.join(missing)}")
    fast = env.get("GEMINI_MODEL_FAST", "gemini-3.5-flash-lite")
    return Settings(env["GEMINI_API_KEY"], env["RESEND_API_KEY"], "", env["TO_EMAIL"],
                    env.get("FROM_EMAIL", "Sprinto Autopilot <onboarding@resend.dev>"), fast,
                    env.get("GEMINI_MODEL_STRONG", fast), env.get("GEMINI_MODEL_GROUNDING", fast),
                    env.get("SENDER_NAME", ""), float(env.get("GEMINI_MIN_INTERVAL", "6.5")))


def account(domain: str) -> dict | None:
    p = DATA / f"{domain}.json"
    return json.loads(p.read_text(encoding="utf-8")) if DOMAIN.match(domain or "") and p.exists() else None


def limited(kind: str, ip: str) -> bool:
    now, key = time.time(), (kind, ip)
    recent = [t for t in _hits.get(key, []) if now - t < 3600]
    _hits[key] = recent
    if len(recent) >= LIMITS[kind]:
        return True
    recent.append(now)
    return False


def sign(domain: str, subject: str, text: str, ts: int) -> str:
    msg = json.dumps([domain, subject, text, ts], ensure_ascii=False).encode()
    return hmac.new(os.environ["DRAFT_SIGNING_KEY"].encode(), msg, hashlib.sha256).hexdigest()


def signed_ok(domain: str, subject: str, text: str, ts, sig: str) -> bool:
    try:
        ts = int(ts)
    except (TypeError, ValueError):
        return False
    fresh = 0 <= time.time() - ts < SIGNED_FOR
    return fresh and isinstance(sig, str) and hmac.compare_digest(sign(domain, subject, text, ts), sig)


def scrub(msg: str, s: Settings | None) -> str:
    for secret in ([s.gemini_api_key, s.resend_api_key, s.to_email] if s else []):
        msg = msg.replace(secret, "***")
    return msg[:200]


def client_ip(handler) -> str:
    return (handler.headers.get("x-forwarded-for") or handler.client_address[0] or "?").split(",")[0].strip()


def read_json(handler) -> dict:
    raw = handler.rfile.read(min(int(handler.headers.get("Content-Length", 0) or 0), 20000))
    try:
        body = json.loads(raw or b"{}")
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def reply(handler, code: int, body: dict) -> None:
    raw = json.dumps(body).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(raw)
