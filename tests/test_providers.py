from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from epic_intel.providers import (
    ModelRequest,
    ModelResponse,
    OpenAICompatibleProvider,
    ProviderError,
    ReplayProvider,
)
from epic_intel.providers.base import ModelMessage
from epic_intel.providers.replay import request_hash


def request() -> ModelRequest:
    return ModelRequest(
        messages=[ModelMessage(role="user", content="Summarize the synthetic event.")],
        model="test-model",
        seed=42,
    )


def test_replay_provider_is_content_addressed(tmp_path: Path) -> None:
    model_request = request()
    digest = request_hash(model_request)
    content = "Synthetic replay response."
    fixture = ModelResponse(
        content=content,
        provider="replay",
        requested_model="test-model",
        resolved_model="test-model-v1",
        request_sha256=digest,
        response_sha256=hashlib.sha256(content.encode()).hexdigest(),
    )
    (tmp_path / f"{digest}.json").write_text(fixture.model_dump_json(), encoding="utf-8")
    assert ReplayProvider(tmp_path).complete(model_request) == fixture


def test_replay_provider_fails_on_missing_fixture(tmp_path: Path) -> None:
    with pytest.raises(ProviderError, match="not found"):
        ReplayProvider(tmp_path).complete(request())


def test_live_provider_requires_https_and_key() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        OpenAICompatibleProvider(base_url="http://localhost:8000/v1", api_key="x")
    with pytest.raises(ValueError, match="api_key"):
        OpenAICompatibleProvider(base_url="https://example.invalid/v1", api_key="")


def test_request_hash_is_stable() -> None:
    first = request_hash(request())
    second = request_hash(ModelRequest.model_validate_json(request().model_dump_json()))
    assert first == second
    assert len(first) == 64

