# Review checklist

## Scope and authority

- The requested outcome and excluded systems are explicit.
- The highest granted capability is stated.
- Missing authority defaults to denied.
- External, financial, destructive, and credential-bearing actions have separate approval gates.

## Containment

- Writable roots and external destinations are allowlisted.
- Protected targets are rejected before initialization.
- Secrets are absent from code, logs, fixtures, and reports.
- Unrelated user changes are preserved.

## Runtime behavior

- Dry-run is the default where execution is possible.
- Preparation and execution have separate paths.
- Retries are bounded and observable.
- Stop conditions produce actionable errors.
- A kill switch exists for autonomous or recurring work.

## Verification

- Denied paths are tested before happy paths.
- Approval bypass attempts are tested.
- Runtime impact is observed, not assumed.
- Claims cite concrete files, checks, or test results.
- The verdict is `BLOCKED` when required evidence is unavailable.

