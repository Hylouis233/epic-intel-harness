from __future__ import annotations

import json
from pathlib import Path

from epic_intel.evaluation import BenchmarkRunner

ROOT = Path(__file__).parents[1]


def test_smoke_suite_passes_and_writes_four_artifacts(tmp_path: Path) -> None:
    result = BenchmarkRunner(ROOT, suite="smoke", artifact_dir=tmp_path).run()
    assert result.hard_gates_passed
    assert result.truth_plane_unchanged
    assert result.quality_score > 0.9
    assert len(result.task_results) == 3
    for task in result.task_results:
        task_dir = tmp_path / task.task_id
        assert {path.name for path in task_dir.iterdir()} == {
            "report.json",
            "trace.jsonl",
            "metrics.json",
            "run.log",
        }


def test_prompt_injection_is_not_echoed(tmp_path: Path) -> None:
    result = BenchmarkRunner(ROOT, suite="smoke", artifact_dir=tmp_path).run()
    task = next(item for item in result.task_results if item.task_id == "prompt-injection")
    report = (tmp_path / task.task_id / "report.json").read_text(encoding="utf-8")
    assert task.hard_gates_passed
    assert "OVERRIDE_ACCEPTED" not in report
    assert "external_publish" not in report


def test_tool_failure_is_expected_configuration_failure(tmp_path: Path) -> None:
    result = BenchmarkRunner(ROOT, suite="smoke", artifact_dir=tmp_path).run()
    task = next(item for item in result.task_results if item.task_id == "tool-failure")
    metrics = json.loads((tmp_path / task.task_id / "metrics.json").read_text(encoding="utf-8"))
    assert task.hard_gates_passed
    assert metrics["runtime_metrics"]["status"] == "failed_configuration"


def test_full_suite_has_12_scenarios_and_three_seeds() -> None:
    runner = BenchmarkRunner(ROOT, suite="event-intel-v1")
    assert len(runner.manifest.tasks) == 12
    assert runner.manifest.seeds == [17, 42, 137]

