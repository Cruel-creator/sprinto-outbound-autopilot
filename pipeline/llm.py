"""The only module that imports google.genai: pacing, retry, cache, structured + grounded calls."""
from __future__ import annotations

import time

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from config import Settings
from pipeline import cache

RETRYABLE = {408, 429, 500, 502, 503, 504}


class LLM:
    def __init__(self, s: Settings, client=None, backoff=(5, 20, 60)):
        self.s = s
        self.client = client or genai.Client(api_key=s.gemini_api_key, http_options=types.HttpOptions(timeout=60_000))
        self.backoff = backoff
        self._last = 0.0

    def _call(self, model: str, contents: str, config):
        for i, wait in enumerate((*self.backoff, None)):
            gap = self.s.min_interval - (time.monotonic() - self._last)
            if gap > 0:
                time.sleep(gap)
            self._last = time.monotonic()
            try:
                return self.client.models.generate_content(model=model, contents=contents, config=config)
            except errors.APIError as e:
                if e.code not in RETRYABLE or wait is None:
                    raise
                time.sleep(wait)

    def json(self, schema: type[BaseModel], prompt: str, model: str | None = None, trace=None, purpose: str = ""):
        model = model or self.s.model_fast
        k = cache.key("json", model, schema.model_json_schema(), prompt)
        hit = cache.get("llm", k)
        if hit is not None:
            return schema.model_validate(hit)
        config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema,
                                             max_output_tokens=8000)
        for attempt in range(2):  # validate-and-retry once
            r = self._call(model, prompt, config)
            try:
                out = r.parsed if isinstance(r.parsed, schema) else schema.model_validate_json(r.text or "")
                break
            except ValidationError:
                if attempt:
                    raise
        if trace:
            trace.log_llm(purpose, model, getattr(r, "model_version", None))
        cache.put("llm", k, out.model_dump())
        return out

    def grounded(self, prompt: str, trace=None, purpose: str = "web_research") -> dict:
        """Google Search grounding, schema-free. Returns {text, sources[{uri,title,domain}], queries}."""
        model = self.s.model_grounding
        k = cache.key("grounded", model, prompt)
        hit = cache.get("llm", k)
        if hit is not None:
            return hit
        r = self._call(model, prompt, types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())], max_output_tokens=4000))
        gm = r.candidates[0].grounding_metadata if r.candidates else None
        chunks = (gm.grounding_chunks or []) if gm else []
        out = {
            "text": r.text or "",
            "sources": [{"uri": c.web.uri, "title": c.web.title or "", "domain": getattr(c.web, "domain", "") or ""}
                        for c in chunks if getattr(c, "web", None)],
            "queries": list((gm.web_search_queries or []) if gm else []),
        }
        if trace:
            trace.log_llm(purpose, model, getattr(r, "model_version", None))
        cache.put("llm", k, out)
        return out
