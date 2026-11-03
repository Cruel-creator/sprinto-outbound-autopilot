"""Data contracts. LLM-facing schemas stay flat (lists of models, str/int/bool) for Gemini."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

FetchOutcome = Literal["OK", "NOT_FOUND", "BLOCKED", "TIMEOUT", "EMPTY_SHELL", "NON_HTML", "TOO_BIG"]
Status = Literal["sent", "not_qualified", "insufficient_data", "no_contact", "failed"]


class Page(BaseModel):
    url: str
    path: str
    outcome: FetchOutcome
    status_code: int = 0
    text: str = ""
    alts: list[str] = []
    hrefs: list[str] = []
    text_hash: str = ""


# ---------- LLM schemas ----------
class Fact(BaseModel):
    topic: str   # product|customers|pricing|security|funding|team|hiring|regions|stack|data|procurement|news
    claim: str
    quote: str   # copied verbatim from the page text
    url: str


class FactList(BaseModel):
    facts: list[Fact]


class CompanyProfile(BaseModel):
    name: str
    one_liner: str
    product_type: str        # saas|platform|api|devtool|ai_software|fintech_infra|healthtech_software|services|d2c|retail|other
    headcount: int | None = None
    facts: list[Fact]


class SignalCall(BaseModel):
    signal_id: str
    bucket: str              # one of the bucket names in icp.yaml, or "unknown"
    evidence_ids: list[str]


class GateCall(BaseModel):
    gate_id: str
    hit: bool
    evidence_ids: list[str]


class NextAction(BaseModel):
    tool: Literal["fetch_page", "web_research", "job_postings", "stop"]
    arg: str = ""
    target_signals: list[str] = []
    rationale: str = ""


class Assessment(BaseModel):
    signals: list[SignalCall]
    gates: list[GateCall]
    next_action: NextAction


class PainPoint(BaseModel):
    text: str
    evidence_ids: list[str]


class Pains(BaseModel):
    pains: list[PainPoint]


class Draft(BaseModel):
    hook_id: str
    subject: str
    body: str                # no greeting, no sign-off (Python adds those)


# ---------- non-LLM ----------
class Candidate(BaseModel):
    first_name: str
    last_name: str = ""
    position: str = ""
    seniority: str = ""
    email: str = ""
    linkedin: str = ""
    source: str = "hunter"   # hunter|csv
