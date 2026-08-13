"""Explicit opt-in adapter for OpenAI-compatible chat-completions endpoints.

This module uses the Python standard library so the deterministic core keeps a small
dependency surface. Network access is never enabled by a benchmark manifest.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request

from .base import ModelProvider, ModelRequest, ModelResponse, ProviderError
from .replay import request_hash


class OpenAICompatibleProvider(ModelProvider):
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 60.0,
        provider_name: str = "openai-compatible",
    ) -> None:
        normalized = base_url.rstrip("/")
        if not normalized.startswith("https://"):
            raise ValueError("base_url must use HTTPS")
        if not api_key:
            raise ValueError("api_key is required")
        self.base_url = normalized
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.provider_name = provider_name

    @property
    def name(self) -> str:
        return self.provider_name

    def complete(self, request: ModelRequest) -> ModelResponse:
        digest = request_hash(request)
        payload: dict[str, object] = {
            "model": request.model,
            "messages": [message.model_dump(mode="json") for message in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
        }
        if request.seed is not None:
            payload["seed"] = request.seed
        if request.response_format is not None:
            payload["response_format"] = request.response_format
        encoded = json.dumps(payload).encode("utf-8")
        http_request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=encoded,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "epic-intel-harness/0.1",
            },
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            raise ProviderError(f"provider request failed: {type(exc).__name__}") from exc
        latency_ms = (time.monotonic() - started) * 1000
        try:
            body = json.loads(raw)
            choice = body["choices"][0]
            content = choice["message"]["content"]
            usage = body.get("usage") or {}
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ProviderError("provider returned an invalid chat-completions response") from exc
        if not isinstance(content, str):
            raise ProviderError("provider response content is not text")
        response_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return ModelResponse(
            content=content,
            provider=self.provider_name,
            requested_model=request.model,
            resolved_model=str(body.get("model") or request.model),
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            latency_ms=latency_ms,
            request_sha256=digest,
            response_sha256=response_digest,
            finish_reason=choice.get("finish_reason"),
            raw_id=body.get("id"),
        )

