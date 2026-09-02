# Project Retrospective

## What was achieved

The original Evolith/Hermes work produced a broad experimental AI operating-system architecture. Negroni Project preserves one of its clearest engineering outcomes: a governed autonomous-research subsystem that can prepare and inspect work while remaining structurally unable to execute external actions.

The preserved implementation includes deterministic policies, explicit autonomy levels, owner gates, safe path handling, append-only records, process-lock discipline, dry-run orchestration, and extensive negative safety tests.

## What was not achieved

The larger project did not establish a verified trading edge or reach a suitable state for live financial execution. This repository does not conceal that result and makes no performance claim.

## Why preserve it

The engineering lessons transfer directly to AI-agent systems outside finance:

- limiting tool authority;
- separating proposals from actions;
- making human approval explicit;
- preserving auditability;
- failing closed under ambiguous state;
- testing forbidden capabilities, not only intended behavior;
- producing deterministic artifacts from agent workflows.

## Publication boundary

The public edition excludes all private runtime state, broker and terminal integrations, recorded market data, credentials, local profiles, schedulers, machine paths, and execution code. It is a technical case study, not a deployable copy of the private environment.
