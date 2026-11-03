import json
import threading
from http.server import ThreadingHTTPServer

import httpx
import pytest

import app
from config import Settings
from pipeline.report import rebuild


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "OUT", tmp_path)
    (tmp_path / "acme.com").mkdir()
    (tmp_path / "acme.com" / "trace.json").write_text(json.dumps({
        "domain": "acme.com", "status": "sent", "failed_step": None, "evidence": [], "llm_calls": [],
        "steps": {"extract": {"name": "Acme", "one_liner": "<img src=x onerror=alert(1)>", "product_type": "saas",
                              "headcount": None}}}), encoding="utf-8")
    rebuild(tmp_path, "me@example.com")
    app.Handler.settings = Settings("g", "r", "h", "me@example.com", "x", "m", "m", "m")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    monkeypatch.setattr(app, "PORT", srv.server_address[1])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_accounts_and_review_roundtrip(server, tmp_path):
    a = httpx.get(f"{server}/api/accounts").json()["accounts"][0]
    assert a["lane"] == "contacted" and a["one_liner"].startswith("<img")   # raw text; the UI renders it as text
    r = httpx.post(f"{server}/api/account/acme.com/review", json={"stage": "replied", "notes": "call Tue", "domain": "x"})
    assert r.status_code == 200 and r.json()["stage"] == "replied" and r.json()["domain"] == "acme.com"
    assert httpx.get(f"{server}/api/accounts").json()["accounts"][0]["lane"] == "replied"
    assert "call Tue" in (tmp_path / "review.csv").read_text(encoding="utf-8")


def test_guards(server):
    assert httpx.get(f"{server}/api/accounts", headers={"Host": "evil.com"}).status_code == 403          # DNS rebinding
    assert httpx.post(f"{server}/api/account/acme.com/review", content="stage=won",
                      headers={"Content-Type": "application/x-www-form-urlencoded"}).status_code == 403  # CSRF form post
    assert httpx.post(f"{server}/api/account/acme.com/review", json={"stage": "bogus"}).status_code == 400
    assert httpx.get(f"{server}/api/account/..%2F..%2Fetc").status_code == 404                           # no traversal
    assert httpx.post(f"{server}/api/run", json={"domains": ["not a domain; rm -rf"]}).status_code == 400
