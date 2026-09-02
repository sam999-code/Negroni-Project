---
name: negroni-governed-agents
description: Design, review, or harden AI-agent workflows that need explicit authority boundaries, owner approval gates, dry-run defaults, safe filesystem scope, audit evidence, and fail-closed stop conditions. Use for agent architecture, automation plans, MCP integrations, local assistants, research pipelines, or code reviews where an agent could write files, launch programs, call external services, send messages, delete data, or take financial actions.
---

# Negroni Governed Agents

Turn an agent idea or implementation into a bounded workflow whose authority is visible, testable, and difficult to escalate accidentally.

## Workflow

### 1. Establish the boundary

Identify the requested outcome, affected systems, data sensitivity, writable locations, external services, and actions with real-world impact. Treat missing authority as absent authority.

Separate the workflow into these capability levels:

- `NONE`: analyze and propose only.
- `READ_ONLY`: inspect state without changing it.
- `PREPARE`: create local drafts or staged artifacts inside approved roots.
- `EXECUTE`: perform an external or consequential action only when explicitly authorized.

Never infer `EXECUTE` from permission to inspect, diagnose, design, test, or prepare.

### 2. Inspect before mutation

Collect current evidence before changing code or state. For repositories, inspect branch, revision, and working-tree status. For runtimes, inspect process and listener state without starting anything. Preserve unrelated user changes.

If evidence is unavailable, label the fact `UNCONFIRMED`; do not convert an assumption into a readiness claim.

### 3. Build the authority matrix

For every tool or operation, record:

| Operation | Default | Required authority | Approval point | Evidence |
|---|---|---|---|---|
| Read local metadata | Allowed | `READ_ONLY` | None | Paths and timestamps |
| Write a local draft | Denied outside safe roots | `PREPARE` | Scope approval | Diff or artifact |
| Launch a process | Denied | `EXECUTE` | Explicit owner approval | Command and result |
| Call an external service | Denied | `EXECUTE` | Explicit owner approval | Request outcome |
| Delete or overwrite | Denied | `EXECUTE` | Exact-target approval | Recovery plan and result |

Adapt the rows to the system under review. Keep financial execution, credential access, external messages, production deployment, and irreversible deletion denied unless the user explicitly places that exact action in scope.

### 4. Add enforceable gates

Prefer controls in code and configuration over prose alone:

- default to dry-run or proposal mode;
- use allowlisted roots and services;
- reject protected targets before initialization;
- keep preparation separate from execution;
- require explicit approval tokens or state transitions;
- make retries bounded and observable;
- write append-only audit records where appropriate;
- keep secrets out of logs, fixtures, and repository history.

Read [references/governance-patterns.md](references/governance-patterns.md) when designing a new system or selecting concrete gate patterns.

### 5. Define stop conditions

Stop rather than improvise when authority is missing, a protected target is detected, identity cannot be verified, required evidence is stale, a safety check fails, or repeated retries would hide a persistent fault.

Return a precise blocker and the smallest owner action needed to continue. A safety refusal is a successful gate, not an error to bypass.

### 6. Verify the implementation

Test both allowed and denied paths. The first integration test for a guarded connector should normally prove that the forbidden target is rejected. Verify that dry-run mode creates no external side effect and that approval cannot be skipped by calling a lower-level function directly.

Read [references/review-checklist.md](references/review-checklist.md) before issuing the final verdict.

### 7. Report the result

Lead with one verdict:

- `READY`: required controls were implemented and verified.
- `READY_WITH_LIMITS`: safe for the named scope, with explicit exclusions.
- `BLOCKED`: a required control, authority decision, or verification is missing.

Then report scope, evidence, changes, tests, runtime impact, remaining risks, and the next owner decision. Distinguish facts from assumptions.

## Output format

Use this compact structure:

```text
VERDICT: READY | READY_WITH_LIMITS | BLOCKED
SCOPE: <systems and actions covered>
AUTHORITY: <highest capability allowed>
CONTROLS: <enforced gates>
EVIDENCE: <files, tests, and observed state>
RUNTIME IMPACT: <none or exact impact>
EXCLUSIONS: <explicitly untouched systems>
NEXT DECISION: <smallest owner action, if any>
```

