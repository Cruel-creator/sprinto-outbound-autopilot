from types import SimpleNamespace

import pytest

from config import Settings
from pipeline import cache


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "ROOT", tmp_path / "cache")
    monkeypatch.setattr(cache, "FORCE", False)


@pytest.fixture
def settings():
    return Settings("g-key", "re_key", "h-key", "me@example.com", "x <onboarding@resend.dev>",
                    "m-fast", "m-strong", "m-ground", sender_name="Asha", min_interval=0)


class ScriptedClient:
    """Fake genai client: pops queued responses (or exceptions) per call."""

    def __init__(self, *responses):
        self.queue = list(responses)
        self.calls = []
        self.models = self

    def generate_content(self, model, contents, config):
        self.calls.append((model, contents, config))
        r = self.queue.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def parsed(obj, model_version="m-v1"):
    return SimpleNamespace(parsed=obj, text=obj.model_dump_json(), model_version=model_version, candidates=[])
