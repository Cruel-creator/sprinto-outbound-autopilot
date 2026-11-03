import json
from types import SimpleNamespace

import httpx
import respx

import run
from pipeline import contacts, qualify, scrape
from pipeline.models import Assessment, CompanyProfile, Draft, Fact, GateCall, NextAction, PainPoint, Pains, SignalCall
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
    return Assessment(signals=[SignalCall(signal_id=s, bucket=b, evidence_ids=["E1"]) for s, b in known.items()],
                      gates=[GateCall(gate_id=g, hit=True, evidence_ids=["E1"]) for g in gates],
                      next_action=NextAction(tool="stop"))


class FakeLLM:
    s = SimpleNamespace(model_strong="m")

    def json(self, schema, prompt, **kw):
        if "boom.com" in prompt:
            raise ValueError("model exploded")
        shop = "shop.com" in prompt
        if schema is CompanyProfile:
            return CompanyProfile(name="Shop" if shop else "Acme", one_liner="x", product_type="d2c" if shop else "saas",
                                  headcount=30, facts=[Fact(topic="product", claim="AI", quote="AI platform for banks",
                                                            url="https://acme.com/")])
        if schema is Assessment:
            return _assessment(gates=["not_software"] if shop else ())
        if schema is Pains:
            return Pains(pains=[PainPoint(text="deals stall", evidence_ids=["E1"]),
                                PainPoint(text="audit cost", evidence_ids=["E1"])])
        return Draft(hook_id="H1", subject="SOC 2 at Acme", body=(
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
