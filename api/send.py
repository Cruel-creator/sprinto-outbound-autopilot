"""POST /api/send {domain, subject, text, ts, sig}: send a draft this server wrote to the owner's inbox only."""
from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # project root, so `api` and `pipeline` import

from api._shared import account, client_ip, limited, read_json, reply, scrub, settings, signed_ok
from pipeline.send import send_email


def send(body: dict, s) -> tuple[int, dict]:
    domain, subject, text = str(body.get("domain") or ""), str(body.get("subject") or ""), str(body.get("text") or "")
    data = account(domain)
    if not data:
        return 404, {"error": "unknown company"}
    if not signed_ok(domain, subject, text, body.get("ts"), body.get("sig")):
        return 403, {"error": "only a draft written here in the last hour can be sent; write a new version first"}
    who = (data["trace"]["steps"].get("contact") or {}).get("chosen") or {}
    name = f"{who.get('first_name', '')} {who.get('last_name', '')}".strip()
    note = (f"\n\n---\nIntended recipient: {name}, {who.get('position', '')} (contact details hidden on the public demo). "
            "Sent to you from the live demo, not to them.")
    res = send_email(subject, text + note, s)
    if res["error"]:
        return 502, {"error": f"Resend refused it: {scrub(str(res['error']), s)}"}
    return 200, {"sent_at": res["sent_at"]}   # never echo the inbox address


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body, s = read_json(self), None
        if limited("send", client_ip(self)):
            return reply(self, 429, {"error": "too many sends from you this hour; try again later"})
        try:
            s = settings()
            code, out = send(body, s)
        except Exception as e:
            return reply(self, 502, {"error": f"sending failed: {scrub(f'{type(e).__name__}: {e}', s)}"})
        reply(self, code, out)

    def do_GET(self):
        reply(self, 405, {"error": "use POST"})
