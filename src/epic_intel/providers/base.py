"""Small provider protocol with auditable request and response metadata."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class ProviderError(RuntimeError):
    """A provider failed without permitting an unsafe fallback."""


class ProviderModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModelMessage(ProviderModel):
    role: str = Field(pattern=r"^(system|user|assistant|tool)$")
    content: str


class ModelRequest(ProviderModel):
    messages: list[ModelMessage] = Field(min_length=1)
    model: str = Field(min_length=1)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=1200, ge=1, le=32_000)
    seed: int | None = None
    response_format: dict[str, Any] | None = None


class ModelResponse(ProviderModel):
    content: str
    provider: str
    requested_model: str
    resolved_model: str
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    latency_ms: float = Field(default=0.0, ge=0.0)
    request_sha256: str = Field(min_length=64, max_length=64)
    response_sha256: str = Field(min_length=64, max_length=64)
    finish_reason: str | None = None
    raw_id: str | None = None


@runtime_checkable
class ModelProvider(Protocol):
    @property
    def name(self) -> str: ...

    def complete(self, request: ModelRequest) -> ModelResponse: ...

