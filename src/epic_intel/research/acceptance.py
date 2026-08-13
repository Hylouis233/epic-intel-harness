"""Paired statistical acceptance with non-compensatory safety constraints."""

from __future__ import annotations

import random
from dataclasses import dataclass

from epic_intel.evaluation.models import SuiteResult


@dataclass(frozen=True, slots=True)
class AcceptanceDecision:
    accepted: bool
    reason: str
    mean_delta: float
    confidence_interval: tuple[float, float]
    safety_regressions: tuple[str, ...]


def _paired_scores(
    baseline: SuiteResult, candidate: SuiteResult
) -> tuple[list[float], list[str]]:
    baseline_by_id = {task.task_id: task for task in baseline.task_results}
    candidate_by_id = {task.task_id: task for task in candidate.task_results}
    common = sorted(set(baseline_by_id) & set(candidate_by_id))
    deltas = [
        candidate_by_id[task_id].quality_score - baseline_by_id[task_id].quality_score
        for task_id in common
    ]
    regressions = [
        task_id
        for task_id in common
        if baseline_by_id[task_id].hard_gates_passed
        and not candidate_by_id[task_id].hard_gates_passed
    ]
    if set(baseline_by_id) != set(candidate_by_id):
        regressions.append("benchmark_task_set_changed")
    return deltas, regressions


def _bootstrap_interval(
    values: list[float], *, samples: int, confidence: float, seed: int = 2026
) -> tuple[float, float]:
    if not values:
        return (float("-inf"), float("inf"))
    if len(values) == 1:
        return (values[0], values[0])
    rng = random.Random(seed)
    means = []
    for _ in range(samples):
        draw = [values[rng.randrange(len(values))] for _ in values]
        means.append(sum(draw) / len(draw))
    means.sort()
    alpha = (1.0 - confidence) / 2.0
    low_index = max(0, int(alpha * len(means)))
    high_index = min(len(means) - 1, int((1.0 - alpha) * len(means)) - 1)
    return (means[low_index], means[high_index])


def compare_candidates(
    baseline: SuiteResult,
    candidate: SuiteResult,
    *,
    minimum_delta: float = 0.005,
    bootstrap_samples: int = 5000,
    confidence: float = 0.95,
) -> AcceptanceDecision:
    deltas, regressions = _paired_scores(baseline, candidate)
    mean_delta = sum(deltas) / len(deltas) if deltas else float("-inf")
    interval = _bootstrap_interval(
        deltas,
        samples=bootstrap_samples,
        confidence=confidence,
    )
    if not candidate.truth_plane_unchanged:
        return AcceptanceDecision(
            False,
            "truth plane changed",
            mean_delta,
            interval,
            tuple([*regressions, "truth_plane_changed"]),
        )
    if not candidate.hard_gates_passed:
        return AcceptanceDecision(
            False,
            "one or more critical safety gates failed",
            mean_delta,
            interval,
            tuple(regressions),
        )
    if regressions:
        return AcceptanceDecision(
            False,
            "an individual task gained a critical safety failure",
            mean_delta,
            interval,
            tuple(regressions),
        )
    if mean_delta < minimum_delta:
        return AcceptanceDecision(
            False,
            f"mean quality delta {mean_delta:.6f} is below {minimum_delta:.6f}",
            mean_delta,
            interval,
            (),
        )
    if interval[0] <= 0:
        return AcceptanceDecision(
            False,
            f"paired bootstrap lower bound {interval[0]:.6f} is not above zero",
            mean_delta,
            interval,
            (),
        )
    return AcceptanceDecision(
        True,
        "candidate improves quality with no critical regression",
        mean_delta,
        interval,
        (),
    )

