---
phase: "1"
slug: "setup-preflight"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-03"
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.2.0 + respx 0.23.1 (Python 3.12) |
| **Config file** | none. Wave 0 creates `pytest.ini` (`testpaths = tests`, `pythonpath = .`) |
| **Quick run command** | `.\.venv\Scripts\python.exe -m pytest -q` |
| **Full suite command** | `.\.venv\Scripts\python.exe -m pytest -q`, then the live gate `.\.venv\Scripts\python.exe preflight.py` |
| **Estimated runtime** | ~10 seconds (mocked suite) |

---

## Sampling Rate

- **After every task commit:** Run `.\.venv\Scripts\python.exe -m pytest -q`
- **After every plan wave:** Run the same, plus `tests/test_repo_hygiene.py`
- **Before `/gsd-verify-work`:** The full suite must be green, then a live `preflight.py` with send, then the human inbox check
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

Task IDs are bound by the planner. Rows are listed by requirement and criterion until the plans exist.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | 1 | SETUP-02 (SC2) | T-1-01 | `.env`, `cache/`, `out/` and `contacts.csv` are ignored; `.env.example` is not ignored; `.env` is never tracked | unit | `.\.venv\Scripts\python.exe -m pytest tests/test_repo_hygiene.py -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | SETUP-02 (SC2) | T-1-01 | `.gitignore` committed before any `.env` existed | git | `git log --diff-filter=A --format=%h -- .gitignore` returns a commit | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | SETUP-01 (SC1) | — | `.env.example` lists the 4 keys and 3 model IDs, with placeholders only | unit (static) | `.\.venv\Scripts\python.exe -m pytest tests/test_setup_files.py -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | SETUP-01 (SC1) | T-1-05 | The documented sequence installs and `pip check` is clean | integration | `.\.venv\Scripts\python.exe -m pip check` | n/a | ⬜ pending |
| TBD | TBD | 2 | SETUP-03 (SC4) | — | Structured pass per model, grounded pass for the grounding model, Hunter searches left shown | unit (mocked) | `.\.venv\Scripts\python.exe -m pytest tests/test_preflight.py -q -k "all_pass or non_grounding or deduped"` | ❌ W0 | ⬜ pending |
| TBD | TBD | 2 | SETUP-03 (SC5) | T-1-02 | A wrong key or unknown model prints one line `PREFLIGHT FAILED [service]: ...`, exits 1, no traceback, secrets scrubbed | unit (mocked) | `.\.venv\Scripts\python.exe -m pytest tests/test_preflight.py -q -k "bad_ or unknown_model or network_error or sandbox"` | ❌ W0 | ⬜ pending |
| TBD | TBD | 2 | SETUP-03 (cross-cut) | T-1-06 | `.env` beats a stale OS env var; BOM/CRLF handled; placeholders rejected | unit | `.\.venv\Scripts\python.exe -m pytest tests/test_preflight.py -q -k config` | ❌ W0 | ⬜ pending |
| TBD | TBD | 3 | SETUP-03 (SC3, SC4) | T-1-04 | Live: Hunter, then Gemini, then a Resend send to `TO_EMAIL` only | live | `.\.venv\Scripts\python.exe preflight.py` shows `[PASS]` lines and exit 0 | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `.gitignore` committed **before** any other Wave 0 file and before any `.env` exists (the ordering is itself a requirement)
- [ ] `requirements.txt` + `requirements-dev.txt` (pytest 9.2.0, respx 0.23.1). Framework install: `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`
- [ ] `pytest.ini`
- [ ] `tests/test_repo_hygiene.py`: stubs for SETUP-02
- [ ] `tests/test_setup_files.py`: stubs for SETUP-01
- [ ] `tests/test_preflight.py`: stubs for SETUP-03

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| The preflight email is visible in the user's Gmail inbox | SETUP-03 (SC3) | Inbox placement (Inbox vs Spam) can't be observed from code | Run `.\.venv\Scripts\python.exe preflight.py`. Open the Gmail for `TO_EMAIL`, find the subject "Sprinto Autopilot preflight <timestamp>", and check Inbox, then Spam. |
| Real `.env` with live keys created by the user | SETUP-01 | Agents must never write real secrets | Copy `.env.example` to `.env` and fill in the keys. Use the Resend account owner's address as `TO_EMAIL`. |
| One-off review of pinned `requirements*.txt` before the first install | SETUP-01 | The package-legitimacy seam flagged every package SUS on metadata alone | Confirm each pin matches its official PyPI project (google-genai, pydantic, httpx, beautifulsoup4, lxml, python-dotenv, tenacity, pytest, respx). |
| Live fake-key failure messages | SETUP-03 (SC5) | Needs throwaway keys against the real services | Run `preflight.py --env-file <fake.env>` and confirm one line `PREFLIGHT FAILED [service]: ...` and exit code 1. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
