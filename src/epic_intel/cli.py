"""Command-line interface for local evaluation and autonomous research."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path

from epic_intel import __version__
from epic_intel.evaluation import BenchmarkRunner
from epic_intel.research import ResearchLoop
from epic_intel.research.ledger import ExperimentLedger

DEFAULT_AGENT_COMMAND = (
    'codex exec --sandbox workspace-write --skip-git-repo-check -C "{worktree}" -'
)


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        if (directory / "pyproject.toml").exists() and (directory / "benchmarks").is_dir():
            return directory
    raise RuntimeError("could not find the EpicIntel Harness project root")


def _timestamp() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")


def command_init(args: argparse.Namespace) -> int:
    root = find_project_root(args.root)
    state = root / ".epic-intel"
    state.mkdir(parents=True, exist_ok=True)
    candidate = root / "candidate"
    required = [candidate / "agent.py", candidate / "graph.yaml"]
    missing = [str(path.relative_to(root)) for path in required if not path.exists()]
    if missing:
        print("candidate is incomplete: " + ", ".join(missing), file=sys.stderr)
        return 2
    print(f"initialized {state}")
    print("editable plane: candidate/**")
    print("truth plane: benchmarks/**, contracts/**, evaluation/**, policy/**")
    print("publication: disabled; human approval required")
    return 0


def command_benchmark(args: argparse.Namespace) -> int:
    root = find_project_root(args.root)
    artifacts = (
        args.artifacts.resolve()
        if args.artifacts
        else root / "artifacts" / f"{args.suite}-{_timestamp()}"
    )
    result = BenchmarkRunner(
        root,
        suite=args.suite,
        candidate_dir=args.candidate,
        artifact_dir=artifacts,
    ).run()
    print(f"suite:             {result.suite}")
    print(f"task runs:         {len(result.task_results)}")
    print(f"hard gates:        {'PASS' if result.hard_gates_passed else 'FAIL'}")
    print(f"quality score:     {result.quality_score:.6f}")
    print(f"truth plane:       {'unchanged' if result.truth_plane_unchanged else 'CHANGED'}")
    print(f"candidate:         {result.candidate_hash[:12]}")
    print(f"artifacts:         {artifacts}")
    failed = [item.task_id for item in result.task_results if not item.hard_gates_passed]
    if failed:
        print("failed task runs:  " + ", ".join(failed))
    if args.json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, default=str))
    return 0 if result.hard_gates_passed else 2


def command_results(args: argparse.Namespace) -> int:
    root = find_project_root(args.root)
    records = ExperimentLedger(root / ".epic-intel" / "results.jsonl").read()
    if args.limit:
        records = records[-args.limit :]
    if args.json:
        print(json.dumps(records, indent=2, ensure_ascii=False, default=str))
        return 0
    if not records:
        print("No research experiments have been recorded yet.")
        return 0
    print("experiment\tstatus\tdelta\tquality\treason")
    for record in records:
        print(
            "\t".join(
                [
                    str(record.get("experiment_id", "-")),
                    str(record.get("status", "-")),
                    f"{float(record.get('quality_delta', 0.0)):.6f}",
                    f"{float(record.get('quality_score', 0.0)):.6f}",
                    str(record.get("reason", ""))[:100].replace("\t", " "),
                ]
            )
        )
    return 0


def command_research(args: argparse.Namespace) -> int:
    root = find_project_root(args.root)
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,39}", args.tag):
        print("tag must contain only lowercase letters, digits, '.', '_' or '-'", file=sys.stderr)
        return 2
    program = args.program if args.program.is_absolute() else root / args.program
    loop = ResearchLoop(
        root,
        program_path=program,
        agent_command=args.agent_command,
        tag=args.tag,
        max_experiments=args.max_experiments,
        agent_timeout_seconds=args.agent_timeout_seconds,
    )
    print(f"research branch: research/{args.tag}")
    print("Each experiment runs in a disposable detached worktree.")
    print("Press Ctrl+C to stop after the current external process boundary.")
    try:
        loop.run()
    except KeyboardInterrupt:
        print("research interrupted")
        return 130
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="epic-intel",
        description="Build, benchmark, and improve auditable outbreak-intelligence agents.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--root", type=Path, help=argparse.SUPPRESS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="initialize local harness state")
    init_parser.set_defaults(handler=command_init)

    benchmark = subparsers.add_parser("benchmark", help="run an immutable benchmark suite")
    benchmark.add_argument("--suite", choices=("smoke", "event-intel-v1"), default="smoke")
    benchmark.add_argument(
        "--candidate",
        type=Path,
        help="candidate directory; defaults to ./candidate",
    )
    benchmark.add_argument("--artifacts", type=Path, help="artifact output directory")
    benchmark.add_argument("--json", action="store_true", help="also print the full JSON summary")
    benchmark.set_defaults(handler=command_benchmark)

    research = subparsers.add_parser("research", help="run disposable worktree experiments")
    research.add_argument("--program", type=Path, default=Path("program.md"))
    research.add_argument("--tag", default=dt.date.today().strftime("%Y%m%d"))
    research.add_argument("--agent-command", default=DEFAULT_AGENT_COMMAND)
    research.add_argument(
        "--max-experiments",
        type=int,
        default=0,
        help="0 means continue until interrupted",
    )
    research.add_argument("--agent-timeout-seconds", type=int, default=900)
    research.set_defaults(handler=command_research)

    results = subparsers.add_parser("results", help="show the append-only experiment ledger")
    results.add_argument("--limit", type=int, default=20)
    results.add_argument("--json", action="store_true")
    results.set_defaults(handler=command_results)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        code = int(args.handler(args))
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        code = 2
    raise SystemExit(code)


if __name__ == "__main__":
    main()
