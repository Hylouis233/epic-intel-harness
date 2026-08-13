"""Run a versioned suite while keeping answer keys outside the candidate interface."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from epic_intel.contracts import BenchmarkTask
from epic_intel.runtime import CandidateRuntime

from .artifacts import write_suite_summary, write_task_artifacts
from .graders import evaluate_task
from .integrity import truth_plane_hash
from .models import GateResult, SuiteResult


class SuiteManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    benchmark_version: str
    description: str
    tasks: list[str] = Field(min_length=1)
    seeds: list[int] = Field(default_factory=lambda: [42], min_length=1)
    budgets: dict[str, float | int]
    acceptance: dict[str, float | int] = Field(default_factory=dict)


def load_manifest(project_root: Path, suite: str) -> SuiteManifest:
    path = project_root / "benchmarks" / suite / "manifest.yaml"
    if not path.exists():
        raise FileNotFoundError(f"unknown benchmark suite: {suite}")
    return SuiteManifest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def load_task(project_root: Path, relative_path: str) -> BenchmarkTask:
    path = project_root / "benchmarks" / relative_path
    return BenchmarkTask.model_validate_json(path.read_text(encoding="utf-8"))


class BenchmarkRunner:
    def __init__(
        self,
        project_root: Path,
        *,
        suite: str,
        candidate_dir: Path | None = None,
        artifact_dir: Path | None = None,
    ) -> None:
        self.project_root = project_root.resolve()
        self.suite = suite
        self.manifest = load_manifest(self.project_root, suite)
        self.candidate_dir = (candidate_dir or self.project_root / "candidate").resolve()
        self.artifact_dir = artifact_dir.resolve() if artifact_dir else None

    def run(self) -> SuiteResult:
        started = dt.datetime.now(dt.UTC)
        before_hash = truth_plane_hash(self.project_root)
        runtime = CandidateRuntime(
            self.candidate_dir,
            wall_time_seconds=float(self.manifest.budgets.get("wall_time_seconds", 10)),
            max_tool_calls=int(self.manifest.budgets.get("max_tool_calls", 24)),
            max_output_characters=int(
                self.manifest.budgets.get("max_output_characters", 24_000)
            ),
        )
        task_results = []
        candidate_hash = ""
        for relative_path in self.manifest.tasks:
            task = load_task(self.project_root, relative_path)
            for seed in self.manifest.seeds:
                run = runtime.run(task.input, seed=seed)
                candidate_hash = run.candidate_hash
                evaluation = evaluate_task(task, run)
                if len(self.manifest.seeds) > 1:
                    evaluation.task_id = f"{evaluation.task_id}@seed-{seed}"
                    run.task_id = evaluation.task_id
                if self.artifact_dir:
                    write_task_artifacts(self.artifact_dir, run, evaluation)
                task_results.append(evaluation)

        after_hash = truth_plane_hash(self.project_root)
        unchanged = before_hash == after_hash
        if not unchanged:
            for evaluation in task_results:
                evaluation.gates.append(
                    GateResult(
                        gate_id="truth_plane_integrity",
                        passed=False,
                        message="protected benchmark, contract, policy, or grader files changed",
                    )
                )
                evaluation.hard_gates_passed = False
                evaluation.quality_score = 0.0

        completed = dt.datetime.now(dt.UTC)
        hard_pass = unchanged and all(item.hard_gates_passed for item in task_results)
        quality = (
            sum(item.quality_score for item in task_results) / len(task_results)
            if task_results
            else 0.0
        )
        result = SuiteResult(
            suite=self.suite,
            benchmark_version=self.manifest.benchmark_version,
            candidate_hash=candidate_hash,
            hard_gates_passed=hard_pass,
            quality_score=round(quality, 6),
            task_results=task_results,
            truth_plane_unchanged=unchanged,
            started_at=started.isoformat(),
            completed_at=completed.isoformat(),
            artifact_dir=str(self.artifact_dir) if self.artifact_dir else None,
            metadata={"task_runs": len(task_results), "seeds": self.manifest.seeds},
        )
        if self.artifact_dir:
            write_suite_summary(self.artifact_dir, result)
        return result
