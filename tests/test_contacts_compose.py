from types import SimpleNamespace

import httpx
import respx

from pipeline import compose, contacts
from pipeline.models import Candidate, Draft, PainPoint, Pains
from pipeline.trace import Trace

HUNTER = {"data": {"emails": [
    {"value": "sam@acme.com", "first_name": "Sam", "last_name": "Lee", "position": "VP Sales"},
    {"value": "ana@acme.com", "first_name": "Ana", "last_name": "Diaz", "position": "CTO"},
    {"value": "raj@acme.com", "first_name": "Raj", "last_name": "Iyer", "position": "Co-founder & CEO"},
    {"value": "kim@acme.com", "first_name": "Kim", "last_name": "Ho", "position": "Head of Security"},
]}}


def _c(pos, name="X"):
    return Candidate(first_name=name, position=pos, email=f"{name}@acme.com")


def test_role_rules_by_size():
    cands = [_c("VP Sales", "Sam"), _c("CTO", "Ana"), _c("Co-founder & CEO", "Raj"), _c("Head of Security", "Kim")]
    assert contacts.choose(cands, 30)["chosen"]["first_name"] == "Raj"
    assert contacts.choose(cands, 50)["chosen"]["first_name"] == "Raj"      # boundary: 50 uses the small rule
    assert contacts.choose(cands, 120)["chosen"]["first_name"] == "Kim"     # security lead promoted
    assert contacts.choose(cands[:3], 120)["chosen"]["first_name"] == "Ana"
    assert contacts.choose(cands, 300)["chosen"]["first_name"] == "Kim"
    assert contacts.choose([_c("Security Engineer"), _c("VP Sales")], 120)["chosen"] is None


@respx.mock
def test_hunter_cached_and_csv_override(tmp_path, monkeypatch):
    route = respx.get(contacts.HUNTER_SEARCH).mock(return_value=httpx.Response(200, json=HUNTER))
    monkeypatch.setattr(contacts, "CSV_PATH", tmp_path / "contacts.csv")
    t = Trace("acme.com", out_dir=tmp_path)
    assert contacts.find_contact("acme.com", 30, "k", httpx.Client(), t)["chosen"]["first_name"] == "Raj"
    contacts.find_contact("acme.com", 30, "k", httpx.Client(), t)
    assert route.call_count == 1                                            # second run spends no credits
    (tmp_path / "contacts.csv").write_text("domain,first_name,last_name,title,email,linkedin\n"
                                           "acme.com,Zoe,Ng,CEO,zoe@acme.com,\n", encoding="utf-8")
    assert contacts.find_contact("acme.com", 30, "k", httpx.Client(), t)["chosen"]["source"] == "csv"


@respx.mock
def test_hunter_error_means_no_contact(tmp_path, monkeypatch):
    respx.get(contacts.HUNTER_SEARCH).mock(return_value=httpx.Response(429))
    monkeypatch.setattr(contacts, "CSV_PATH", tmp_path / "none.csv")
    out = contacts.find_contact("acme.com", 30, "k", httpx.Client(), Trace("acme.com", out_dir=tmp_path))
    assert out["chosen"] is None and out["error"] == "hunter HTTP 429"


# ---------- compose ----------
QUAL = {"signals": [
    {"signal_id": "C1_certification_gap", "bucket": "no_trust_page_and_no_certs", "points": 12, "evidence_ids": ["E1"]},
    {"signal_id": "B1_enterprise_motion", "bucket": "one_of_them", "points": 5, "evidence_ids": ["E2"]},
    {"signal_id": "C4_recent_funding", "bucket": "within_6_months", "points": 0, "evidence_ids": []},
]}
CONTACT = {"first_name": "raj", "position": "Co-founder & CEO"}
GOOD = Draft(hook_id="H1", subject="SOC 2 at Acme", body=(
    "Noticed Acme sells an Enterprise plan to banks, but the site does not mention SOC 2 or ISO 27001 yet. "
    "Founders in that spot often see security reviews add weeks to every enterprise deal. "
    "Sprinto helped GeoIQ get SOC 2 and ISO 27001 in 3 months. Worth a 15-minute look?"))


class FakeLLM:
    def __init__(self, *outs):
        self.outs, self.s = list(outs), SimpleNamespace(model_strong="m")

    def json(self, schema, prompt, **kw):
        return self.outs.pop(0)


def _trace(tmp_path):
    t = Trace("acme.com", out_dir=tmp_path)
    t.add_evidence("https://acme.com/security", "GET /security -> NOT_FOUND", True, "scrape")
    t.add_evidence("https://acme.com/pricing", "Enterprise: contact us", True, "extract")
    return t


def test_hooks_follow_priority_and_need_points(tmp_path):
    hk = compose.hooks(QUAL, _trace(tmp_path))
    assert [h["signal_id"] for h in hk] == ["B1_enterprise_motion"]   # C1 cites only a fetch result: not a hook
    t = _trace(tmp_path)
    t.add_evidence("https://acme.com/", "Built for banks; security docs on request", True, "extract")   # E3
    qual = {"signals": [dict(s, evidence_ids=["E1", "E3"]) if s["signal_id"] == "C1_certification_gap" else s
                        for s in QUAL["signals"]]}
    assert [h["signal_id"] for h in compose.hooks(qual, t)] == ["C1_certification_gap", "B1_enterprise_motion"]


def test_pains_drop_uncited(tmp_path):
    llm = FakeLLM(Pains(pains=[PainPoint(text="a", evidence_ids=["E1"]), PainPoint(text="b", evidence_ids=["E99"])]),
                  Pains(pains=[PainPoint(text="a", evidence_ids=["E1"]), PainPoint(text="c", evidence_ids=["E2"])]))
    assert [p["text"] for p in compose.pains(QUAL, CONTACT, _trace(tmp_path), llm)] == ["a", "c"]


def test_validator_rules():
    ok = compose.validate(GOOD, ["H1"], "Acme", "3 months 27001 2")
    assert ok == []
    bad = GOOD.model_copy(update={"body": GOOD.body + " Revolutionary! Also 40% cheaper? " + "word " * 80,
                                  "hook_id": "H9", "subject": "Quick question"})
    errs = " | ".join(compose.validate(bad, ["H1"], "Acme", "3 months 27001 2"))
    for e in ("words (max 110)", "exactly one question", "exclamation", "banned phrase: revolutionary",
              "hook_id H9", "subject must", "numbers not backed"):
        assert e in errs, e


def test_draft_adds_greeting_signoff_and_regenerates(tmp_path):
    bad = GOOD.model_copy(update={"body": "Hi Raj, " + GOOD.body})
    out = compose.draft("Acme", QUAL, CONTACT, [], _trace(tmp_path), FakeLLM(bad, GOOD), "Asha")
    assert out["regenerated"] and out["validator_errors"] == []
    assert out["text"].startswith("Hi raj,\n\n")                     # first name kept verbatim, never .title()
    assert out["text"].endswith("Asha\nGrowth Lead, Sprinto\n(Not relevant? Tell me and I'll stop.)")
    assert out["hook"]["signal_id"] == "B1_enterprise_motion"


@respx.mock
def test_leader_fallback_uses_only_names_in_search_text(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from pipeline.contacts import HUNTER_FINDER, find_contact, leaders
    from pipeline.models import Leader, Leaders
    from pipeline.trace import Trace
    monkeypatch.setattr(contacts, "CSV_PATH", tmp_path / "none.csv")
    respx.get(contacts.HUNTER_SEARCH).mock(return_value=httpx.Response(200, json={"data": {"emails": [
        {"value": "x@acme.com", "first_name": "Sid", "last_name": "B", "position": None}]}}))
    finder = respx.get(HUNTER_FINDER).mock(return_value=httpx.Response(200, json={"data": {"email": "maya@acme.com",
                                                                                          "score": 91}}))
    llm = SimpleNamespace(
        grounded=lambda p, trace=None: {"text": "Acme was founded by Maya Rao (CEO).", "sources": [], "queries": []},
        json=lambda schema, p, **kw: Leaders(leaders=[Leader(first_name="Maya", last_name="Rao", title="Co-founder & CEO"),
                                                      Leader(first_name="Ghost", last_name="Person", title="CTO")]))
    t, http = Trace("acme.com", out_dir=tmp_path), httpx.Client()
    c = find_contact("acme.com", None, "k", http, t, lookup=lambda: leaders("Acme", "acme.com", "k", http, llm, t))
    assert c["chosen"]["email"] == "maya@acme.com" and "email-finder" in c["chosen"]["source"]
    assert finder.call_count == 1          # the invented "Ghost Person" is never looked up
    assert "Email Finder" in c["fallback"]
