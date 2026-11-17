"""POST /api/redraft {domain, note}: rewrite one company's email on the public demo. Nothing is stored or sent."""
from __future__ import annotations

import sys
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # project root, so `api` and `pipeline` import

from api._shared import TMP_OUT, account, client_ip, limited, read_json, reply, scrub, settings, sign
from pipeline.compose import draft, pains
from pipeline.llm import LLM
from pipeline.trace import Trace


def redraft(domain: str, note: str, s, llm) -> tuple[int, dict]:
    data = account(domain)
    if not data:
        return 404, {"error": "unknown company"}
    st = data["trace"]["steps"]
    q, who = st.get("qualify") or {}, (st.get("contact") or {}).get("chosen")
    if q.get("verdict") not in ("QUALIFY", "PRIORITY") or not who:
        return 400, {"error": "only a qualified company with a contact can get a new email"}
    t = Trace(domain, TMP_OUT)
    t.data = data["trace"]
    p = pains(q, who, t, llm, fresh=True)
    d = draft(st["extract"]["name"], q, who, p, t, llm, s.sender_name, fresh=True, note=note)
    out = {k: d[k] for k in ("subject", "body", "text", "hook", "word_count", "validator_errors", "review", "attempts")}
    if d["validator_errors"]:
        return 200, {"status": "held", "draft": out}
    ts = int(time.time())
    return 200, {"status": "ready", "draft": out, "ts": ts, "sig": sign(domain, d["subject"], d["text"], ts)}


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body, s = read_json(self), None
        if limited("redraft", client_ip(self)):
            return reply(self, 429, {"error": "too many rewrites from you this hour; try again later"})
        try:
            s = settings()
            code, out = redraft(str(body.get("domain") or ""), str(body.get("note") or "")[:300], s, LLM(s))
        except Exception as e:   # surfaced to the page with secrets scrubbed
            return reply(self, 502, {"error": f"the rewrite failed: {scrub(f'{type(e).__name__}: {e}', s)}"})
        reply(self, code, out)

    def do_GET(self):
        reply(self, 405, {"error": "use POST"})
