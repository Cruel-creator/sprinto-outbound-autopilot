"""Build the public read-only demo in site/: the CRM UI plus a scrubbed snapshot of out/. No API calls, no secrets.

python build_demo.py   (then deploy site/ to Vercel; vercel.json points there)
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import app
from pipeline.report import rebuild
from pipeline.trace import OUT

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
DROP = {"email", "linkedin", "notes", "to", "gmail", "error"}          # never published
KEY_PREFIXES = ("re_", "AQ.", "AIza", "sk-")                              # what a leaked key looks like


def scrub(v):
    if isinstance(v, dict):
        return {k: (None if k in DROP else scrub(x)) for k, x in v.items()}
    if isinstance(v, list):
        return [scrub(x) for x in v]
    if isinstance(v, str):
        return EMAIL.sub("[hidden]", v)
    return v


def leak_check(text: str, where: str) -> None:
    if EMAIL.search(text):
        raise SystemExit(f"refusing to publish: an email address survived in {where}")
    if any(re.search(rf"(?<![\w-]){re.escape(p)}[A-Za-z0-9_-]{{16,}}", text) for p in KEY_PREFIXES):
        raise SystemExit(f"refusing to publish: something shaped like an API key is in {where}")


def main() -> int:
    rebuild(OUT, "hidden@example.invalid")            # fresh review.csv; the address never reaches site/
    if SITE.exists():
        shutil.rmtree(SITE)
    shutil.copytree(ROOT / "web", SITE)
    (SITE / "data" / "account").mkdir(parents=True)
    accounts = scrub(app.accounts())
    files = {SITE / "data" / "accounts.json": {"accounts": accounts, "stages": app.STAGES, "job": None}}
    for a in accounts:
        detail = app.account(a["domain"], "hidden@example.invalid")
        files[SITE / "data" / "account" / f"{a['domain']}.json"] = scrub({**detail, "gmail": None})
    for path, data in files.items():
        text = json.dumps(data, ensure_ascii=False)
        leak_check(text, path.name)
        path.write_text(text, encoding="utf-8")
    print(f"site/ built: {len(accounts)} accounts, emails and keys scrubbed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
