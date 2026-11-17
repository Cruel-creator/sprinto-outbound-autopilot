"""Local CRM for the pipeline: python app.py, then open http://127.0.0.1:8765. Listens on localhost only."""
from __future__ import annotations

import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import run
from config import ConfigError, load_settings
from pipeline import scrape
from pipeline.llm import LLM
from pipeline.qualify import load_icp
from pipeline.report import STAGES, gmail_link, read_review, rebuild, row, update_review
from pipeline.trace import OUT

PORT = 8765
WEB = Path(__file__).resolve().parent / "web"
FILES = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
         "/style.css": ("style.css", "text/css")}
VENDOR_TYPES = {".js": "text/javascript", ".css": "text/css", ".woff2": "font/woff2"}
DOMAIN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9-]{1,63})+$")
JOB = {"running": False, "action": "Researching", "queue": [], "current": None, "done": [], "error": None}
LOCK = threading.Lock()


def lane(r: dict, stage: str) -> str:
    if stage in STAGES:
        return stage
    return {"sent": "contacted", "not_qualified": "not_fit", "no_contact": "qualified",
            "held": "needs_review", "ready": "needs_review"}.get(r["status"], "needs_data")


def _trace(domain: str) -> dict | None:
    p = OUT / domain / "trace.json"
    return json.loads(p.read_text(encoding="utf-8")) if DOMAIN.match(domain) and p.exists() else None


def accounts() -> list[dict]:
    icp, review, out = load_icp(), read_review(OUT / "review.csv"), []
    for p in sorted(OUT.glob("*/trace.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        r, rv = row(data, icp), review.get(data["domain"], {})
        ext = data["steps"].get("extract") or {}
        loop = (data["steps"].get("qualify") or {}).get("iterations", [])
        r.update(name=ext.get("name") or data["domain"], one_liner=ext.get("one_liner", ""), started=data.get("started"),
                 loop=[{"tool": it["tool"], "arg": it["arg"], "before": it["score_before"],
                        "after": it.get("score_after")} for it in loop],
                 review={k: rv.get(k, "") for k in ("stage", "lead_agrees", "edit_level", "replied", "notes")})
        r["lane"] = lane(r, r["review"]["stage"])
        d = data["steps"].get("draft")
        r["draft"] = {"subject": d["subject"], "body": d["body"]} if d else None
        out.append(r)
    return out


def account(domain: str, to_email: str) -> dict | None:
    data = _trace(domain)
    if not data:
        return None
    d = data["steps"].get("draft")
    review = read_review(OUT / "review.csv").get(domain, {})
    return {"trace": data, "review": review,
            "gmail": gmail_link(to_email, d["subject"], d["text"]) if d else None}


def _start(action: str, domains: list[str], one, s) -> str | None:
    """Run one(domain) -> status for each domain in a background thread; one job at a time."""
    with LOCK:
        if JOB["running"]:
            return "something is already running; wait for it to finish"
        JOB.update(running=True, action=action, queue=list(domains), current=None, done=[], error=None)

    def work():
        try:
            while JOB["queue"]:
                JOB["current"] = JOB["queue"].pop(0)
                JOB["done"].append({"domain": JOB["current"], "status": one(JOB["current"])})
            rebuild(OUT, s.to_email)
        except Exception as e:  # surfaced in the UI; secrets scrubbed
            msg = f"{type(e).__name__}: {e}"
            for secret in s.secrets:
                msg = msg.replace(secret, "***")
            JOB["error"] = msg[:300]
        finally:
            JOB.update(running=False, current=None)

    threading.Thread(target=work, daemon=True).start()
    return None


def start_job(domains: list[str], s) -> str | None:
    ctx = {}

    def one(d):
        if not ctx:
            ctx.update(llm=LLM(s), http=scrape.client(), icp=load_icp())
        return run.process(d, s, ctx["llm"], ctx["http"], ctx["icp"])["status"]
    return _start("Researching", domains, one, s)


def start_redraft(domain: str, note: str, s) -> str | None:
    return _start("Rewriting the email for", [domain], lambda d: run.redraft(d, s, LLM(s), note, out_dir=OUT)["status"], s)


def can_redraft(data: dict) -> bool:
    q, c = data["steps"].get("qualify") or {}, data["steps"].get("contact") or {}
    return q.get("verdict") in ("QUALIFY", "PRIORITY") and bool(c.get("chosen"))


class Handler(BaseHTTPRequestHandler):
    settings = None

    def _send(self, code: int, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype if ctype.startswith("font/") else f"{ctype}; charset=utf-8")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def _local(self) -> bool:  # blocks DNS-rebinding: only our own host names are served
        return self.headers.get("Host", "") in (f"127.0.0.1:{PORT}", f"localhost:{PORT}")

    def do_GET(self):
        if not self._local():
            return self._send(403, {"error": "forbidden"})
        path = self.path.split("?")[0]
        if path in FILES:
            name, ctype = FILES[path]
            return self._send(200, (WEB / name).read_bytes(), ctype)
        if path.startswith("/vendor/"):
            root = (WEB / "vendor").resolve()
            f = (root / path[len("/vendor/"):]).resolve()
            if f.is_file() and root in f.parents and f.suffix in VENDOR_TYPES:   # no traversal outside web/vendor
                return self._send(200, f.read_bytes(), VENDOR_TYPES[f.suffix])
        if path == "/api/accounts":
            return self._send(200, {"accounts": accounts(), "stages": STAGES, "job": JOB})
        if path == "/api/job":
            return self._send(200, JOB)
        if path.startswith("/api/account/"):
            a = account(path.rsplit("/", 1)[1], self.settings.to_email)
            return self._send(200, a) if a else self._send(404, {"error": "unknown account"})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        raw = self.rfile.read(min(int(self.headers.get("Content-Length", 0) or 0), 20000))   # drain first: Windows resets unread sockets
        if not self._local() or "application/json" not in self.headers.get("Content-Type", ""):
            return self._send(403, {"error": "forbidden"})   # JSON-only also stops cross-site form posts
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            return self._send(400, {"error": "bad json"})
        path = self.path.split("?")[0]
        if path == "/api/run":
            domains = [run.clean_domain(str(d)) for d in body.get("domains", [])][:15]
            bad = [d for d in domains if not DOMAIN.match(d)]
            if not domains or bad:
                return self._send(400, {"error": f"invalid domains: {bad or 'none given'}"})
            err = start_job(domains, self.settings)
            return self._send(409, {"error": err}) if err else self._send(202, JOB)
        m = re.fullmatch(r"/api/account/([^/]+)/(review|redraft|send)", path)
        data = _trace(m.group(1)) if m else None
        if not data:
            return self._send(404, {"error": "not found"})
        domain, action = m.groups()
        if action == "review":
            if body.get("stage") not in ("", None, *STAGES):
                return self._send(400, {"error": "unknown stage"})
            try:
                return self._send(200, update_review(OUT / "review.csv", domain, body))
            except KeyError:
                return self._send(404, {"error": "run the pipeline for this account first"})
        if action == "redraft":
            if not can_redraft(data):
                return self._send(400, {"error": "only a qualified company with a contact can get a new email"})
            err = start_redraft(domain, str(body.get("note") or "")[:300], self.settings)
            return self._send(409, {"error": err}) if err else self._send(202, JOB)
        try:   # send: only a draft that passed every check, only to your own inbox
            res = run.send_draft(domain, self.settings, out_dir=OUT)
        except ValueError as e:
            return self._send(400, {"error": str(e)})
        except RuntimeError as e:
            msg = str(e)
            for secret in self.settings.secrets:
                msg = msg.replace(secret, "***")
            return self._send(502, {"error": f"Resend refused it: {msg[:200]}"})
        rebuild(OUT, self.settings.to_email)
        return self._send(200, {"id": res["id"], "sent_at": res["sent_at"]})

    def log_message(self, *args):  # keep the console quiet
        pass


def main() -> int:
    try:
        Handler.settings = load_settings()
    except ConfigError as e:
        print(f"CONFIG ERROR: {e}")
        return 1
    OUT.mkdir(exist_ok=True)
    rebuild(OUT, Handler.settings.to_email)   # make sure review.csv has a row for every account
    print(f"Sprinto Outbound CRM on http://127.0.0.1:{PORT}  (Ctrl+C to stop)")
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
