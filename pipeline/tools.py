"""Agent-loop tools. Only these (plus scrape/extract) write evidence."""
from __future__ import annotations

import re

import httpx
from google.genai import errors

from pipeline import scrape
from pipeline.extract import extract_page

ALLOWED_PATHS = ["/security", "/trust", "/trust-center", "/compliance", "/privacy", "/legal", "/dpa",
                 "/subprocessors", "/careers", "/jobs", "/about", "/company", "/customers", "/case-studies",
                 "/pricing", "/enterprise", "/blog"]
JOB_KEYWORDS = re.compile(r"\b(grc|compliance|security|ciso|infosec|soc ?2|iso ?27001|audit|risk)\b", re.I)


class Tools:
    def __init__(self, domain: str, name: str, pages: list, trace, llm, http: httpx.Client):
        self.domain, self.name, self.pages, self.trace, self.llm, self.http = domain, name, pages, trace, llm, http
        self.root = domain.split(".")[0].lower()

    def run(self, tool: str, arg: str) -> tuple[str, list[str]]:
        return {"fetch_page": self.fetch_page, "web_research": self.web_research,
                "job_postings": lambda _: self.job_postings()}[tool](arg)

    def fetch_page(self, path: str) -> tuple[str, list[str]]:
        path = "/" + path.strip().strip("/")
        if path not in ALLOWED_PATHS:
            return f"refused: {path} is not on the allow-list", []
        page = scrape.fetch(self.domain, path, self.http)
        self.pages.append(page)
        ids = [self.trace.add_evidence(page.url, f"GET {path} -> {page.outcome}", True, "fetch_page")]
        if page.outcome == "OK":
            ids += [f["id"] for f in extract_page(page, self.llm, self.trace, "fetch_page")]
        return f"{path}: {page.outcome}, {len(ids) - 1} facts", ids

    def web_research(self, query: str) -> tuple[str, list[str]]:
        try:
            out = self.llm.grounded(f"{query}\nCompany: {self.name} ({self.domain}). Answer in 2-4 factual "
                                    "sentences with dates. Say 'not found' if unsure.", trace=self.trace)
        except errors.APIError as e:
            return f"web_research unavailable ({e.code}); signals stay unknown", []
        blob = (out["text"] + " ".join(s["uri"] + s["title"] + s["domain"] for s in out["sources"])).lower()
        if not out["text"] or "not found" in out["text"].lower() or self.root not in blob:
            return "dropped: answer/sources do not mention the company", []
        url = out["sources"][0]["uri"] if out["sources"] else "google-search"
        eid = self.trace.add_evidence(url, out["text"][:400], False, "web_research")
        return f"search: {out['text'][:120]} | sources: {[s['title'] for s in out['sources']][:3]}", [eid]

    def job_postings(self) -> tuple[str, list[str]]:
        boards = [
            (f"https://boards-api.greenhouse.io/v1/boards/{self.root}/jobs", lambda d: [j["title"] for j in d["jobs"]]),
            (f"https://api.lever.co/v0/postings/{self.root}?mode=json", lambda d: [j["text"] for j in d]),
            (f"https://api.ashbyhq.com/posting-api/job-board/{self.root}", lambda d: [j["title"] for j in d["jobs"]]),
        ]
        for url, titles_of in boards:
            try:
                r = self.http.get(url)
                titles = titles_of(r.json()) if r.status_code == 200 else []
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                titles = []
            if titles:
                hits = [t for t in titles if JOB_KEYWORDS.search(t)][:5]
                ids = [self.trace.add_evidence(url, f"Open role: {t}", True, "job_postings") for t in hits]
                if not hits:
                    ids = [self.trace.add_evidence(url, f"{len(titles)} open roles, none in security/compliance",
                                                   True, "job_postings")]
                return f"ATS {url.split('/')[2]}: {len(titles)} roles, {len(hits)} security/compliance", ids
        summary, ids = self.fetch_page("/careers")
        return f"no public ATS board; {summary}", ids
