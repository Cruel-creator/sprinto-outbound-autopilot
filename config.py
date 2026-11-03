"""Settings loader: .env wins over stale OS env vars; pure function for tests."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
SECRET_KEYS = ("GEMINI_API_KEY", "RESEND_API_KEY", "HUNTER_API_KEY")
REQUIRED = SECRET_KEYS + ("TO_EMAIL", "GEMINI_MODEL_FAST", "GEMINI_MODEL_STRONG", "GEMINI_MODEL_GROUNDING")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    resend_api_key: str
    hunter_api_key: str
    to_email: str
    from_email: str
    model_fast: str
    model_strong: str
    model_grounding: str
    sender_name: str = ""
    min_interval: float = 6.5

    @property
    def models(self) -> list[str]:  # distinct, order-preserving
        return list(dict.fromkeys([self.model_fast, self.model_strong, self.model_grounding]))

    @property
    def secrets(self) -> list[str]:
        return [self.gemini_api_key, self.resend_api_key, self.hunter_api_key]


def load_settings(env_path: Path | None = None, environ: dict | None = None) -> Settings:
    env_path = env_path or ROOT / ".env"
    if not env_path.exists():
        raise ConfigError(f"{env_path.name} not found - copy .env.example to .env and fill it in")
    file_vals = {k: (v or "").strip() for k, v in dotenv_values(env_path, encoding="utf-8-sig").items()}
    base = dict(os.environ if environ is None else environ)
    merged = {**base, **{k: v for k, v in file_vals.items() if v}}  # non-empty .env value wins over OS env
    missing = [k for k in REQUIRED if not merged.get(k, "").strip() or merged[k].lower().startswith("your_")]
    if missing:
        raise ConfigError("missing or placeholder values in .env: " + ", ".join(missing))
    if not _EMAIL.match(merged["TO_EMAIL"].strip()):
        raise ConfigError("TO_EMAIL is not a valid email address")

    def g(k: str) -> str:
        return merged[k].strip()

    return Settings(
        g("GEMINI_API_KEY"), g("RESEND_API_KEY"), g("HUNTER_API_KEY"), g("TO_EMAIL"),
        merged.get("FROM_EMAIL", "").strip() or "Sprinto Autopilot <onboarding@resend.dev>",
        g("GEMINI_MODEL_FAST"), g("GEMINI_MODEL_STRONG"), g("GEMINI_MODEL_GROUNDING"),
        merged.get("SENDER_NAME", "").strip(),
        float(merged.get("GEMINI_MIN_INTERVAL", "6.5") or 6.5),
    )
