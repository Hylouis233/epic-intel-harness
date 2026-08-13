"""Private process entrypoint for executing an untrusted candidate graph.

The parent sends only ``TaskInput``. Benchmark expectations and grader internals are not
serialized into this process. OS-level isolation remains an optional deployment concern;
this worker provides process and wall-clock isolation for the default local workflow.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import traceback
from pathlib import Path
from types import ModuleType
from typing import Any

from epic_intel.contracts import TaskInput

from .budget import BudgetExceeded, RunBudget
from .graph import load_and_compile_graph
from .runner import _failure_report
from .tools import RuntimeServices, ToolUnavailable


def _load_candidate_module(path: Path, candidate_hash: str) -> ModuleType:
    module_name = f"epic_intel_candidate_{candidate_hash[:12]}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load candidate module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def execute(args: argparse.Namespace) -> dict[str, Any]:
    task = TaskInput.model_validate_json(args.input.read_text(encoding="utf-8"))
    budget = RunBudget(
        wall_time_seconds=args.wall_time_seconds,
        max_tool_calls=args.max_tool_calls,
        max_output_characters=args.max_output_characters,
    )
    services = RuntimeServices(
        task=task,
        budget=budget,
        candidate_hash=args.candidate_hash,
        seed=args.seed,
    )
    state: dict[str, Any] = {"task": task.model_dump(mode="json"), "run_id": args.run_id}
    log_lines: list[str] = []
    report: dict[str, Any] | None = None
    status = "completed"
    error: str | None = None
    try:
        graph = load_and_compile_graph(args.candidate / "graph.yaml")
        module = _load_candidate_module(args.candidate / "agent.py", args.candidate_hash)
        handlers = getattr(module, "NODE_HANDLERS", None)
        if not isinstance(handlers, dict):
            raise RuntimeError("candidate.agent must define NODE_HANDLERS")
        for node in graph.nodes:
            budget.check_time()
            handler = handlers.get(node.handler)
            if not callable(handler):
                raise RuntimeError(f"missing callable handler: {node.handler}")
            services.trace.append({"kind": "node_start", "node": node.id})
            update = handler(state.copy(), services)
            if update is not None:
                if not isinstance(update, dict):
                    raise TypeError(f"node {node.id} returned a non-dict update")
                state.update(update)
            services.trace.append({"kind": "node_end", "node": node.id})
            log_lines.append(f"node={node.id} ok")
        report_value = state.get("report")
        if not isinstance(report_value, dict):
            raise RuntimeError("candidate graph completed without a report object")
        serialized = json.dumps(report_value, ensure_ascii=False, default=str)
        if len(serialized) > budget.max_output_characters:
            raise BudgetExceeded(
                f"output budget exceeded: {len(serialized)} > {budget.max_output_characters}"
            )
        report = report_value
    except ToolUnavailable as exc:
        status = "failed_configuration"
        error = str(exc)
        log_lines.append(f"failed_configuration={error}")
        report = _failure_report(
            task,
            run_id=args.run_id,
            candidate_hash=args.candidate_hash,
            seed=args.seed,
            tool_call_count=budget.tool_calls,
            status="failed_configuration",
            reason=error,
        )
    except Exception as exc:  # noqa: BLE001
        status = "crash"
        error = f"{type(exc).__name__}: {exc}"
        log_lines.extend(traceback.format_exc().rstrip().splitlines())
    return {
        "report": report,
        "state": state,
        "trace": services.trace,
        "status": status,
        "error": error,
        "elapsed_seconds": budget.elapsed_seconds,
        "tool_call_count": budget.tool_calls,
        "log_lines": log_lines,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--candidate-hash", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--wall-time-seconds", type=float, required=True)
    parser.add_argument("--max-tool-calls", type=int, required=True)
    parser.add_argument("--max-output-characters", type=int, required=True)
    args = parser.parse_args()
    payload = execute(args)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
