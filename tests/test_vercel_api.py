import json
import time

import httpx
import respx

from api import _shared
from api.redraft import redraft
from api.send import send
from config import Settings
from pipeline.send import RESEND_EMAILS

S = Settings("g", "re", "", "me@example.com", "x <onboarding@resend.dev>", "m", "m", "m", "Asha", 0)


def _signed(monkeypatch, subject="Nurix AI enterprise security", text="Hi Mukesh,\n\nbody"):
    monkeypatch.setenv("DRAFT_SIGNING_KEY", "test-key")
    ts = int(time.time())
    return {"domain": "nurix.ai", "subject": subject, "text": text, "ts": ts, "sig": _shared.sign("nurix.ai", subject, text, ts)}


@respx.mock
def test_send_only_accepts_a_draft_this_server_signed(monkeypatch):
    resend = respx.post(RESEND_EMAILS).mock(return_value=httpx.Response(200, json={"id": "em_1"}))
    body = _signed(monkeypatch)
    assert send({**body, "text": "anything I like"}, S)[0] == 403                 # tampered text
    assert send({**body, "sig": "0" * 64}, S)[0] == 403                           # forged signature
    old = _signed(monkeypatch); old["ts"] -= 7200
    old["sig"] = _shared.sign("nurix.ai", old["subject"], old["text"], old["ts"])
    assert send(old, S)[0] == 403                                                 # older than an hour
    assert resend.call_count == 0
    code, out = send(body, S)
    assert code == 200 and "sent_at" in out and "me@example.com" not in json.dumps(out)
    payload = json.loads(resend.calls.last.request.read())
    assert payload["to"] == ["me@example.com"] and "contact details hidden" in payload["text"]


def test_redraft_refuses_unknown_and_unqualified_companies():
    assert redraft("not-a-company.io", "", S, None)[0] == 404
    assert redraft("../../.env", "", S, None)[0] == 404
    assert redraft("salesforce.com", "", S, None)[0] == 400                      # disqualified in the snapshot


def test_hourly_limits_per_visitor():
    _shared._hits.clear()
    assert [_shared.limited("redraft", "1.2.3.4") for _ in range(4)] == [False, False, False, True]
    assert _shared.limited("redraft", "5.6.7.8") is False                         # another visitor is unaffected
