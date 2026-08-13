"""Pydantic contracts for synthetic event-intelligence benchmarks.

The candidate receives :class:`TaskInput`, never :class:`BenchmarkExpected`.
Keeping those models separate prevents a candidate from reading the answer key.
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class EventRecord(ContractModel):
    event_id: str = Field(min_length=1)
    event_date: dt.date
    location: str = Field(min_length=1)
    disease: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    source_document_ids: list[str] = Field(min_length=1)


class OfficialDocument(ContractModel):
    document_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    published_at: dt.datetime
    language: str = "en"
    body: str = Field(min_length=1)


class TaskPolicy(ContractModel):
    minimum_official_documents: int = Field(default=1, ge=1)
    maximum_age_days: int = Field(default=30, ge=1)
    publication_enabled: bool = False
    requires_human_approval: bool = True
    database_write_enabled: bool = False
    notifications_enabled: bool = False
    external_publish_enabled: bool = False


class TaskInput(ContractModel):
    schema_version: Literal["task-input-v1"] = "task-input-v1"
    task_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    disease: str = Field(min_length=1)
    region: str = Field(min_length=1)
    period_start: dt.date
    period_end: dt.date
    data_as_of: dt.datetime
    events: list[EventRecord] = Field(default_factory=list)
    official_documents: list[OfficialDocument] = Field(default_factory=list)
    location_aliases: dict[str, list[str]] = Field(default_factory=dict)
    quality_flags: list[str] = Field(default_factory=list)
    unavailable_tools: list[str] = Field(default_factory=list)
    policy: TaskPolicy = Field(default_factory=TaskPolicy)

    @model_validator(mode="after")
    def validate_period(self) -> TaskInput:
        if self.period_start > self.period_end:
            raise ValueError("period_start must be on or before period_end")
        event_ids = [event.event_id for event in self.events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("event_id values must be unique")
        document_ids = [doc.document_id for doc in self.official_documents]
        if len(document_ids) != len(set(document_ids)):
            raise ValueError("document_id values must be unique")
        known_docs = set(document_ids)
        for event in self.events:
            unknown = set(event.source_document_ids) - known_docs
            if unknown:
                raise ValueError(f"event {event.event_id} references unknown documents: {unknown}")
        return self


class BenchmarkExpected(ContractModel):
    disposition: Literal["report", "abstain", "failed_configuration"]
    required_topics: list[str] = Field(default_factory=list)
    sensitive_strings: list[str] = Field(default_factory=list)
    prohibited_output_strings: list[str] = Field(default_factory=list)


class BenchmarkTask(ContractModel):
    benchmark_version: Literal["event-intel-v1"] = "event-intel-v1"
    synthetic: Literal[True] = True
    redistribution_license: Literal["CC0-1.0"] = "CC0-1.0"
    input: TaskInput
    expected: BenchmarkExpected


class ReportMetadata(ContractModel):
    report_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    disease: str = Field(min_length=1)
    region: str = Field(min_length=1)
    period_start: dt.date
    period_end: dt.date
    generated_at: dt.datetime
    status: Literal["ready_for_human_review", "abstained", "failed_configuration"]
    risk_status: Literal["unknown", "not_assessed"] = "unknown"
    generator_version: str = Field(min_length=1)


class DataWatermark(ContractModel):
    data_as_of: dt.datetime
    event_record_count: int = Field(ge=0)
    official_document_count: int = Field(ge=0)
    coverage_description: str = Field(min_length=1)


class LocationSeriesPoint(ContractModel):
    location: str = Field(min_length=1)
    event_count: int = Field(ge=1)
    first_event_date: dt.date
    latest_event_date: dt.date
    source_event_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_count(self) -> LocationSeriesPoint:
        if self.event_count != len(self.source_event_ids):
            raise ValueError("event_count must equal the number of source_event_ids")
        if self.first_event_date > self.latest_event_date:
            raise ValueError("first_event_date must not be after latest_event_date")
        return self


class TimelinePoint(ContractModel):
    event_date: dt.date
    event_count: int = Field(ge=1)
    location_count: int = Field(ge=1)
    source_event_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_count(self) -> TimelinePoint:
        if self.event_count != len(self.source_event_ids):
            raise ValueError("event_count must equal the number of source_event_ids")
        return self


class OfficialEvidenceSummary(ContractModel):
    document_count: int = Field(ge=0)
    document_ids: list[str] = Field(default_factory=list)
    source_names: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_count(self) -> OfficialEvidenceSummary:
        if self.document_count != len(self.document_ids):
            raise ValueError("document_count must equal the number of document_ids")
        return self


class EventRecommendation(ContractModel):
    action: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    supporting_event_ids: list[str] = Field(min_length=1)


class EventNarrative(ContractModel):
    headline: str = Field(min_length=1)
    overview: str = Field(min_length=1)
    timeline_analysis: str = Field(min_length=1)
    location_assessment: str = Field(min_length=1)
    evidence_assessment: str = Field(min_length=1)
    conclusion: str = Field(min_length=1)
    recommendations: list[EventRecommendation] = Field(default_factory=list)


class AuditSummary(ContractModel):
    run_id: str = Field(min_length=1)
    candidate_hash: str = Field(min_length=8)
    tool_call_count: int = Field(ge=0)
    seed: int


class EventIntelligenceReport(ContractModel):
    schema_version: Literal["event-intelligence-report-v1"] = "event-intelligence-report-v1"
    report_type: Literal["event_intelligence"] = "event_intelligence"
    metadata: ReportMetadata
    data_watermark: DataWatermark
    location_series: list[LocationSeriesPoint] = Field(default_factory=list)
    event_timeline: list[TimelinePoint] = Field(default_factory=list)
    official_evidence: OfficialEvidenceSummary
    narrative: EventNarrative
    limitations: list[str] = Field(default_factory=list)
    audit: AuditSummary

    @model_validator(mode="after")
    def validate_cross_axis_invariants(self) -> EventIntelligenceReport:
        status = self.metadata.status
        if status == "ready_for_human_review":
            location_ids = {
                event_id for point in self.location_series for event_id in point.source_event_ids
            }
            timeline_ids = {
                event_id for point in self.event_timeline for event_id in point.source_event_ids
            }
            if location_ids != timeline_ids:
                raise ValueError("location and timeline source_event_ids must match")
            if len(location_ids) != self.data_watermark.event_record_count:
                raise ValueError("event axes must match data_watermark.event_record_count")
            cited = {
                event_id
                for recommendation in self.narrative.recommendations
                for event_id in recommendation.supporting_event_ids
            }
            if not cited.issubset(location_ids):
                raise ValueError("recommendations reference unknown source_event_ids")
        elif self.location_series or self.event_timeline:
            raise ValueError("non-report dispositions must not expose event aggregates")
        if self.official_evidence.document_count != self.data_watermark.official_document_count:
            raise ValueError("official evidence count must match data watermark")
        return self
