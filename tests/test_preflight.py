from types import SimpleNamespace

import httpx
import pytest
import respx
from google.genai import errors

import preflight
from config import ConfigError, Settings, load_settings
from preflight import HUNTER_ACCOUNT, RESEND_EMAILS, Ping

ENV = """GEMINI_API_KEY=g-key-123
RESEND_API_KEY=re_key_123
HUNTER_API_KEY=h-key-123
TO_EMAIL=me@example.com
GEMINI_MODEL_FAST=m-fast
GEMINI_MODEL_STRONG=m-fast
GEMINI_MODEL_GROUNDING=m-ground
"""

S = Settings("g-key-123", "re_key_123", "h-key-123", "me@example.com", "x <onboarding@resend.dev>",
             "m-fast", "m-fast", "m-ground")

HUNTER_OK = {"data": {"plan_name": "Free", "reset_date": "2026-12-01",
                      "requests": {"searches": {"used": 3, "available": 25}}}}


def _env(tmp_path, text=ENV):
    p = tmp_path / ".env"
    p.write_text(text, encoding="utf-8")
    return p


class FakeClient:
    """Mimics genai.Client().models.generate_content for structured and grounded calls."""

    def __init__(self, fail=None, ground=True):
        self.fail, self.ground = fail, ground
        self.models = self

    def generate_content(self, model, contents, config):
        if self.fail and self.fail[0] in (model, "*"):
            raise self.fail[1]
        if config.tools:
            gm = SimpleNamespace(web_search_queries=["q"], grounding_chunks=[1]) if self.ground or model == "m-ground" else None
            return SimpleNamespace(candidates=[SimpleNamespace(grounding_metadata=gm)])
        return SimpleNamespace(parsed=Ping(ok=True, word="pong"))


def _api_error(code, message, reason=""):
    return errors.ClientError(code, {"error": {"code": code, "message": message, "status": "X",
                                               "details": [{"reason": reason}]}})


# ---------- config ----------
def test_config_env_file_beats_os_env(tmp_path):
    s = load_settings(_env(tmp_path), environ={"GEMINI_API_KEY": "stale-os-key"})
    assert s.gemini_api_key == "g-key-123"
    assert s.models == ["m-fast", "m-ground"]  # deduped


def test_config_rejects_placeholders(tmp_path):
    with pytest.raises(ConfigError, match="HUNTER_API_KEY"):
        load_settings(_env(tmp_path, ENV.replace("h-key-123", "your_hunter_api_key_here")), environ={})


def test_config_handles_bom_and_crlf(tmp_path):
    p = tmp_path / ".env"
    p.write_bytes(b"\xef\xbb\xbf" + ENV.replace("\n", "\r\n").encode())
    assert load_settings(p, environ={}).to_email == "me@example.com"


def test_config_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_settings(tmp_path / ".env", environ={})


# ---------- preflight run ----------
def _run(client, send=True):
    lines = []
    code = preflight.run(S, out=lines.append, send=send, client=client)
    return code, lines


@respx.mock
def test_all_pass_sends_only_to_self():
    respx.get(HUNTER_ACCOUNT).mock(return_value=httpx.Response(200, json=HUNTER_OK))
    send = respx.post(RESEND_EMAILS).mock(return_value=httpx.Response(200, json={"id": "abc"}))
    code, lines = _run(FakeClient())
    assert code == 0 and lines[-1] == "PREFLIGHT OK"
    assert "searches left: 22 of 25" in lines[0]
    assert b'"to":["me@example.com"]' in send.calls.last.request.read().replace(b" ", b"")


@respx.mock
def test_non_grounding_model_only_warns():
    respx.get(HUNTER_ACCOUNT).mock(return_value=httpx.Response(200, json=HUNTER_OK))
    code, lines = _run(FakeClient(ground=False), send=False)
    assert code == 0
    assert any(line.startswith("[WARN] gemini m-fast grounded") for line in lines)


@respx.mock
def test_grounding_model_must_ground():
    respx.get(HUNTER_ACCOUNT).mock(return_value=httpx.Response(200, json=HUNTER_OK))
    client = FakeClient(ground=False)
    client.generate_content = lambda model, contents, config: (
        SimpleNamespace(candidates=[SimpleNamespace(grounding_metadata=None)]) if config.tools
        else SimpleNamespace(parsed=Ping(ok=True, word="pong")))
    code, lines = _run(client, send=False)
    assert code == 1 and "no grounding_metadata" in lines[-1]


@respx.mock
def test_bad_hunter_key_one_line():
    respx.get(HUNTER_ACCOUNT).mock(return_value=httpx.Response(401, json={"errors": []}))
    code, lines = _run(FakeClient())
    assert code == 1 and lines == ["PREFLIGHT FAILED [hunter]: HUNTER_API_KEY rejected (401 authentication_failed)"]


@respx.mock
def test_bad_gemini_key():
    respx.get(HUNTER_ACCOUNT).mock(return_value=httpx.Response(200, json=HUNTER_OK))
    code, lines = _run(FakeClient(fail=("*", _api_error(400, "API key not valid", "API_KEY_INVALID"))))
    assert code == 1 and lines[-1] == "PREFLIGHT FAILED [gemini]: GEMINI_API_KEY rejected (API_KEY_INVALID)"


@respx.mock
def test_unknown_model():
    respx.get(HUNTER_ACCOUNT).mock(return_value=httpx.Response(200, json=HUNTER_OK))
    code, lines = _run(FakeClient(fail=("m-fast", _api_error(404, "not found"))))
    assert code == 1 and "model 'm-fast' not found" in lines[-1]


@respx.mock
def test_resend_sandbox_rule():
    respx.get(HUNTER_ACCOUNT).mock(return_value=httpx.Response(200, json=HUNTER_OK))
    respx.post(RESEND_EMAILS).mock(return_value=httpx.Response(403, json={
        "name": "validation_error", "message": "You can only send testing emails to your own email address"}))
    code, lines = _run(FakeClient())
    assert code == 1 and "TO_EMAIL must equal your Resend account email" in lines[-1]


@respx.mock
def test_network_error_and_secret_scrub():
    respx.get(HUNTER_ACCOUNT).mock(side_effect=httpx.ConnectError("boom h-key-123"))
    code, lines = _run(FakeClient())
    assert code == 1 and lines == ["PREFLIGHT FAILED [hunter]: network error: ConnectError"]
    assert preflight._scrub("key=h-key-123", S.secrets) == "key=***"
