"""Thin HTTP wrapper over an OpenAI-style endpoint: the Meta Model API (https://api.meta.ai/v1),
or llama.cpp's llama-server running Muse Glimmer on this PC.

Raw JSON is returned on purpose: the SAM 3.1 response schema is not published, so
perceive.py parses it defensively. Every call is cached by request body.
"""
import base64
import json
from typing import Any

import httpx

from .cache import ResponseCache
from .config import Settings


class MetaAPIError(RuntimeError):
    pass


def image_data_url(png_bytes: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")


class MetaClient:
    def __init__(self, settings: Settings, cache: ResponseCache, timeout: float | None = None):
        self.settings = settings
        self.cache = cache
        self._http = httpx.Client(
            base_url=settings.base_url,
            headers={"Authorization": f"Bearer {settings.api_key}"} if settings.api_key else {},
            timeout=timeout or settings.timeout_s,
        )

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        key = self.cache.key(path, json.dumps(body, sort_keys=True))
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        last_error: Exception | None = None
        for _ in range(2):
            try:
                response = self._http.post(path, json=body)
            except httpx.HTTPError as exc:
                last_error = exc
                continue
            if response.status_code == 429 or response.status_code >= 500:
                last_error = MetaAPIError(f"{response.status_code}: {response.text[:300]}")
                continue
            if response.status_code >= 400:
                raise MetaAPIError(f"{response.status_code}: {response.text[:300]}")
            data = response.json()
            self.cache.set(key, data)
            return data
        if self.settings.backend == "local" and isinstance(last_error, httpx.ConnectError):
            raise MetaAPIError(f"the local model server at {self.settings.base_url} is not running. Start it first.")
        raise MetaAPIError(f"request failed: {last_error}")

    def segment(self, png_bytes: bytes, phrase: str) -> dict[str, Any]:
        """Ask SAM 3.1 for masks of one concept (noun phrase) in the image."""
        body = {
            "model": self.settings.sam_model,
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": phrase},
                        {"type": "input_image", "image_url": image_data_url(png_bytes)},
                    ],
                }
            ],
        }
        return self._post("/responses", body)

    def chat(self, messages: list[dict[str, Any]], prefill: str = "", **params: Any) -> str:
        """Muse Spark or local Muse Glimmer via Chat Completions; returns the assistant text.

        `prefill` starts the answer (e.g. "{" for JSON). Locally it makes Muse Glimmer skip its
        hidden thinking, which otherwise takes most of the time on a consumer GPU.
        """
        local = self.settings.backend == "local"
        if local and prefill:
            messages = [*messages, {"role": "assistant", "content": prefill}]
        body = {"model": self.settings.muse_model, "messages": messages, **params}
        if local:
            body.setdefault("chat_template_kwargs", {"reasoning_strength": self.settings.local_reasoning})
            body.setdefault("max_tokens", 2048)
        data = self._post("/chat/completions", body)
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise MetaAPIError(f"Unexpected chat response shape: {str(data)[:300]}") from exc
        # The server may or may not echo the prefill; make sure the answer starts with it once.
        if local and prefill and not text.lstrip().startswith(prefill):
            text = prefill + text
        return text
