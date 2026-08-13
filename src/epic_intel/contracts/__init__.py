"""Versioned, immutable contracts shared by runtime and evaluators."""

from .models import (
    BenchmarkExpected,
    BenchmarkTask,
    EventIntelligenceReport,
    TaskInput,
)

__all__ = [
    "BenchmarkExpected",
    "BenchmarkTask",
    "EventIntelligenceReport",
    "TaskInput",
]

