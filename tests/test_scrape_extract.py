import httpx
import respx

from conftest import ScriptedClient, parsed
from pipeline import scrape
from pipeline.extract import extract
from pipeline.llm import LLM
from pipeline.models import CompanyProfile, Fact
from pipeline.trace import Trace

BODY = "Acme builds an AI platform for banks. " * 10
HOME = f"<html><body><p>{BODY}</p><footer><img alt='SOC 2 badge' src='/img/soc2.png'>" \
       f"<a href='https://trust.acme.com'>Trust</a></footer></body></html>"


def _route(path, **kw):
    return respx.get(f"https://acme.com{path}").mock(**kw)


@respx.mock
def test_typed_outcomes_and_soft_404(tmp_path):
    _route("/", return_value=httpx.Response(200, html=HOME))
    _route("/pricing", return_value=httpx.Response(200, html=HOME))           # soft-404 (same as home)
    _route("/security", return_value=httpx.Response(404))
    _route("/trust", return_value=httpx.Response(403))
    _route("/customers", side_effect=httpx.ReadTimeout("slow"))
    _route("/about", return_value=httpx.Response(200, html="<html><body>tiny</body></html>"))
    _route("/careers", return_value=httpx.Response(200, json={"a": 1}))
    t = Trace("acme.com", out_dir=tmp_path)
    pages = scrape.scrape("acme.com", t, http=httpx.Client())
    got = {p.path: p.outcome for p in pages}
    assert got == {"/": "OK", "/pricing": "NOT_FOUND", "/security": "NOT_FOUND", "/trust": "BLOCKED",
                   "/customers": "TIMEOUT", "/about": "EMPTY_SHELL", "/careers": "NON_HTML"}
    assert "SOC 2 badge [soc2.png]" in pages[0].alts and "https://trust.acme.com" in pages[0].hrefs
    assert any(e["quote"] == "GET /trust -> BLOCKED" for e in t.data["evidence"])


@respx.mock
def test_blocked_is_not_cached_but_ok_is():
    route = _route("/", side_effect=[httpx.Response(403), httpx.Response(200, html=HOME), httpx.Response(500)])
    c = httpx.Client()
    assert scrape.fetch("acme.com", "/", c).outcome == "BLOCKED"
    assert scrape.fetch("acme.com", "/", c).outcome == "OK"
    assert scrape.fetch("acme.com", "/", c).outcome == "OK"   # served from cache
    assert route.call_count == 2


def test_extract_verifies_quotes(settings, tmp_path):
    page = scrape.parse("https://acme.com/", "/", 200, HOME)
    prof = CompanyProfile(name="Acme", one_liner="AI for banks", product_type="ai_software", headcount=None, facts=[
        Fact(topic="product", claim="AI platform", quote="Acme builds an AI platform for banks.", url="https://acme.com/"),
        Fact(topic="security", claim="SOC 2", quote="SOC 2 badge", url="https://acme.com/"),
        Fact(topic="funding", claim="Series B", quote="raised a $40M Series B", url="https://acme.com/"),
    ])
    t = Trace("acme.com", out_dir=tmp_path)
    _, facts = extract("acme.com", [page], LLM(settings, client=ScriptedClient(parsed(prof)), backoff=()), t)
    assert [f["verified"] for f in facts] == [True, True, False]   # invented quote is flagged
    assert t.data["steps"]["extract"]["facts"][2]["id"] == "E3"
