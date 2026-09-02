# Governance patterns

Use the smallest set of patterns that makes the workflow enforceable.

## Capability separation

Model inspection, preparation, and execution as distinct capabilities. Give each one a separate entry point where practical. A caller with preparation authority must not acquire execution authority through an internal helper.

## Fail-closed initialization

Validate identity, target, environment, and policy before opening a connection or starting a worker. Refuse ambiguous or protected targets. Do not continue with a warning when the check is a safety boundary.

## Safe-root policy

Resolve candidate paths to absolute canonical paths. Permit writes only when the resolved target is inside an allowlisted root. Reject broad roots, traversal, symlink escapes, and unresolved environment variables.

## Proposal and commit

Use two phases for consequential actions:

1. Prepare a human-readable proposal with exact targets and expected impact.
2. Execute only after explicit approval of that proposal.

Invalidate approval when the proposal changes.

## Dry-run default

Dry-run should exercise validation and produce the planned action without performing it. Test that it does not create external side effects.

## Append-only evidence

Record decisions, approvals, stop reasons, and outcomes in an append-only format when accountability matters. Redact secrets before serialization. Prefer deterministic timestamps and canonical serialization for reproducible tests.

## Kill switch and bounded retries

Provide a visible disable control for autonomous workers. Bound retries by count and time. Escalate persistent failure rather than looping silently.

## Negative-first testing

Test the forbidden path before the allowed path:

- protected environment is rejected;
- missing approval is rejected;
- path outside the safe root is rejected;
- dry-run makes no external call;
- direct lower-level invocation cannot bypass policy;
- secrets never appear in logs or fixtures.

