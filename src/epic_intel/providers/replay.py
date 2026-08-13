"""Offline, content-addressed provider for repeatable evaluations."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .base import ModelProvider, ModelRequest, ModelResponse, ProviderError


def request_hash(request: ModelRequest) -> str:
    payload = request.model_dump(mode="json")
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class ReplayProvider(ModelProvider):
    def __init__(self, fixture_dir: Path) -> None:
        self.fixture_dir = fixture_dir.resolve()

    @property
    def name(self) -> str:
        return "replay"

    def complete(self, request: ModelRequest) -> ModelResponse:
        digest = request_hash(request)
        path = self.fixture_dir / f"{digest}.json"
        if not path.exists():
            raise ProviderError(f"replay fixture not found for request {digest}")
        response = ModelResponse.model_validate_json(path.read_text(encoding="utf-8"))
        if response.request_sha256 != digest:
            raise ProviderError("replay fixture request hash does not match its filename")
        return response

