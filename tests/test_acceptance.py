from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from epic_intel.evaluation.models import SuiteResult, TaskEvaluation
from epic_intel.research import ResearchLoop, compare_candidates
from epic_intel.research.ledger import ExperimentLedger

ROOT = Path(__file__).parents[1]


def suite(scores: list[float], gates: list[bool] | None = None) -> SuiteResult:
    gates = gates or [True] * len(scores)
    tasks = [
        TaskEvaluation(
            task_id=f"task-{index}",
            hard_gates_passed=gates[index],
            gates=[],
            quality_metrics={},
            quality_score=score,
            runtime_metrics={},
        )
        for index, score in enumerate(scores)
    ]
    return SuiteResult(
        suite="test",
        benchmark_version="event-intel-v1",
        candidate_hash="a" * 64,
        hard_gates_passed=all(gates),
        quality_score=sum(scores) / len(scores),
        task_results=tasks,
        truth_plane_unchanged=True,
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:01Z",
    )


def test_accepts_consistent_practical_improvement() -> None:
    decision = compare_candidates(
        suite([0.80, 0.82, 0.81, 0.83]),
        suite([0.82, 0.84, 0.83, 0.85]),
        minimum_delta=0.005,
        bootstrap_samples=500,
    )
    assert decision.accepted
    assert decision.confidence_interval[0] > 0


def test_rejects_any_safety_regression() -> None:
    decision = compare_candidates(
        suite([0.80, 0.82]),
        suite([0.95, 0.95], gates=[True, False]),
        bootstrap_samples=100,
    )
    assert not decision.accepted
    assert "task-1" in decision.safety_regressions


def test_rejects_truth_plane_change() -> None:
    candidate = suite([0.90, 0.90])
    candidate.truth_plane_unchanged = False
    decision = compare_candidates(suite([0.80, 0.80]), candidate, bootstrap_samples=100)
    assert not decision.accepted
    assert "truth_plane_changed" in decision.safety_regressions


def test_research_loop_discards_no_change_and_removes_worktree(tmp_path: Path) -> None:
    repository = tmp_path / "harness"
    repository.mkdir()
    for name in ("candidate", "benchmarks"):
        shutil.copytree(ROOT / name, repository / name)
    shutil.copy2(ROOT / "program.md", repository / "program.md")
    (repository / ".gitignore").write_text(".epic-intel/\n", encoding="utf-8")
    noop = tmp_path / "noop_agent.py"
    noop.write_text("import sys\nsys.stdin.read()\n", encoding="utf-8")

    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(repository), *args], check=True, capture_output=True)

    git("init", "-b", "main")
    git("config", "user.email", "harness-test@example.invalid")
    git("config", "user.name", "Harness Test")
    git("add", ".")
    git("commit", "-m", "baseline")

    loop = ResearchLoop(
        repository,
        program_path=repository / "program.md",
        agent_command=f'"{sys.executable}" "{noop}"',
        tag="test-loop",
        max_experiments=1,
        agent_timeout_seconds=30,
    )
    loop.run()

    records = ExperimentLedger(repository / ".epic-intel" / "results.jsonl").read()
    assert len(records) == 1
    assert records[0]["status"] == "discard"
    assert records[0]["reason"] == "coding agent produced no change"
    worktrees = repository / ".epic-intel" / "worktrees"
    assert not list(worktrees.iterdir())
