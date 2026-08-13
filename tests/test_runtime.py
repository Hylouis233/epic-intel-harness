from __future__ import annotations

import shutil
import time
from pathlib import Path

from epic_intel.contracts import BenchmarkTask
from epic_intel.runtime import CandidateRuntime

ROOT = Path(__file__).parents[1]


def task(name: str) -> BenchmarkTask:
    path = ROOT / "benchmarks" / "event-intel-v1" / "tasks" / f"{name}.json"
    return BenchmarkTask.model_validate_json(path.read_text(encoding="utf-8"))


def copy_candidate(tmp_path: Path) -> Path:
    target = tmp_path / "candidate"
    shutil.copytree(ROOT / "candidate", target)
    return target


def test_baseline_runs_in_child_process() -> None:
    run = CandidateRuntime(ROOT / "candidate", wall_time_seconds=5).run(
        task("normal-complete").input
    )
    assert run.status == "completed"
    assert run.report is not None
    assert run.report["metadata"]["status"] == "ready_for_human_review"
    assert run.tool_call_count == 3


def test_missing_required_tool_fails_closed() -> None:
    run = CandidateRuntime(ROOT / "candidate", wall_time_seconds=5).run(
        task("tool-failure").input
    )
    assert run.status == "failed_configuration"
    assert run.report is not None
    assert run.report["metadata"]["status"] == "failed_configuration"
    assert run.report["metadata"]["risk_status"] == "unknown"


def test_parent_enforces_wall_clock_timeout(tmp_path: Path) -> None:
    candidate = copy_candidate(tmp_path)
    (candidate / "agent.py").write_text(
        """def spin(state, services):
    while True:
        pass
NODE_HANDLERS = {"spin": spin}
""",
        encoding="utf-8",
    )
    (candidate / "graph.yaml").write_text(
        "version: 1\nnodes:\n  - {id: spin, handler: spin}\nedges: []\n",
        encoding="utf-8",
    )
    started = time.monotonic()
    run = CandidateRuntime(candidate, wall_time_seconds=0.2).run(task("normal-complete").input)
    elapsed = time.monotonic() - started
    assert run.status == "crash"
    assert "wall-clock budget exceeded" in (run.error or "")
    assert elapsed < 4


def test_output_budget_is_enforced(tmp_path: Path) -> None:
    candidate = copy_candidate(tmp_path)
    original = (candidate / "agent.py").read_text(encoding="utf-8")
    original = original.replace(
        'return {"report": report}',
        'report["narrative"]["overview"] = "X" * 10000\n    return {"report": report}',
    )
    (candidate / "agent.py").write_text(original, encoding="utf-8")
    run = CandidateRuntime(candidate, max_output_characters=1000).run(task("normal-complete").input)
    assert run.status == "crash"
    assert "output budget exceeded" in (run.error or "")

