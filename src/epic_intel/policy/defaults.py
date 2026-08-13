"""Policy is part of the truth plane and is never candidate-editable."""

CANDIDATE_ROOT = "candidate/"

PROTECTED_PATHS = (
    "benchmarks/",
    "src/epic_intel/contracts/",
    "src/epic_intel/evaluation/",
    "src/epic_intel/policy/",
    "tests/",
    "program.md",
)

ALLOWED_RUNTIME_TOOLS = frozenset(
    {
        "assess_readiness",
        "aggregate_events",
        "summarize_official_evidence",
        "content_fingerprint",
    }
)

FORBIDDEN_EVENT_CLAIMS = (
    "case count",
    "cases",
    "patient",
    "incidence",
    "fatality rate",
    "r_t",
    "rt =",
    "seir",
    "病例数",
    "发病率",
    "患者",
)

