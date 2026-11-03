"""Step 1: fetch homepage + key paths with typed outcomes; keep footer text, img alts, link hrefs."""
from __future__ import annotations

import hashlib
from pathlib import PurePosixPath
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from pipeline import cache
from pipeline.models import Page

PATHS = ["/", "/pricing", "/security", "/trust", "/customers", "/about", "/careers"]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
MAX_BYTES = 2_000_000
MIN_TEXT = 200
TRANSIENT = {"BLOCKED", "TIMEOUT"}  # never cached, so a re-run can succeed


def parse(url: str, path: str, status: int, html: str) -> Page:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        if tag.name == "script" and tag.get("src"):
            continue
        tag.decompose()
    text = " ".join(soup.get_text(" ", strip=True).split())
    alts = [f"{img.get('alt', '')} [{PurePosixPath(urlparse(img.get('src', '')).path).name}]".strip()
            for img in soup.find_all("img")][:80]
    hrefs = [t.get("href") or t.get("src") for t in soup.find_all(["a", "iframe", "script"])
             if t.get("href") or t.get("src")][:300]
    if "just a moment" in text.lower()[:300] or "cf-chl" in html[:5000]:
        outcome = "BLOCKED"
    elif len(text) < MIN_TEXT:
        outcome = "EMPTY_SHELL"
    else:
        outcome = "OK"
    return Page(url=url, path=path, outcome=outcome, status_code=status, text=text, alts=alts, hrefs=hrefs,
                text_hash=hashlib.sha256(text.encode()).hexdigest())


def fetch(domain: str, path: str, client: httpx.Client) -> Page:
    url = f"https://{domain}{path}"
    k = cache.key("page", url)
    hit = cache.get("pages", k)
    if hit is not None:
        return Page.model_validate(hit)
    try:
        r = client.get(url)
    except httpx.TimeoutException:
        return Page(url=url, path=path, outcome="TIMEOUT")
    except httpx.HTTPError:
        return Page(url=url, path=path, outcome="BLOCKED")
    if r.status_code == 404:
        page = Page(url=url, path=path, outcome="NOT_FOUND", status_code=404)
    elif r.status_code >= 400:
        page = Page(url=url, path=path, outcome="BLOCKED", status_code=r.status_code)
    elif "html" not in r.headers.get("content-type", "html"):
        page = Page(url=url, path=path, outcome="NON_HTML", status_code=r.status_code)
    elif len(r.content) > MAX_BYTES:
        page = Page(url=url, path=path, outcome="TOO_BIG", status_code=r.status_code)
    else:
        page = parse(str(r.url), path, r.status_code, r.text)
    if page.outcome not in TRANSIENT:
        cache.put("pages", k, page.model_dump())
    return page


def client() -> httpx.Client:
    return httpx.Client(follow_redirects=True, timeout=10, headers={"User-Agent": UA})


def scrape(domain: str, trace, http: httpx.Client | None = None) -> list[Page]:
    http = http or client()
    pages = [fetch(domain, p, http) for p in PATHS]
    home = pages[0]
    for p in pages[1:]:  # soft-404: a path that just re-serves the homepage
        if p.outcome == "OK" and home.outcome == "OK" and p.text_hash == home.text_hash:
            p.outcome = "NOT_FOUND"
    for p in pages:  # fetch outcomes are evidence too, so "no /security page" can be cited
        trace.add_evidence(p.url, f"GET {p.path} -> {p.outcome}", True, "scrape")
    trace.step("scrape", [{"path": p.path, "outcome": p.outcome, "status": p.status_code, "chars": len(p.text)}
                          for p in pages])
    return pages


def site_text(pages: list[Page], per_page: int = 12000) -> str:
    """Untrusted page content for prompts, fenced in <page> tags."""
    blocks = []
    for p in pages:
        if p.outcome != "OK":
            continue
        links = [h for h in p.hrefs if h.startswith("http") or "trust" in h or "security" in h][:60]
        blocks.append(f'<page url="{p.url}">\n{p.text[:per_page]}\nIMAGES: {"; ".join(p.alts[:40])}\n'
                      f'LINKS: {" ".join(links)}\n</page>')
    return "\n".join(blocks)
