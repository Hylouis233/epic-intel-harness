"""Read-only deterministic tools exposed to candidate nodes."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from epic_intel.contracts import TaskInput

from .budget import RunBudget


class ToolUnavailable(RuntimeError):
    """Raised when a benchmark intentionally removes a required tool."""


def _canonical_location(location: str, aliases: dict[str, list[str]]) -> str:
    folded = " ".join(location.casefold().split())
    for canonical, variants in aliases.items():
        candidates = [canonical, *variants]
        if folded in {" ".join(item.casefold().split()) for item in candidates}:
            return canonical
    return location.strip()


@dataclass(slots=True)
class RuntimeServices:
    task: TaskInput
    budget: RunBudget
    candidate_hash: str
    seed: int
    trace: list[dict[str, Any]] = field(default_factory=list)

    def _record(self, tool: str, payload: dict[str, Any], result: Any) -> Any:
        self.budget.consume_tool_call(tool)
        if tool in self.task.unavailable_tools:
            self.trace.append({"kind": "tool_error", "tool": tool, "error": "unavailable"})
            raise ToolUnavailable(f"required tool is unavailable: {tool}")
        digest = hashlib.sha256(
            json.dumps(result, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        self.trace.append(
            {
                "kind": "tool_call",
                "tool": tool,
                "input": payload,
                "output_sha256": digest,
            }
        )
        return result

    def assess_readiness(self) -> dict[str, Any]:
        """Return deterministic readiness facts without an expected disposition."""

        latest_document = max(
            (document.published_at for document in self.task.official_documents),
            default=None,
        )
        document_age_days = (
            (self.task.data_as_of - latest_document).total_seconds() / 86_400
            if latest_document is not None
            else None
        )
        result = {
            "event_count": len(self.task.events),
            "official_document_count": len(self.task.official_documents),
            "minimum_official_documents": self.task.policy.minimum_official_documents,
            "latest_document_age_days": document_age_days,
            "maximum_age_days": self.task.policy.maximum_age_days,
            "quality_flags": sorted(self.task.quality_flags),
        }
        return self._record("assess_readiness", {}, result)

    def aggregate_events(self) -> dict[str, Any]:
        """Aggregate immutable event identifiers across location and date axes."""

        locations: dict[str, list[Any]] = defaultdict(list)
        dates: dict[str, list[Any]] = defaultdict(list)
        for event in self.task.events:
            canonical = _canonical_location(event.location, self.task.location_aliases)
            locations[canonical].append(event)
            dates[event.event_date.isoformat()].append(event)

        location_series = []
        for location in sorted(locations):
            events = sorted(locations[location], key=lambda item: (item.event_date, item.event_id))
            location_series.append(
                {
                    "location": location,
                    "event_count": len(events),
                    "first_event_date": events[0].event_date.isoformat(),
                    "latest_event_date": events[-1].event_date.isoformat(),
                    "source_event_ids": [event.event_id for event in events],
                }
            )

        timeline = []
        for event_date in sorted(dates):
            events = sorted(dates[event_date], key=lambda item: item.event_id)
            timeline.append(
                {
                    "event_date": event_date,
                    "event_count": len(events),
                    "location_count": len(
                        {
                            _canonical_location(event.location, self.task.location_aliases)
                            for event in events
                        }
                    ),
                    "source_event_ids": [event.event_id for event in events],
                }
            )
        result = {"location_series": location_series, "event_timeline": timeline}
        return self._record("aggregate_events", {}, result)

    def summarize_official_evidence(self) -> dict[str, Any]:
        """Expose evidence metadata, not raw answer keys or benchmark expectations."""

        documents = sorted(self.task.official_documents, key=lambda item: item.document_id)
        result = {
            "document_count": len(documents),
            "document_ids": [document.document_id for document in documents],
            "source_names": sorted({document.source_name for document in documents}),
            "languages": sorted({document.language for document in documents}),
        }
        return self._record("summarize_official_evidence", {}, result)

    def content_fingerprint(self) -> str:
        """Return a content hash for audit metadata."""

        payload = self.task.model_dump(mode="json")
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return self._record("content_fingerprint", {}, digest)

