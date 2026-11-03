import subprocess
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def test_secret_and_runtime_paths_are_ignored():
    for p in (".env", "cache/x", "out/x", "contacts.csv"):
        assert _git("check-ignore", "-q", p).returncode == 0, p  # -q takes one path per call


def test_template_is_not_ignored():
    assert _git("check-ignore", "-q", ".env.example").returncode == 1


def test_no_secret_file_is_tracked_or_ever_committed():
    tracked = _git("ls-files").stdout.split()
    assert ".env" not in tracked and "contacts.csv" not in tracked
    history = _git("log", "--all", "--name-only", "--format=").stdout.split()
    assert ".env" not in history and "contacts.csv" not in history


def test_env_example_lists_keys_with_placeholders_only():
    vals = dotenv_values(ROOT / ".env.example")
    for k in ("GEMINI_API_KEY", "RESEND_API_KEY", "HUNTER_API_KEY", "TO_EMAIL",
              "GEMINI_MODEL_FAST", "GEMINI_MODEL_STRONG", "GEMINI_MODEL_GROUNDING"):
        assert k in vals, k
    for k in ("GEMINI_API_KEY", "RESEND_API_KEY", "HUNTER_API_KEY"):
        assert vals[k].startswith("your_"), k
