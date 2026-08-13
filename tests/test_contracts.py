from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from epic_intel.contracts import BenchmarkTask, EventIntelligenceReport

ROOT = Path(__file__).parents[1]


def load_task(name: str) -> BenchmarkTask:
    path = ROOT / "benchmarks" / "event-intel-v1" / "tasks" / f"{name}.json"
    return BenchmarkTask.model_validate_json(path.read_text(encoding="utf-8"))


def test_bundled_tasks_are_synthetic_cc0_and_valid() -> None:
    paths = sorted((ROOT / "benchmarks" / "event-intel-v1" / "tasks").glob("*.json"))
    assert len(paths) == 12
    for path in paths:
        task = BenchmarkTask.model_validate_json(path.read_text(encoding="utf-8"))
        assert task.synthetic is True
        assert task.redistribution_license == "CC0-1.0"


def test_task_rejects_unknown_document_reference() -> None:
    payload = load_task("normal-complete").model_dump(mode="json")
    payload["input"]["events"][0]["source_document_ids"] = ["DOES-NOT-EXIST"]
    with pytest.raises(ValidationError, match="unknown documents"):
        BenchmarkTask.model_validate(payload)


def test_report_contract_rejects_cross_axis_mismatch() -> None:
    report = {
        "schema_version": "event-intelligence-report-v1",
        "report_type": "event_intelligence",
        "metadata": {
            "report_id": "EI-test",
            "title": "Synthetic test",
            "disease": "River fever",
            "region": "North Estuary",
            "period_start": "2026-06-01",
            "period_end": "2026-06-03",
            "generated_at": "2026-06-04T08:00:00Z",
            "status": "ready_for_human_review",
            "risk_status": "unknown",
            "generator_version": "test",
        },
        "data_watermark": {
            "data_as_of": "2026-06-04T08:00:00Z",
            "event_record_count": 1,
            "official_document_count": 1,
            "coverage_description": "synthetic",
        },
        "location_series": [
            {
                "location": "A",
                "event_count": 1,
                "first_event_date": "2026-06-01",
                "latest_event_date": "2026-06-01",
                "source_event_ids": ["EV-A"],
            }
        ],
        "event_timeline": [
            {
                "event_date": "2026-06-01",
                "event_count": 1,
                "location_count": 1,
                "source_event_ids": ["EV-B"],
            }
        ],
        "official_evidence": {
            "document_count": 1,
            "document_ids": ["DOC-A"],
            "source_names": ["Synthetic Office"],
        },
        "narrative": {
            "headline": "Synthetic",
            "overview": "Synthetic",
            "timeline_analysis": "Synthetic",
            "location_assessment": "Synthetic",
            "evidence_assessment": "Synthetic",
            "conclusion": "Synthetic",
            "recommendations": [],
        },
        "limitations": [],
        "audit": {
            "run_id": "run-test",
            "candidate_hash": "0" * 64,
            "tool_call_count": 1,
            "seed": 42,
        },
    }
    with pytest.raises(ValidationError, match="source_event_ids must match"):
        EventIntelligenceReport.model_validate(report)


def test_expected_answer_is_not_nested_under_task_input() -> None:
    task = load_task("normal-complete")
    serialized_input = json.dumps(task.input.model_dump(mode="json"), sort_keys=True)
    assert "expected" not in serialized_input
    assert "disposition" not in serialized_input
