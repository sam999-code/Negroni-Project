---
name: negroni-governed-agents
description: Design and audit bounded AI-agent workflows.
---

# Negroni Governed Agents Skill

Turn an agent idea or implementation into a bounded workflow whose authority is visible, testable, and difficult to escalate accidentally. This skill governs decisions and verification; it does not grant tools, credentials, or execution authority.

## When to Use

Use this skill for agent architecture, automation plans, MCP integrations, local assistants, research pipelines, and code reviews where an agent could write files, launch programs, call external services, send messages, delete data, deploy software, or take financial actions.

Trigger it when the user asks to design, review, audit, harden, or approve an autonomous or tool-using workflow.

## Prerequisites

- The requested outcome and affected systems are identifiable.
- Available tools and their side effects can be inspected.
- The owner retains control of consequential actions.

If any prerequisite is missing, continue only with read-only analysis and report the gap as `UNCONFIRMED`.

## How to Run

Load this skill through the host's native Agent Skills mechanism. If the host does not support skills, use the repository's `UNIVERSAL_PROMPT.md` as system or custom instructions.

Apply the procedure below to the user's actual task. Do not treat loading this skill as authorization to mutate anything.

## Quick Reference

| Level | Meaning | Default examples |
|---|---|---|
| `NONE` | Analyze and propose only | plans, explanations, risk reviews |
| `READ_ONLY` | Inspect without changing state | files, metadata, status, logs |
| `PREPARE` | Create staged artifacts in approved roots | drafts, patches, dry-run output |
| `EXECUTE` | Cause external or consequential effects | launches, messages, deployments, deletion |

Never infer `EXECUTE` from permission to inspect, diagnose, design, test, or prepare.

## Procedure

### 1. Establish the boundary

Identify the requested outcome, affected systems, data sensitivity, writable locations, external services, and actions with real-world impact. Record explicit exclusions. Treat missing authority as absent authority.

Completion criterion: every affected system and the highest permitted capability level are stated.

### 2. Inspect before mutation

Collect current evidence before changing code or state. For repositories, inspect branch, revision, and working-tree status. For runtimes, inspect process and listener state without starting anything. Preserve unrelated user changes.

If evidence is unavailable, label the fact `UNCONFIRMED`; do not convert an assumption into a readiness claim.

Completion criterion: relevant current state is evidenced or explicitly marked unconfirmed.

### 3. Build the authority matrix

For every tool or operation, record:

| Operation | Default | Required authority | Approval point | Evidence |
|---|---|---|---|---|
| Read local metadata | Allowed | `READ_ONLY` | None | Paths and timestamps |
| Write a local draft | Denied outside safe roots | `PREPARE` | Scope approval | Diff or artifact |
| Launch a process | Denied | `EXECUTE` | Explicit owner approval | Command and result |
| Call an external service | Denied | `EXECUTE` | Explicit owner approval | Request outcome |
| Delete or overwrite | Denied | `EXECUTE` | Exact-target approval | Recovery plan and result |

Adapt the rows to the system. Keep financial execution, credential access, external messages, production deployment, and irreversible deletion denied unless the user explicitly places that exact action in scope.

Completion criterion: every consequential operation has an explicit default and approval point.

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

Completion criterion: critical boundaries are mechanically enforced or reported as blockers.

### 5. Define stop conditions

Stop rather than improvise when authority is missing, a protected target is detected, identity cannot be verified, required evidence is stale, a safety check fails, or repeated retries would hide a persistent fault.

Return a precise blocker and the smallest owner action needed to continue. A safety refusal is a successful gate, not an error to bypass.

Completion criterion: each serious failure mode has a fail-closed outcome.

### 6. Verify denied and allowed paths

Test both allowed and denied paths. The first integration test for a guarded connector should normally prove that the forbidden target is rejected. Verify that dry-run mode creates no external side effect and that approval cannot be skipped by calling a lower-level function directly.

Read [references/review-checklist.md](references/review-checklist.md) before issuing the final verdict.

Completion criterion: negative-path evidence exists alongside happy-path evidence.

### 7. Report the result

Lead with one verdict:

- `READY`: required controls were implemented and verified.
- `READY_WITH_LIMITS`: safe for the named scope, with explicit exclusions.
- `BLOCKED`: a required control, authority decision, or verification is missing.

Then report scope, evidence, changes, tests, runtime impact, remaining risks, and the next owner decision. Distinguish facts from assumptions.

## Pitfalls

- Do not confuse a written policy with an enforced gate.
- Do not treat a successful connection as proof that the target is safe.
- Do not hide missing evidence behind optimistic language.
- Do not let a retry loop replace escalation.
- Do not grant the host LLM more authority than the user granted for the task.
- Do not assume tool names or permission systems are identical across hosts.

## Verification

Use this output format:

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

Before returning `READY`, confirm every item in `references/review-checklist.md` that applies to the task.

