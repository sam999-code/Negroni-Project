# Security Policy

## Scope

Negroni Project is deliberately isolated from external execution systems. The published package must remain unable to reach broker APIs, trading terminals, order functions, private market-data stores, native gateways, or messaging endpoints.

## Required invariants

- Execution authority remains `NONE`.
- Dry-run is the default runner behavior.
- Owner approval is represented explicitly and cannot be inferred.
- Writable paths must remain inside a caller-declared research root.
- Safety and governance failures pause processing.
- No credentials, account identifiers, machine-specific paths, or runtime records belong in the repository.

## Reporting a problem

Open a GitHub issue describing the affected file and invariant. Do not include credentials, private paths, account information, or runtime data in an issue.

## Non-goals

This project is not a trading system and is not suitable for controlling financial accounts or other consequential external systems.
