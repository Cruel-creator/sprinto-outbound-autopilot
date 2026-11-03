import copy
from types import SimpleNamespace

from pipeline import qualify
from pipeline.agent import run_loop
from pipeline.models import Assessment, GateCall, NextAction, Page, SignalCall
from pipeline.trace import Trace

ICP = qualify.load_icp()
STRONG = {"A1_b2b_software": "b2b_saas_devtool_or_ai", "A2_stage": "series_a_to_c", "A3_headcount": "from_30_to_300",
          "B1_enterprise_motion": "enterprise_tier_plus_contact_sales", "B2_enterprise_logos": "three_plus_enterprise_logos",
          "C1_certification_gap": "no_trust_page_and_no_certs", "C4_recent_funding": "within_6_months"}  # 63 pts


def _trace(tmp_path):
    t = Trace("acme.com", out_dir=tmp_path)
    t.add_evidence("https://acme.com/", "verified quote", True, "extract")        # E1
    t.add_evidence("https://acme.com/", "hallucinated quote", False, "extract")   # E2
    return t


def _a(buckets, ev="E1", gates=(), action=NextAction(tool="stop")):
    sigs = [SignalCall(signal_id=s, bucket=buckets.get(s, "unknown"), evidence_ids=[ev]) for s in ICP["signals"]]
    return Assessment(signals=sigs, gates=[GateCall(gate_id=g, hit=True, evidence_ids=[ev]) for g in gates],
                      next_action=action)


def _all_known(extra=None):
    known = {s: list(v["buckets"])[-1] for s, v in ICP["signals"].items()}  # every signal at its 0-point bucket
    known.update(STRONG)
    known.update(extra or {})
    return known


def test_weights_sum_to_100():
    assert sum(qualify.weight(s) for s in ICP["signals"].values()) == 100


def test_strong_company_qualifies(tmp_path):
    res = qualify.score(ICP, _a(_all_known()), _trace(tmp_path), [])
    assert res["score"] == 63 and res["lo"] == res["hi"] == 63
    assert qualify.verdict(res, ICP) == "QUALIFY"


def test_points_without_verified_evidence_count_zero(tmp_path):
    res = qualify.score(ICP, _a(_all_known(), ev="E2"), _trace(tmp_path), [])
    assert res["score"] == 0 and all(s["state"] != "present" for s in res["signals"])


def test_editing_yaml_weight_changes_verdict(tmp_path):
    icp = copy.deepcopy(ICP)
    icp["signals"]["C1_certification_gap"]["buckets"]["no_trust_page_and_no_certs"] = 6
    res = qualify.score(icp, _a(_all_known()), _trace(tmp_path), [])
    assert res["score"] == 57 and qualify.verdict(res, icp) == "NURTURE"


def test_gate_needs_evidence(tmp_path):
    t = _trace(tmp_path)
    assert qualify.score(ICP, _a(_all_known(), gates=["too_large"], ev="E2"), t, [])["disqualifier"] is None
    res = qualify.score(ICP, _a(_all_known(), gates=["too_large"]), t, [])
    assert qualify.verdict(res, ICP) == "DISQUALIFIED" and "too_large" in qualify.reason(res, ICP, t)


def test_sprinto_trust_site_is_existing_customer(tmp_path):
    page = Page(url="https://acme.com/", path="/", outcome="OK", hrefs=["https://acme.trust.site"])
    res = qualify.score(ICP, _a(_all_known()), _trace(tmp_path), [page])
    assert res["disqualifier"]["gate_id"] == "existing_sprinto_customer"


def test_fully_certified_cap_and_tag(tmp_path):
    res = qualify.score(ICP, _a(_all_known({"C1_certification_gap": "soc2_type2_plus_iso27001"})), _trace(tmp_path), [])
    assert res["score"] <= 40 and "switch_or_expand_candidate" in res["tags"]


def test_no_upmarket_pull_cap(tmp_path):
    k = _all_known({"B1_enterprise_motion": "self_serve_only", "B2_enterprise_logos": "only_smb_or_startup_logos",
                    "B3_sensitive_data": "strong", "C2_in_flight_statement": "explicit_in_progress",
                    "C3_security_hiring": "dedicated_grc_or_compliance_role"})
    res = qualify.score(ICP, _a(k), _trace(tmp_path), [])
    assert "no_upmarket_pull" in res["caps"] and res["score"] == 55


def test_unknowns_near_bar_are_insufficient(tmp_path):
    k = {s: b for s, b in _all_known().items() if s not in ("C4_recent_funding", "D3_recent_enterprise_win")}
    k["A2_stage"] = "seed_top_tier_or_yc_or_3m_plus"   # 63 - 5 - 4 = 54, hi = 54 + 5 + 3 = 62
    res = qualify.score(ICP, _a(k), _trace(tmp_path), [])
    assert (res["lo"], res["hi"]) == (54, 62) and qualify.needs_more(res, ICP)
    assert qualify.verdict(res, ICP) == "INSUFFICIENT_DATA"


# ---------- agent loop ----------
class FakeLLM:
    def __init__(self, assessments):
        self.queue, self.s = list(assessments), SimpleNamespace(model_strong="m")

    def json(self, schema, prompt, **kw):
        return self.queue.pop(0) if len(self.queue) > 1 else self.queue[0]


class FakeTools:
    def __init__(self):
        self.calls = []

    def run(self, tool, arg):
        self.calls.append((tool, arg))
        return f"{tool} ran", []


PROFILE = SimpleNamespace(name="Acme", one_liner="x", product_type="saas", headcount=None)
UNSURE = {s: b for s, b in STRONG.items() if s != "C4_recent_funding"}   # lo 58, hi >= 60


def _loop(tmp_path, actions):
    tools = FakeTools()
    llm = FakeLLM([_a(UNSURE, action=a) for a in actions])
    res = run_loop("acme.com", PROFILE, [], _trace(tmp_path), llm, ICP, tools)
    return res, tools


def test_loop_stops_at_tool_budget(tmp_path):
    acts = [NextAction(tool="fetch_page", arg=p) for p in ("/security", "/trust", "/pricing", "/about", "/blog")]
    res, tools = _loop(tmp_path, acts)
    assert len(tools.calls) == 4 and res["stop_reason"] == "tool budget spent"
    assert [i["n"] for i in res["iterations"]] == [1, 2, 3, 4] and "score_after" in res["iterations"][0]


def test_loop_search_budget_and_repeats(tmp_path):
    acts = [NextAction(tool="web_research", arg=q) for q in ("funding", "headcount", "soc2")]
    res, tools = _loop(tmp_path, acts)
    assert len(tools.calls) == 2 and res["stop_reason"] == "search budget spent"
    res, tools = _loop(tmp_path, [NextAction(tool="job_postings"), NextAction(tool="job_postings")])
    assert len(tools.calls) == 1 and res["stop_reason"].startswith("refused repeat")


def test_loop_exits_early_when_decided(tmp_path):
    tools = FakeTools()
    llm = FakeLLM([_a(_all_known(), action=NextAction(tool="web_research", arg="q"))])
    res = run_loop("acme.com", PROFILE, [], _trace(tmp_path), llm, ICP, tools)
    assert tools.calls == [] and res["verdict"] == "QUALIFY"


def _thin(t):
    """Homepage only: software + enterprise tier, the site says nothing about funding, stage, headcount or hiring."""
    return _a({"A1_b2b_software": "b2b_saas_devtool_or_ai", "B1_enterprise_motion": "enterprise_tier_plus_contact_sales",
               "B2_enterprise_logos": "three_plus_enterprise_logos", "C1_certification_gap": "no_trust_page_and_no_certs",
               "A2_stage": "none_found", "A3_headcount": "other", "C3_security_hiring": "none",
               "C4_recent_funding": "older_or_none"}, ev="E9")


def test_thin_signal_silence_is_unknown_and_triggers_the_loop(tmp_path):
    t = _trace(tmp_path)
    t.add_evidence("https://acme.com/", "verified quote 2", True, "extract")   # E3
    a = _thin(t)
    for s in a.signals:   # positives cite real evidence; external "absent" calls cite nothing
        s.evidence_ids = [] if s.signal_id in ("A2_stage", "A3_headcount", "C3_security_hiring", "C4_recent_funding") else ["E3"]
    res = qualify.score(ICP, a, t, [])
    ext = {s["signal_id"]: s["state"] for s in res["signals"] if ICP["signals"][s["signal_id"]].get("external")}
    assert set(ext.values()) == {"unknown"}
    assert res["lo"] == 38 and res["hi"] >= 60 and qualify.needs_more(res, ICP)   # a fixed pipeline would REJECT here


def test_absent_external_signal_counts_with_evidence(tmp_path):
    t = _trace(tmp_path)
    res = qualify.score(ICP, _a(_all_known({"A2_stage": "none_found"})), t, [])
    assert next(s for s in res["signals"] if s["signal_id"] == "A2_stage")["state"] == "absent"


def test_unreadable_page_is_not_evidence(tmp_path):
    t = _trace(tmp_path)
    t.add_evidence("https://acme.com/careers", "GET /careers -> EMPTY_SHELL", True, "scrape")   # E3
    res = qualify.score(ICP, _a(_all_known({"C3_security_hiring": "none"}), ev="E3"), t, [])
    assert next(s for s in res["signals"] if s["signal_id"] == "C3_security_hiring")["state"] == "unknown"
