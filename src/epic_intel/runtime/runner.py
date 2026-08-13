"""Load and execute the candidate plane, then return auditable raw artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import site
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from epic_intel.contracts import TaskInput


@dataclass(slots=True)
class RunResult:
    task_id: str
    run_id: str
    report: dict[str, Any] | None
    state: dict[str, Any]
    trace: list[dict[str, Any]]
    status: str
    error: str | None
    elapsed_seconds: float
    tool_call_count: int
    candidate_hash: str
    log_lines: list[str]


def hash_candidate(candidate_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(candidate_dir.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            digest.update(path.relative_to(candidate_dir).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _worker_python() -> str:
    """Return the real interpreter instead of the Windows venv launcher.

    uv-created Windows virtual environments use a launcher process that spawns the base
    interpreter. Starting the base interpreter directly lets the parent enforce a hard
    timeout against the process that actually executes candidate code while preserving the
    active virtual environment through ``VIRTUAL_ENV`` and ``sys.prefix`` configuration.
    """

    if os.name != "nt" or sys.prefix == sys.base_prefix:
        return sys.executable
    config = Path(sys.prefix) / "pyvenv.cfg"
    if not config.exists():
        return sys.executable
    values: dict[str, str] = {}
    for line in config.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key.strip()] = value.strip()
    home = values.get("home")
    if not home:
        return sys.executable
    base_python = Path(home) / "python.exe"
    return str(base_python) if base_python.is_file() else sys.executable


def _worker_bootstrap() -> tuple[str, str]:
    """Return isolated bootstrap code and its explicit trusted import roots."""

    package_root = Path(__file__).resolve().parents[2]
    trusted = {str(package_root)}
    trusted.update(path for path in site.getsitepackages() if Path(path).is_dir())
    encoded_paths = json.dumps(sorted(trusted))
    code = (
        "import json,runpy,sys;"
        "sys.path[:0]=json.loads(sys.argv.pop(1));"
        "sys.argv[0]='epic_intel.runtime.worker';"
        "runpy.run_module('epic_intel.runtime.worker',run_name='__main__')"
    )
    return code, encoded_paths


def _failure_report(
    task: TaskInput,
    *,
    run_id: str,
    candidate_hash: str,
    seed: int,
    tool_call_count: int,
    status: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema_version": "event-intelligence-report-v1",
        "report_type": "event_intelligence",
        "metadata": {
            "report_id": f"EI-{run_id[:12]}",
            "title": task.title,
            "disease": task.disease,
            "region": task.region,
            "period_start": task.period_start.isoformat(),
            "period_end": task.period_end.isoformat(),
            "generated_at": task.data_as_of.isoformat(),
            "status": status,
            "risk_status": "unknown",
            "generator_version": "core-fail-closed-v1",
        },
        "data_watermark": {
            "data_as_of": task.data_as_of.isoformat(),
            "event_record_count": len(task.events),
            "official_document_count": len(task.official_documents),
            "coverage_description": "No report emitted; the harness failed closed.",
        },
        "location_series": [],
        "event_timeline": [],
        "official_evidence": {
            "document_count": len(task.official_documents),
            "document_ids": sorted(doc.document_id for doc in task.official_documents),
            "source_names": sorted({doc.source_name for doc in task.official_documents}),
        },
        "narrative": {
            "headline": "Report withheld",
            "overview": reason,
            "timeline_analysis": "No timeline assessment was emitted.",
            "location_assessment": "No location assessment was emitted.",
            "evidence_assessment": "Evidence requires review before another run.",
            "conclusion": "The system did not produce an intelligence conclusion.",
            "recommendations": [],
        },
        "limitations": [reason],
        "audit": {
            "run_id": run_id,
            "candidate_hash": candidate_hash,
            "tool_call_count": tool_call_count,
            "seed": seed,
        },
    }


class CandidateRuntime:
    def __init__(
        self,
        candidate_dir: Path,
        *,
        wall_time_seconds: float = 10.0,
        max_tool_calls: int = 24,
        max_output_characters: int = 24_000,
    ) -> None:
        self.candidate_dir = candidate_dir.resolve()
        self.wall_time_seconds = wall_time_seconds
        self.max_tool_calls = max_tool_calls
        self.max_output_characters = max_output_characters

    def run(self, task: TaskInput, *, seed: int = 42) -> RunResult:
        run_id = uuid.uuid4().hex
        candidate_hash = hash_candidate(self.candidate_dir)
        log_lines = [f"run_id={run_id}", f"task_id={task.task_id}"]
        with tempfile.TemporaryDirectory(prefix="epic-intel-run-") as temporary:
            temporary_path = Path(temporary)
            candidate_snapshot = temporary_path / "candidate"
            shutil.copytree(
                self.candidate_dir,
                candidate_snapshot,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )
            input_path = temporary_path / "task-input.json"
            output_path = temporary_path / "run-result.json"
            stdout_path = temporary_path / "worker-stdout.log"
            stderr_path = temporary_path / "worker-stderr.log"
            input_path.write_text(task.model_dump_json(indent=2), encoding="utf-8")
            bootstrap_code, trusted_paths = _worker_bootstrap()
            command = [
                _worker_python(),
                "-I",
                "-c",
                bootstrap_code,
                trusted_paths,
                "--candidate",
                str(candidate_snapshot),
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--run-id",
                run_id,
                "--candidate-hash",
                candidate_hash,
                "--seed",
                str(seed),
                "--wall-time-seconds",
                str(self.wall_time_seconds),
                "--max-tool-calls",
                str(self.max_tool_calls),
                "--max-output-characters",
                str(self.max_output_characters),
            ]
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = str(seed)
            env["PYTHONNOUSERSITE"] = "1"
            timed_out = False
            return_code = -1
            with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
                "w", encoding="utf-8"
            ) as stderr_handle:
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
                process = subprocess.Popen(
                    command,
                    cwd=temporary_path,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    env=env,
                    text=True,
                    creationflags=creationflags,
                )
                try:
                    # Allow a small interpreter-startup margin while keeping the parent
                    # deadline close to the configured wall-clock budget.
                    return_code = process.wait(timeout=self.wall_time_seconds + 1.0)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    if os.name == "nt":
                        terminated = subprocess.run(
                            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                            check=False,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        if terminated.returncode != 0:
                            process.kill()
                    else:
                        process.kill()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2)
                    # Windows can release redirected file handles just after the process tree exits.
                    time.sleep(0.05)

            def read_tail(path: Path, limit: int = 12_000) -> str:
                if not path.exists():
                    return ""
                with path.open("rb") as handle:
                    handle.seek(0, os.SEEK_END)
                    size = handle.tell()
                    handle.seek(max(0, size - limit))
                    return handle.read().decode("utf-8", errors="replace")

            stdout_tail = read_tail(stdout_path)
            stderr_tail = read_tail(stderr_path)
            if stdout_tail.strip():
                log_lines.append("worker_stdout_tail:")
                log_lines.extend(stdout_tail.rstrip().splitlines())
            if stderr_tail.strip():
                log_lines.append("worker_stderr_tail:")
                log_lines.extend(stderr_tail.rstrip().splitlines())

            if output_path.exists():
                payload = json.loads(output_path.read_text(encoding="utf-8"))
                return RunResult(
                    task_id=task.task_id,
                    run_id=run_id,
                    report=payload.get("report"),
                    state=payload.get("state", {}),
                    trace=payload.get("trace", []),
                    status=str(payload.get("status", "crash")),
                    error=payload.get("error"),
                    elapsed_seconds=float(payload.get("elapsed_seconds", 0.0)),
                    tool_call_count=int(payload.get("tool_call_count", 0)),
                    candidate_hash=candidate_hash,
                    log_lines=[*log_lines, *payload.get("log_lines", [])],
                )

            error = (
                f"wall-clock budget exceeded after {self.wall_time_seconds:.3f}s"
                if timed_out
                else f"candidate worker exited with code {return_code} without a result"
            )
            log_lines.append(error)
            return RunResult(
                task_id=task.task_id,
                run_id=run_id,
                report=None,
                state={},
                trace=[],
                status="crash",
                error=error,
                elapsed_seconds=self.wall_time_seconds if timed_out else 0.0,
                tool_call_count=0,
                candidate_hash=candidate_hash,
                log_lines=log_lines,
            )
