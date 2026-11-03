import json
from types import SimpleNamespace

import pytest
from google.genai import errors

from conftest import ScriptedClient, parsed
from pipeline import cache
from pipeline.llm import LLM
from pipeline.models import Pains, PainPoint
from pipeline.trace import Trace

P = Pains(pains=[PainPoint(text="x", evidence_ids=["E1"])])


def _err(code):
    return errors.ClientError(code, {"error": {"code": code, "message": "m", "status": "S"}})


def test_json_is_cached(settings):
    client = ScriptedClient(parsed(P))
    llm = LLM(settings, client=client, backoff=())
    assert llm.json(Pains, "prompt") == P
    assert llm.json(Pains, "prompt") == P      # second call served from cache
    assert len(client.calls) == 1


def test_force_bypasses_cache(settings, monkeypatch):
    client = ScriptedClient(parsed(P), parsed(P))
    llm = LLM(settings, client=client, backoff=())
    llm.json(Pains, "prompt")
    monkeypatch.setattr(cache, "FORCE", True)
    llm.json(Pains, "prompt")
    assert len(client.calls) == 2


def test_429_is_retried(settings):
    client = ScriptedClient(_err(429), parsed(P))
    assert LLM(settings, client=client, backoff=(0,)).json(Pains, "p") == P
    assert len(client.calls) == 2


def test_400_is_not_retried(settings):
    client = ScriptedClient(_err(400), parsed(P))
    with pytest.raises(errors.ClientError):
        LLM(settings, client=client, backoff=(0, 0)).json(Pains, "p")


def test_grounded_returns_sources(settings):
    web = SimpleNamespace(uri="https://r/1", title="techcrunch.com", domain="techcrunch.com")
    gm = SimpleNamespace(grounding_chunks=[SimpleNamespace(web=web)], web_search_queries=["q"])
    r = SimpleNamespace(text="Raised $6M", candidates=[SimpleNamespace(grounding_metadata=gm)], model_version="g1")
    out = LLM(settings, client=ScriptedClient(r), backoff=()).grounded("funding?")
    assert out == {"text": "Raised $6M", "sources": [{"uri": "https://r/1", "title": "techcrunch.com",
                                                      "domain": "techcrunch.com"}], "queries": ["q"]}


def test_trace_ledger_and_flush(tmp_path):
    t = Trace("acme.com", out_dir=tmp_path)
    a = t.add_evidence("https://acme.com/", "We are SOC 2", True, "extract")
    b = t.add_evidence("https://acme.com/", "We are SOC 2", True, "extract")
    c = t.add_evidence("https://acme.com/x", "Other", False, "web_research")
    assert (a, b, c) == ("E1", "E1", "E2")
    t.step("scrape", {"pages": 1})
    data = json.loads((tmp_path / "acme.com" / "trace.json").read_text(encoding="utf-8"))
    assert data["steps"]["scrape"] == {"pages": 1} and len(data["evidence"]) == 2
