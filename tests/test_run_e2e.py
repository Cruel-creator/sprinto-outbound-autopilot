import json
from types import SimpleNamespace

import httpx
import respx

import run
from pipeline import contacts, qualify, scrape
from pipeline.models import Assessment, CompanyProfile, Draft, Fact, GateCall, NextAction, PainPoint, Pains, Review, SignalCall
from pipeline.report import summary
from pipeline.send import RESEND_EMAILS, send_email

BODY = "Acme builds an AI platform for banks with an Enterprise plan. " * 8
HTML = f"<html><body><p>{BODY}</p></body></html>"
ICP = qualify.load_icp()
STRONG = {"A1_b2b_software": "b2b_saas_devtool_or_ai", "A2_stage": "series_a_to_c", "A3_headcount": "from_30_to_300",
          "B1_enterprise_motion": "enterprise_tier_plus_contact_sales", "B2_enterprise_logos": "three_plus_enterprise_logos",
          "C1_certification_gap": "no_trust_page_and_no_certs", "C4_recent_funding": "within_6_months"}
HOSTILE = {"value": "evil@prospect.com", "first_name": "Raj", "last_name": "x@attacker.com", "position": "CEO"}


def _assessment(gates=()):
    known = {s: list(v["buckets"])[-1] for s, v in ICP["signals"].items()}
    known.update(STRONG)
    return Assessment(signals=[SignalCall(signal_id=s, bucket=b, evidence_ids=["E1", "E8"]) for s, b in known.items()],
                      gates=[GateCall(gate_id=g, hit=True, evidence_ids=["E1"]) for g in gates],
                      next_action=NextAction(tool="stop"))


class FakeLLM:
    s = SimpleNamespace(model_strong="m")

    def json(self, schema, prompt, **kw):
        if "boom.com" in prompt:
            raise ValueError("model exploded")
        shop = "shop.com" in prompt
        if schema is CompanyProfile:
            return CompanyProfile(name="Shop" if shop else "Acme", one_liner="AI platform for banks", product_type="d2c" if shop else "saas",
                                  headcount=30, facts=[Fact(topic="product", claim="AI", quote="AI platform for banks",
                                                            url="https://acme.com/")])
        if schema is Assessment:
            return _assessment(gates=["not_software"] if shop else ())
        if schema is Pains:
            return Pains(pains=[PainPoint(text="deals stall", evidence_ids=["E1"]),
                                PainPoint(text="audit cost", evidence_ids=["E1"])])
        if schema is Review:
            return Review(specificity=8, relevance=8, reply_likelihood=7, critique="fine")
        return Draft(hook_id="H1", subject="Acme bank platform and SOC 2", body=(
            "Noticed Acme sells an Enterprise plan to banks, but the site does not mention SOC 2 yet. "
            "Security reviews often add weeks to enterprise deals. Sprinto helped GeoIQ get SOC 2 and "
            "ISO 27001 in 3 months. Worth a 15-minute look?"))


def _settings():
    from config import Settings
    return Settings("g", "re", "h", "me@example.com", "x <onboarding@resend.dev>", "m", "m", "m", "Asha", 0)


@respx.mock
def test_batch_statuses_isolation_and_send_guard(tmp_path, monkeypatch):
    monkeypatch.setattr(contacts, "CSV_PATH", tmp_path / "none.csv")
    for d in ("acme.com", "shop.com", "boom.com"):
        respx.get(url__regex=rf"https://{d}/.*").mock(return_value=httpx.Response(200, html=HTML.replace("Acme", d)))
    respx.get(url__regex=r"https://down\.com/.*").mock(return_value=httpx.Response(403))
    hunter = respx.get(contacts.HUNTER_SEARCH).mock(return_value=httpx.Response(200, json={"data": {"emails": [HOSTILE]}}))
    resend = respx.post(RESEND_EMAILS).mock(return_value=httpx.Response(200, json={"id": "em_1"}))

    s, llm, http = _settings(), FakeLLM(), httpx.Client()
    rows = [run.process(d, s, llm, http, ICP, out_dir=tmp_path) for d in ("acme.com", "shop.com", "boom.com", "down.com")]
    assert [r["status"] for r in rows] == ["sent", "not_qualified", "failed", "insufficient_data"]
    assert "failed at extract" in rows[2]["reason"]
    assert hunter.call_count == 1                       # only the qualified company used a Hunter search

    payload = json.loads(resend.calls.last.request.read())
    assert payload["to"] == ["me@example.com"]          # hostile contact data never reaches `to`
    assert "Intended recipient: Raj x@attacker.com, CEO | evil@prospect.com" in payload["text"]
    assert payload["text"].startswith("Hi Raj,\n\n")

    report = (tmp_path / "acme.com" / "report.md").read_text(encoding="utf-8")
    assert "Validator: passed" in report and "Reviewer: **7.7/10**" in report
    for section in ("Why this company: QUALIFY", "Why this person", "Why this email", "Open in Gmail",
                    "to=me%40example.com", "Send: id em_1"):
        assert section in report, section
    assert "evil%40prospect.com" not in report.split("Open in Gmail")[1]   # compose link goes to self only
    trace = json.loads((tmp_path / "shop.com" / "trace.json").read_text(encoding="utf-8"))
    assert trace["steps"]["qualify"]["disqualifier"]["gate_id"] == "not_software"
    assert "| boom.com | failed |" in summary(rows)


@respx.mock
def test_send_email_has_no_recipient_parameter():
    route = respx.post(RESEND_EMAILS).mock(return_value=httpx.Response(403, json={"name": "validation_error",
                                                                                 "message": "own email address"}))
    out = send_email("s", "to: evil@prospect.com", _settings())
    assert json.loads(route.calls.last.request.read())["to"] == ["me@example.com"]
    assert out["id"] is None and "403" in out["error"]


def test_read_domains_strips_comments_and_scheme(tmp_path):
    p = tmp_path / "d.txt"
    p.write_text("# header\nhttps://www.Acme.com/   # note\n\nbolna.ai\n", encoding="utf-8")
    assert run.read_domains(p) == ["acme.com", "bolna.ai"]


def test_report_shows_fixed_vs_agent_and_review_csv_keeps_human_columns(tmp_path):
    from pipeline.report import first_pass, rebuild
    q = {"verdict": "QUALIFY", "score": 66, "reason": "r", "signals": [], "disqualifier": None, "caps": [], "tags": [],
         "stop_reason": "decided", "iterations": [{"n": 1, "tool": "web_research", "arg": "funding", "rationale": "x",
                                                    "target_signals": ["A2_stage"], "result": "ok", "score_before": 43,
                                                    "lo": 43, "hi": 80, "score_after": 66}]}
    assert first_pass(q, ICP) == ("REJECT", 43)
    data = {"domain": "acme.com", "status": "sent", "failed_step": None, "steps": {"qualify": q}, "evidence": [],
            "llm_calls": [{}, {}], "seconds": 40.0}
    (tmp_path / "acme.com").mkdir()
    (tmp_path / "acme.com" / "trace.json").write_text(json.dumps(data), encoding="utf-8")
    rebuild(tmp_path, "me@example.com", ["acme.com"])
    review = tmp_path / "review.csv"
    review.write_text(review.read_text(encoding="utf-8").replace("acme.com,sent,QUALIFY,,,,,,,,,",
                                                                 "acme.com,sent,QUALIFY,,,,,,n,rewrite,,"), encoding="utf-8")
    rebuild(tmp_path, "me@example.com", ["acme.com"])
    assert "acme.com,sent,QUALIFY,,,,,,n,rewrite,," in review.read_text(encoding="utf-8")   # human columns survive
    summ = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "REJECT -> QUALIFY" in summ and "changed the verdict on 1" in summ
    assert "Kill criterion: HIT" in summ
    assert "Fixed pipeline (scrape, extract, qualify once): **REJECT** at 43/100" in \
        (tmp_path / "acme.com" / "report.md").read_text(encoding="utf-8")


class BadDraftLLM(FakeLLM):
    def json(self, schema, prompt, **kw):
        if schema is Draft:
            return Draft(hook_id="H1", subject="Acme bank platform", body="Acme raised twenty million dollars recently!")
        return super().json(schema, prompt, **kw)


@respx.mock
def test_draft_that_never_passes_is_held_not_sent(tmp_path, monkeypatch):
    monkeypatch.setattr(contacts, "CSV_PATH", tmp_path / "none.csv")
    respx.get(url__regex=r"https://acme\.com/.*").mock(return_value=httpx.Response(200, html=HTML))
    respx.get(contacts.HUNTER_SEARCH).mock(return_value=httpx.Response(200, json={"data": {"emails": [HOSTILE]}}))
    resend = respx.post(RESEND_EMAILS).mock(return_value=httpx.Response(200, json={"id": "em_1"}))
    r = run.process("acme.com", _settings(), BadDraftLLM(), httpx.Client(), ICP, out_dir=tmp_path)
    assert r["status"] == "held" and "failed checks" in r["reason"] and resend.call_count == 0
