"""Step 7: Resend. The recipient is ALWAYS settings.to_email; there is no recipient parameter."""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from config import Settings

RESEND_EMAILS = "https://api.resend.com/emails"


def footer(contact: dict) -> str:
    name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
    return (f"\n\n---\nIntended recipient: {name}, {contact.get('position', '')} | {contact.get('email', '')} | "
            f"{contact.get('linkedin', '') or 'no LinkedIn'} (source: {contact.get('source', '')}). "
            "Sent to you, not to them.")


def send_email(subject: str, text: str, s: Settings, http: httpx.Client | None = None) -> dict:
    payload = {"from": s.from_email, "to": [s.to_email], "subject": subject, "text": text}
    r = (http or httpx).post(RESEND_EMAILS, json=payload, timeout=20,
                             headers={"Authorization": f"Bearer {s.resend_api_key}"})
    try:
        body = r.json()
    except ValueError:
        body = {}
    stamp = datetime.now(timezone.utc).isoformat()
    if r.is_success and body.get("id"):
        return {"id": body["id"], "to": s.to_email, "sent_at": stamp, "error": None}
    return {"id": None, "to": s.to_email, "sent_at": stamp,
            "error": f"HTTP {r.status_code} {body.get('name', '')}: {body.get('message', '')}"[:200]}
