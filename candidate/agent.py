"""Editable baseline candidate for the EpicIntel research loop.

Only files under ``candidate/`` belong to the proposal plane. The benchmark
answer key, contracts, safety policy, and graders are intentionally elsewhere.
"""

from __future__ import annotations

from typing import Any

ABSTAIN_FLAGS = {
    "contains_patient_rows": "sensitive row-level data is present",
    "evidence_conflict": "official sources contain an unresolved conflict",
    "prompt_injection": "an untrusted source contains hostile instructions",
    "unknown_disease": "the disease label is not recognized",
}


def readiness(state: dict[str, Any], services: Any) -> dict[str, Any]:
    facts = services.assess_readiness()
    reasons: list[str] = []
    if facts["event_count"] == 0:
        reasons.append("the frozen snapshot contains no outbreak events")
    if facts["official_document_count"] < facts["minimum_official_documents"]:
        reasons.append("official evidence is below the configured minimum")
    age = facts["latest_document_age_days"]
    if age is None or age > facts["maximum_age_days"]:
        reasons.append("the newest official evidence is outside the freshness window")
    flagged = sorted(set(ABSTAIN_FLAGS).intersection(facts["quality_flags"]))
    if flagged:
        reasons.extend(ABSTAIN_FLAGS[flag] for flag in flagged)
    return {
        "readiness": facts,
        "disposition": "abstain" if reasons else "report",
        "abstention_reasons": reasons,
    }


def event_analysis(state: dict[str, Any], services: Any) -> dict[str, Any]:
    if state.get("disposition") != "report":
        return {"aggregates": {"location_series": [], "event_timeline": []}}
    return {"aggregates": services.aggregate_events()}


def evidence_retrieval(state: dict[str, Any], services: Any) -> dict[str, Any]:
    return {"evidence": services.summarize_official_evidence()}


def _report_narrative(task: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    aggregates = state["aggregates"]
    evidence = state["evidence"]
    locations = [point["location"] for point in aggregates["location_series"]]
    dates = [point["event_date"] for point in aggregates["event_timeline"]]
    event_ids = [event["event_id"] for event in task["events"]]
    language_note = ", ".join(evidence.get("languages", [])) or "unspecified"
    source_note = ", ".join(evidence["source_names"])
    recommendation_ids = event_ids[: min(3, len(event_ids))]
    return {
        "headline": f"{task['disease']} event intelligence — {task['region']}",
        "overview": (
            f"The frozen snapshot contains {len(event_ids)} outbreak event records for "
            f"{task['disease']} in {task['region']}, supported by "
            f"{evidence['document_count']} official documents."
        ),
        "timeline_analysis": (
            f"Recorded event dates span {dates[0]} through {dates[-1]}; "
            "counts describe records in the snapshot, not affected people."
        ),
        "location_assessment": (
            f"Canonicalized locations in scope are {', '.join(locations)}. "
            "Location aliases were resolved before aggregation."
        ),
        "evidence_assessment": (
            f"Evidence sources: {source_note}. Document languages: {language_note}. "
            "Every aggregate is traceable to immutable event identifiers."
        ),
        "conclusion": (
            "The available evidence supports continued source verification and monitoring; "
            "this report does not estimate clinical burden or forecast transmission."
        ),
        "recommendations": [
            {
                "action": f"Review the next official update for {task['region']}",
                "rationale": (
                    "Reconcile any new document against the frozen event identifiers and "
                    "record a new data watermark before changing the assessment."
                ),
                "supporting_event_ids": recommendation_ids,
            }
        ],
    }


def _abstention_narrative(task: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    reasons = state.get("abstention_reasons") or ["the evidence did not meet policy"]
    reason_text = "; ".join(reasons)
    return {
        "headline": f"Assessment withheld — {task['region']}",
        "overview": f"The harness abstained because {reason_text}.",
        "timeline_analysis": "No temporal assessment was emitted.",
        "location_assessment": "No geographic assessment was emitted.",
        "evidence_assessment": "The available evidence must be reviewed before another run.",
        "conclusion": "No operational conclusion is available from this snapshot.",
        "recommendations": [],
    }


def report_writer(state: dict[str, Any], services: Any) -> dict[str, Any]:
    task = state["task"]
    evidence = state["evidence"]
    disposition = state.get("disposition", "abstain")
    is_report = disposition == "report"
    aggregates = state["aggregates"]
    reasons = state.get("abstention_reasons", [])
    narrative = (
        _report_narrative(task, state) if is_report else _abstention_narrative(task, state)
    )
    report = {
        "schema_version": "event-intelligence-report-v1",
        "report_type": "event_intelligence",
        "metadata": {
            "report_id": f"EI-{state['run_id'][:12]}",
            "title": task["title"],
            "disease": task["disease"],
            "region": task["region"],
            "period_start": task["period_start"],
            "period_end": task["period_end"],
            "generated_at": task["data_as_of"],
            "status": "ready_for_human_review" if is_report else "abstained",
            "risk_status": "unknown",
            "generator_version": "baseline-deterministic-v1",
        },
        "data_watermark": {
            "data_as_of": task["data_as_of"],
            "event_record_count": len(task["events"]),
            "official_document_count": len(task["official_documents"]),
            "coverage_description": (
                f"Synthetic frozen snapshot for {task['region']}; "
                f"{len(task['events'])} event records and "
                f"{len(task['official_documents'])} official documents."
            ),
        },
        "location_series": aggregates["location_series"],
        "event_timeline": aggregates["event_timeline"],
        "official_evidence": {
            "document_count": evidence["document_count"],
            "document_ids": evidence["document_ids"],
            "source_names": evidence["source_names"],
        },
        "narrative": narrative,
        "limitations": reasons,
        "audit": {
            "run_id": state["run_id"],
            "candidate_hash": services.candidate_hash,
            "tool_call_count": services.budget.tool_calls,
            "seed": services.seed,
        },
    }
    return {"report": report}


NODE_HANDLERS = {
    "readiness": readiness,
    "event_analysis": event_analysis,
    "evidence_retrieval": evidence_retrieval,
    "report_writer": report_writer,
}
