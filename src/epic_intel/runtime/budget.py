"""Deterministic wall-clock and tool-call budgets."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


class BudgetExceeded(RuntimeError):
    """Raised before a candidate can exceed a configured resource budget."""


@dataclass(slots=True)
class RunBudget:
    wall_time_seconds: float = 10.0
    max_tool_calls: int = 24
    max_output_characters: int = 24_000
    started_at: float = field(default_factory=time.monotonic)
    tool_calls: int = 0

    def check_time(self) -> None:
        elapsed = time.monotonic() - self.started_at
        if elapsed > self.wall_time_seconds:
            raise BudgetExceeded(
                f"wall-clock budget exceeded: {elapsed:.3f}s > {self.wall_time_seconds:.3f}s"
            )

    def consume_tool_call(self, tool_name: str) -> None:
        self.check_time()
        self.tool_calls += 1
        if self.tool_calls > self.max_tool_calls:
            raise BudgetExceeded(
                f"tool-call budget exceeded while calling {tool_name}: "
                f"{self.tool_calls} > {self.max_tool_calls}"
            )

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.started_at

