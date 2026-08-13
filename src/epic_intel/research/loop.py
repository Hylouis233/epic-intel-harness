"""Coding-agent-agnostic autonomous experimentation in disposable worktrees."""

from __future__ import annotations

import datetime as dt
import os
import shlex
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from epic_intel.evaluation import BenchmarkRunner

from .acceptance import compare_candidates
from .ledger import ExperimentLedger


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _changed_paths(root: Path, base_commit: str) -> list[str]:
    changed = set(
        line.strip()
        for line in _git(root, "diff", "--name-only", f"{base_commit}..HEAD").stdout.splitlines()
        if line.strip()
    )
    for args in (("diff", "--name-only"), ("diff", "--cached", "--name-only")):
        changed.update(
            line.strip() for line in _git(root, *args).stdout.splitlines() if line.strip()
        )
    changed.update(
        line.strip()
        for line in _git(root, "ls-files", "--others", "--exclude-standard").stdout.splitlines()
        if line.strip()
    )
    return sorted(changed)


class ResearchLoop:
    def __init__(
        self,
        project_root: Path,
        *,
        program_path: Path,
        agent_command: str,
        tag: str,
        max_experiments: int = 0,
        agent_timeout_seconds: int = 900,
    ) -> None:
        self.project_root = project_root.resolve()
        self.program_path = program_path.resolve()
        self.agent_command = agent_command
        self.tag = tag
        self.max_experiments = max_experiments
        self.agent_timeout_seconds = agent_timeout_seconds
        self.state_root = self.project_root / ".epic-intel"
        self.worktree_root = (self.state_root / "worktrees").resolve()
        self.run_root = self.state_root / "runs" / tag
        self.ledger = ExperimentLedger(self.state_root / "results.jsonl")
        self.branch = f"research/{tag}"

    def _ensure_repository(self) -> None:
        inside = _git(self.project_root, "rev-parse", "--is-inside-work-tree").stdout.strip()
        if inside != "true":
            raise RuntimeError("research requires a Git repository")
        if _git(self.project_root, "status", "--porcelain").stdout.strip():
            raise RuntimeError("research requires a clean working tree")
        exists = _git(
            self.project_root,
            "show-ref",
            "--verify",
            "--quiet",
            f"refs/heads/{self.branch}",
            check=False,
        ).returncode == 0
        if exists:
            raise RuntimeError(f"research branch already exists: {self.branch}")
        _git(self.project_root, "branch", self.branch, "HEAD")

    def _make_worktree(self, commit: str, experiment_id: str) -> Path:
        self.worktree_root.mkdir(parents=True, exist_ok=True)
        path = (self.worktree_root / experiment_id).resolve()
        if self.worktree_root not in path.parents:
            raise RuntimeError("resolved worktree escaped the harness state directory")
        _git(self.project_root, "worktree", "add", "--detach", str(path), commit)
        return path

    def _remove_worktree(self, path: Path) -> None:
        resolved = path.resolve()
        if self.worktree_root not in resolved.parents:
            raise RuntimeError("refusing to remove a worktree outside the harness state directory")
        _git(self.project_root, "worktree", "remove", "--force", str(resolved), check=False)
        if resolved.exists():
            shutil.rmtree(resolved)

    def _agent_prompt(self, baseline_score: float, iteration: int) -> str:
        program = self.program_path.read_text(encoding="utf-8")
        return (
            f"{program}\n\n"
            f"Experiment context:\n- iteration: {iteration}\n"
            f"- current full-suite quality: {baseline_score:.6f}\n"
            "- change only candidate/**\n"
            "- do not commit, edit Git configuration, or touch the truth plane\n"
            "Implement one focused improvement, then stop. The harness will benchmark it.\n"
        )

    def _run_agent(self, worktree: Path, prompt: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["EPIC_INTEL_CANDIDATE_ROOT"] = str(worktree / "candidate")
        command = self.agent_command.format(worktree=str(worktree), program=str(self.program_path))
        return subprocess.run(
            command if os.name == "nt" else shlex.split(command),
            cwd=worktree,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.agent_timeout_seconds,
            env=env,
            shell=os.name == "nt",
        )

    def run(self) -> None:
        self._ensure_repository()
        baseline_dir = self.run_root / "baseline"
        baseline = BenchmarkRunner(
            self.project_root,
            suite="event-intel-v1",
            artifact_dir=baseline_dir,
        ).run()
        if not baseline.hard_gates_passed:
            raise RuntimeError("baseline failed critical gates; repair it before research")
        current_commit = _git(self.project_root, "rev-parse", self.branch).stdout.strip()
        iteration = 0
        while self.max_experiments == 0 or iteration < self.max_experiments:
            iteration += 1
            experiment_id = f"{self.tag}-{iteration:04d}-{uuid.uuid4().hex[:6]}"
            worktree = self._make_worktree(current_commit, experiment_id)
            status = "crash"
            record: dict[str, Any] = {
                "experiment_id": experiment_id,
                "created_at": dt.datetime.now(dt.UTC).isoformat(),
                "base_commit": current_commit,
                "candidate_commit": None,
                "meta_agent_command": self.agent_command,
                "runtime_agent_model": "candidate-defined",
                "benchmark_version": "event-intel-v1",
                "status": status,
            }
            try:
                prompt = self._agent_prompt(baseline.quality_score, iteration)
                agent = self._run_agent(worktree, prompt)
                record["agent_returncode"] = agent.returncode
                record["agent_stdout_tail"] = agent.stdout[-2000:]
                record["agent_stderr_tail"] = agent.stderr[-2000:]
                head = _git(worktree, "rev-parse", "HEAD").stdout.strip()
                changed = _changed_paths(worktree, current_commit)
                record["changed_paths"] = changed
                if head != current_commit:
                    record["status"] = "discard"
                    record["reason"] = "coding agent changed Git history"
                    continue
                if not changed:
                    record["status"] = "discard"
                    record["reason"] = "coding agent produced no change"
                    continue
                outside = [path for path in changed if not path.startswith("candidate/")]
                if outside:
                    record["status"] = "discard"
                    record["reason"] = f"changed protected paths: {outside}"
                    continue
                if agent.returncode != 0:
                    record["status"] = "crash"
                    record["reason"] = "coding agent command failed"
                    continue

                smoke = BenchmarkRunner(
                    worktree,
                    suite="smoke",
                    artifact_dir=self.run_root / experiment_id / "smoke",
                ).run()
                record["smoke"] = {
                    "hard_gates_passed": smoke.hard_gates_passed,
                    "quality_score": smoke.quality_score,
                }
                if not smoke.hard_gates_passed:
                    record["status"] = "discard"
                    record["reason"] = "smoke suite failed critical gates"
                    continue

                candidate = BenchmarkRunner(
                    worktree,
                    suite="event-intel-v1",
                    artifact_dir=self.run_root / experiment_id / "full",
                ).run()
                acceptance = self._acceptance(baseline, candidate)
                record["hard_gates"] = candidate.hard_gates_passed
                record["quality_score"] = candidate.quality_score
                record["quality_delta"] = acceptance.mean_delta
                record["confidence_interval"] = acceptance.confidence_interval
                record["reason"] = acceptance.reason
                if not acceptance.accepted:
                    record["status"] = "discard"
                    continue

                _git(worktree, "add", "candidate")
                _git(worktree, "commit", "-m", f"research: keep {experiment_id}")
                candidate_commit = _git(worktree, "rev-parse", "HEAD").stdout.strip()
                _git(
                    self.project_root,
                    "update-ref",
                    f"refs/heads/{self.branch}",
                    candidate_commit,
                    current_commit,
                )
                current_commit = candidate_commit
                baseline = candidate
                record["candidate_commit"] = candidate_commit
                record["status"] = "keep"
            except subprocess.TimeoutExpired:
                record["status"] = "crash"
                record["reason"] = "coding agent exceeded its timeout"
            except Exception as exc:  # noqa: BLE001
                record["status"] = "crash"
                record["reason"] = f"{type(exc).__name__}: {exc}"
            finally:
                self.ledger.append(record)
                self._remove_worktree(worktree)

    @staticmethod
    def _acceptance(baseline: Any, candidate: Any):
        return compare_candidates(
            baseline,
            candidate,
            minimum_delta=0.005,
            bootstrap_samples=5000,
            confidence=0.95,
        )
