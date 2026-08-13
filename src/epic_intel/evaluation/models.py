"""Serializable evaluation results."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class GateResult:
    gate_id: str
    passed: bool
    message: str
    severity: str = "critical"


@dataclass(slots=True)
class TaskEvaluation:
    task_id: str
    hard_gates_passed: bool
    gates: list[GateResult]
    quality_metrics: dict[str, float]
    quality_score: float
    runtime_metrics: dict[str, Any]
    artifact_dir: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SuiteResult:
    suite: str
    benchmark_version: str
    candidate_hash: str
    hard_gates_passed: bool
    quality_score: float
    task_results: list[TaskEvaluation]
    truth_plane_unchanged: bool
    started_at: str
    completed_at: str
    artifact_dir: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

