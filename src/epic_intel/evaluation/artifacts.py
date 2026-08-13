"""Emit the four per-task artifacts and a compact suite summary."""

from __future__ import annotations

import json
from pathlib import Path

from epic_intel.runtime import RunResult

from .models import SuiteResult, TaskEvaluation


def _write_json(path: Path, value: object) -> None:
    serialized = json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n"
    path.write_text(serialized, encoding="utf-8")


def write_task_artifacts(
    root: Path,
    run: RunResult,
    evaluation: TaskEvaluation,
) -> Path:
    task_dir = root / run.task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    _write_json(task_dir / "report.json", run.report)
    with (task_dir / "trace.jsonl").open("w", encoding="utf-8") as handle:
        for item in run.trace:
            handle.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
    _write_json(task_dir / "metrics.json", evaluation.as_dict())
    (task_dir / "run.log").write_text("\n".join(run.log_lines) + "\n", encoding="utf-8")
    evaluation.artifact_dir = str(task_dir)
    return task_dir


def write_suite_summary(root: Path, result: SuiteResult) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _write_json(root / "summary.json", result.as_dict())
    rows = ["task\thard_gates\tquality_score\tstatus"]
    for task in result.task_results:
        rows.append(
            "\t".join(
                [
                    task.task_id,
                    "pass" if task.hard_gates_passed else "fail",
                    f"{task.quality_score:.6f}",
                    str(task.runtime_metrics["status"]),
                ]
            )
        )
    (root / "summary.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
