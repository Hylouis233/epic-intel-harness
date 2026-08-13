# Private deployment boundary

The production platform and this public harness are separate products.

## Public core

This repository owns versioned contracts, deterministic event aggregation, candidate graph
execution, synthetic benchmarks, hard gates, quality scoring, research worktrees, experiment
records, and default-deny policy.

## Private adapter

A private deployment may implement data-source, model-provider, MCP/HTTP tool, persistence,
renderer, human-review, and publisher adapters. Those adapters must translate private data
into `TaskInput` and consume a verified `EventIntelligenceReport` without changing public
grader behavior.

Keep Dagster, databases, object storage, caches, administration UIs, live feeds, deployment
topology, credentials, incident documents, and notification infrastructure out of this
repository. Do not use Git subtree or history-preserving merges from the private repository.

## Import checklist

- prove the source file contains no secret or internal endpoint;
- remove production-specific imports and environment variables;
- replace live fixtures with synthetic CC0 data;
- preserve event-versus-case semantics and evidence IDs;
- add a public contract test;
- record provenance and license compatibility;
- copy into a new commit, never merge private history.

