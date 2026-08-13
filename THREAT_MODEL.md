# Threat model

## Protected assets

- benchmark inputs and answer keys;
- evaluation and policy code;
- report and task contracts;
- private deployment details and credentials;
- row-level or identifiable health data;
- publication, notification, and database side effects;
- the integrity of the kept research branch and experiment ledger.

## Adversaries and failures

The harness assumes candidate code may crash, loop, overfit visible tasks, emit oversized
output, mislabel event records as cases, invent citations, repeat sensitive source strings,
follow prompt injection, attempt unauthorized tools, or modify protected files. An external
coding agent may also accidentally change Git history or unrelated files.

## Controls in v0.1

- new public repository without private history;
- synthetic CC0 benchmark data only;
- separate `TaskInput` and parent-owned `BenchmarkExpected` models;
- temporary candidate snapshots so `__file__` is not adjacent to the benchmark tree;
- candidate execution in a child process with a parent-enforced timeout;
- fixed tool-call and output budgets;
- declarative acyclic graph validation;
- read-only deterministic in-process tools;
- protected-plane hashing before and after a suite;
- research diffs restricted to `candidate/**`;
- disposable detached Git worktrees;
- non-compensatory hard gates;
- report status enum that excludes approval and publication;
- publication and side effects disabled by policy.

## Explicit limitations

The default child process is not an OS security sandbox. Candidate Python still runs with
the current user's filesystem and network privileges, so parent-owned expectations are
withheld by interface—not guaranteed confidential against active disk enumeration. Use the
included no-network, read-only container profile or an external sandbox before running an
untrusted coding agent or candidate. Do not place secrets in the repository or environment.
Windows, macOS, and Linux process controls do not provide identical isolation guarantees.

The benchmark is an engineering test, not clinical validation. It covers synthetic event
intelligence only and does not establish medical safety, epidemiological validity, or
fitness for operational deployment.
