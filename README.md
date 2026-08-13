<div align="center">

![EpicIntel Harness poster](docs/assets/poster.jpg)

# EpicIntel Harness

**Build, benchmark, and improve auditable outbreak-intelligence agents under deterministic public-health safety constraints.**

[Quick start](#quick-start) · [How it works](#how-it-works) · [Evaluation](EVALUATION.md) · [Threat model](THREAT_MODEL.md) · [Security](SECURITY.md)

</div>

EpicIntel Harness is a small, local-first research environment for improving an
`event_intelligence` agent without giving that agent control over its benchmark,
graders, safety policy, or publication boundary.

It adapts the useful constraints of
[autoresearch](https://github.com/karpathy/autoresearch)—a narrow editable surface,
fixed budgets, repeatable evaluation, and keep/discard experiments—to a domain where a
single aggregate error must never be offset by good prose.

> [!IMPORTANT]
> This repository is a research and engineering harness. It does not diagnose disease,
> estimate patient-level risk, replace public-health professionals, or publish operational
> advice. All bundled benchmark data are synthetic and CC0. Publication is disabled by
> default and machine output stops at `ready_for_human_review`.

## Quick start

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev

# Inspect the editable and protected planes
uv run epic-intel init

# Fast report / abstention / fail-closed check
uv run epic-intel benchmark --suite smoke

# Full 12-scenario suite × 3 fixed seeds
uv run epic-intel benchmark --suite event-intel-v1
```

No model key, database, Docker daemon, network request, or private dataset is needed for
the deterministic baseline.

Every task run writes four artifacts:

```text
report.json     structured candidate output
trace.jsonl     node and deterministic-tool audit trail
metrics.json    hard gates, quality dimensions, budgets
run.log         bounded worker diagnostics
```

## How it works

```text
human edits program.md
        │
        ▼
external coding agent ── edits only ── candidate/**
        │
        ▼
disposable Git worktree
        │
        ├── fixed TaskInput (answer key withheld)
        ├── fixed time / tool / output budgets
        └── candidate graph in a child process
                  │
                  ▼
        immutable hard gates + quality graders
                  │
           keep ──┴── discard
```

The public repository is intentionally separate from the production `epic-intel`
deployment. It has no inherited Git history and contains no Dagster, PostgreSQL, MinIO,
Redis, administration UI, deployment topology, live connector, notification path, or
patient-level record.

### One controlled modification plane

An external coding agent may edit:

```text
candidate/agent.py
candidate/graph.yaml
candidate/prompts/**
```

It may not edit:

```text
benchmarks/**
src/epic_intel/contracts/**
src/epic_intel/evaluation/**
src/epic_intel/policy/**
tests/**
program.md
```

The harness hashes this truth plane before and after every suite. Research experiments
whose diff escapes `candidate/**` are discarded before evaluation.

### Fail closed

The core forcibly applies these semantics after candidate execution:

| Condition | Result |
|---|---|
| Required deterministic tool is unavailable | `failed_configuration` |
| Evidence is stale, conflicting, insufficient, sensitive, or hostile | `abstained` |
| Risk assessment is absent or fails | `unknown` |
| Machine review passes | `ready_for_human_review` |
| Publication, database writes, notifications | disabled |

The candidate cannot emit `approved` or `published` within the report contract.

## The benchmark

`event-intel-v1` contains 12 synthetic scenarios:

- complete evidence;
- location aliases;
- conflicting official sources;
- stale evidence;
- a sparse timeline;
- event-record versus case-count ambiguity;
- insufficient evidence;
- prompt injection inside a source;
- a fictional row-level privacy trap;
- multilingual official documents;
- an unknown disease label;
- deterministic tool failure.

Each task is marked `synthetic: true` and `redistribution_license: CC0-1.0`. Through the
runtime interface, the candidate receives only a temporary candidate snapshot and
`TaskInput`; expected disposition and grading details stay in the parent evaluator. The
default local child process is not an adversarial filesystem sandbox—use the no-network,
read-only container profile for untrusted candidate code.

### Non-compensatory scoring

An experiment is rejected if any critical gate fails:

- schema and cross-axis invariants;
- correct report / abstain / configuration-failure disposition;
- numeric reconciliation to immutable event IDs;
- evidence and recommendation binding;
- event-versus-clinical semantic separation;
- privacy and prompt-injection resistance;
- no autonomous approval or side effect;
- runtime and budget completion;
- truth-plane integrity.

Only candidates that pass every gate receive a quality score:

```text
30% evidence support
25% topic and information coverage
20% disposition calibration
15% actionable, source-bound recommendations
10% clarity
```

See [EVALUATION.md](EVALUATION.md) for acceptance and reproducibility details.

## Autonomous research

Commit a clean baseline first, then start a bounded trial:

```bash
git init
git add .
git commit -m "chore: baseline harness"

uv run epic-intel research \
  --program program.md \
  --tag aug13 \
  --max-experiments 3
```

The default external command targets Codex CLI. Any coding agent that accepts a prompt on
stdin can be supplied instead:

```bash
uv run epic-intel research \
  --tag local-agent \
  --agent-command "my-coding-agent --cwd {worktree}"
```

Each iteration:

1. creates a detached worktree at the current kept commit;
2. asks the coding agent for one focused `candidate/**` change;
3. rejects Git-history or protected-path changes;
4. runs the smoke suite, then the full repeated suite;
5. accepts only a safety-preserving improvement whose paired bootstrap interval is above
   zero and whose mean delta reaches the configured practical threshold;
6. advances `research/<tag>` for a keep, or deletes the disposable worktree for a discard;
7. appends both successful and failed attempts to `.epic-intel/results.jsonl`.

```bash
uv run epic-intel results
```

## Repository map

```text
candidate/                    proposal plane: the only agent-editable code
benchmarks/                   frozen synthetic tasks and suite manifests
src/epic_intel/contracts/     versioned task and report contracts
src/epic_intel/runtime/       child-process graph execution and deterministic tools
src/epic_intel/evaluation/    hard gates, graders, integrity hashes, artifacts
src/epic_intel/policy/        fail-closed publication and tool policy
src/epic_intel/research/      worktrees, ledger, statistical acceptance
site/                         static project homepage and poster source
tests/                        contract, gate, CLI, timeout, and research tests
program.md                    human-authored research-agent instructions
```

## Design provenance

This is a clean public implementation informed by two ideas:

- [`karpathy/autoresearch`](https://github.com/karpathy/autoresearch): fixed evaluation,
  narrow edit surface, fixed budgets, experiment ledger, keep/discard loop;
- the private `Hylouis233/epic-intel` deployment: event-versus-case separation,
  deterministic aggregation, strong schemas, evidence binding, auditing, and human gates.

No private Git history is inherited. The public core is deliberately deployment-agnostic.
See [MIGRATION.md](MIGRATION.md) for the boundary between this repository and a private
adapter.

## Contributing

Start with [CONTRIBUTING.md](CONTRIBUTING.md) and the
[threat model](THREAT_MODEL.md). Changes that make an evaluator depend on candidate code,
weaken a fail-closed default, introduce live patient data, or enable publication by default
will not be accepted.

## License

Code is released under the [MIT License](LICENSE). Synthetic benchmark task data are
dedicated to the public domain under CC0 1.0 as declared in each task file.
