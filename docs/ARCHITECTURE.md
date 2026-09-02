# Architecture

## Purpose

The package demonstrates how an AI-assisted research lead can be useful without being granted execution authority. The design separates what an agent may describe, validate, queue, and report from anything that could act externally.

## Main components

| Component | Responsibility |
|---|---|
| `levels.py` | Capability levels, allowed operations, and prohibited operations |
| `queue.py` | Versioned candidate records and deterministic queue transitions |
| `stops.py` | Fail-closed preflight conditions and pause decisions |
| `dry_run.py` | Pure validation and task-brief preparation |
| `roots.py` | Research-root containment and protected-root exclusions |
| `audit.py` | Append-only audit outcomes and integrity metadata |
| `runner.py` | Bounded queue processing with lock discipline and dry-run default |
| `report.py` | Deterministic daily reporting |
| `seed.py` | Historical example candidate used to exercise the governance model |

## Decision flow

```text
candidate input
    -> schema and provenance validation
    -> capability-level check
    -> safety and governance stop evaluation
    -> dry-run decision
    -> audit record and report
    -> owner review when required
```

There is no downstream execution stage in this repository.

## Enforcement by absence

The research orchestrator has no generic function dispatcher and imports no broker client. Structural tests inspect the package's syntax and public records to ensure execution-shaped functions and fields do not enter the package unnoticed.

## Data model principles

- Records carry explicit policy and schema identifiers.
- Canonical JSON supports reproducible digests.
- Conflicting duplicate records fail closed.
- Approval is a field supplied by the owner, not a state inferred by the agent.
- A pause remains visible until the responsible actor resolves it.

## Provenance

This portfolio edition was extracted from the private Evolith repository at source commit `dcbd8f91c2098e1a4d68a1a9d2ea7b340b83c5fb`. It is a clean snapshot and intentionally does not reproduce the private repository's history or operational environment.
