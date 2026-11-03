"""Preflight: prove every external service works. One-line failures, no tracebacks."""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from config import ConfigError, Settings, load_settings

HUNTER_ACCOUNT = "https://api.hunter.io/v2/account"
RESEND_EMAILS = "https://api.resend.com/emails"


class PreflightError(Exception):
    def __init__(self, service: str, message: str):
        super().__init__(message)
        self.service, self.message = service, message


class Ping(BaseModel):
    ok: bool
    word: str


def _scrub(text: str, secrets: list[str]) -> str:
    for s in secrets:
        if s:
            text = text.replace(s, "***")
    return " ".join(text.split())[:200]


# ---------- Hunter ----------
def check_hunter(s: Settings) -> str:
    try:
        r = httpx.get(HUNTER_ACCOUNT, headers={"X-API-KEY": s.hunter_api_key}, timeout=15)
    except httpx.HTTPError as e:
        raise PreflightError("hunter", f"network error: {type(e).__name__}") from e
    if r.status_code == 401:
        raise PreflightError("hunter", "HUNTER_API_KEY rejected (401 authentication_failed)")
    if r.status_code != 200:
        raise PreflightError("hunter", f"/account returned HTTP {r.status_code}")
    try:
        d = r.json()["data"]
        reqs = d["requests"]
        q = reqs.get("searches") or reqs["credits"]
        used, avail = int(q["used"]), int(q["available"])
        left = int(q.get("remaining", avail - used))
    except (KeyError, TypeError, ValueError) as e:
        raise PreflightError("hunter", "unexpected /account response shape") from e
    return f"plan={d.get('plan_name', '?')} searches left: {left} of {avail} (resets {d.get('reset_date', '?')})"


# ---------- Gemini ----------
def _gemini_message(model: str, step: str, e: Exception) -> str:
    if isinstance(e, errors.APIError):
        reason = ""
        try:
            reason = e.details["error"]["details"][0].get("reason", "")
        except Exception:
            pass
        msg = e.message or ""
        if reason == "API_KEY_INVALID" or "API key not valid" in msg:
            return "GEMINI_API_KEY rejected (API_KEY_INVALID)"
        if e.code == 404:
            return f"model '{model}' not found - fix GEMINI_MODEL_* in .env"
        if e.code == 429:
            return f"model '{model}' {step}: quota/rate limit hit (429 {e.status}) - grounding may need billing"
        return f"model '{model}' {step}: {e.code} {e.status} {msg[:80]}"
    if isinstance(e, httpx.HTTPError):
        return f"network error: {type(e).__name__}"
    return f"model '{model}' {step}: {type(e).__name__}: {str(e)[:80]}"


def check_gemini_structured(client, model: str) -> str:
    try:
        r = client.models.generate_content(
            model=model,
            contents='Return ok=true and word="pong".',
            config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=Ping, max_output_tokens=1024),
        )
    except Exception as e:
        raise PreflightError("gemini", _gemini_message(model, "structured", e)) from e
    if not isinstance(r.parsed, Ping):
        raise PreflightError("gemini", f"model '{model}' structured: reply did not match schema")
    return "structured OK"


def check_gemini_grounded(client, model: str) -> str:
    try:
        r = client.models.generate_content(
            model=model,
            contents="Use Google Search: what is the most recent funding round announced by Sprinto (sprinto.com)? One sentence.",
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())], max_output_tokens=1024),
        )
    except Exception as e:
        raise PreflightError("gemini", _gemini_message(model, "grounded", e)) from e
    gm = r.candidates[0].grounding_metadata if r.candidates else None
    if gm is None or not (gm.web_search_queries or gm.grounding_chunks):
        raise PreflightError("gemini", f"model '{model}' grounded: call succeeded but no grounding_metadata (search did not run)")
    return f"grounded OK ({len(gm.web_search_queries or [])} queries, {len(gm.grounding_chunks or [])} sources)"


# ---------- Resend ----------
def check_resend(s: Settings) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    payload = {
        "from": s.from_email,
        "to": [s.to_email],
        "subject": f"Sprinto Autopilot preflight {stamp}",
        "text": "Preflight OK. If you can read this in your inbox, Resend delivery works.",
    }
    try:
        r = httpx.post(RESEND_EMAILS, json=payload, timeout=20,
                       headers={"Authorization": f"Bearer {s.resend_api_key}"})
    except httpx.HTTPError as e:
        raise PreflightError("resend", f"network error: {type(e).__name__}") from e
    try:
        body = r.json()
    except ValueError:
        body = {}
    name, msg = body.get("name", ""), body.get("message", "")
    if r.is_success and body.get("id"):
        return f"sent to {s.to_email} (id {body['id']}) - now check Inbox/Spam"
    if name == "missing_api_key" or (r.status_code in (400, 401) and name == "validation_error" and "API key" in msg):
        raise PreflightError("resend", f"RESEND_API_KEY rejected ({r.status_code} {name})")
    if r.status_code == 403 and "own email address" in msg:
        raise PreflightError("resend", "TO_EMAIL must equal your Resend account email when sending from onboarding@resend.dev")
    if r.status_code == 403 and "not verified" in msg:
        raise PreflightError("resend", "FROM_EMAIL domain is not verified in Resend")
    if r.status_code == 429:
        raise PreflightError("resend", f"rate/quota limit ({name or 429})")
    raise PreflightError("resend", f"HTTP {r.status_code} {name}: {msg[:100]}")


# ---------- orchestration ----------
def run(s: Settings, out=print, send: bool = True, client=None) -> int:
    def step(label, fn, *a, required=True):
        t0 = time.monotonic()
        try:
            res = fn(*a)
        except PreflightError as e:
            if required:
                raise
            out(f"[WARN] {label:<34} {_scrub(e.message, s.secrets)} (not required)")
            return
        out(f"[PASS] {label:<34} {res} ({time.monotonic() - t0:.1f}s)")

    try:
        step("hunter /account", check_hunter, s)
        client = client or genai.Client(api_key=s.gemini_api_key, http_options=types.HttpOptions(timeout=30_000))
        for m in s.models:
            step(f"gemini {m} structured", check_gemini_structured, client, m)
            step(f"gemini {m} grounded", check_gemini_grounded, client, m,
                 required=(m == s.model_grounding))   # only the grounding model MUST ground
        if send:
            step("resend send-to-self", check_resend, s)
    except PreflightError as e:
        out(f"PREFLIGHT FAILED [{e.service}]: {_scrub(e.message, s.secrets)}")
        return 1
    except Exception as e:  # never a traceback
        out(f"PREFLIGHT FAILED [internal]: {type(e).__name__}: {_scrub(str(e), s.secrets)}")
        return 1
    out("PREFLIGHT OK")
    return 0


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-send", action="store_true", help="skip the Resend test email")
    ap.add_argument("--env-file", type=Path, help="alternate .env (e.g. one with fake keys)")
    args = ap.parse_args(argv)
    try:
        s = load_settings(args.env_file)
    except ConfigError as e:
        print(f"PREFLIGHT FAILED [config]: {e}")
        return 1
    return run(s, send=not args.no_send)


if __name__ == "__main__":
    raise SystemExit(main())
