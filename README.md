# Negroni Porject

Negroni Porject is a compact, source-available case study in governed AI-agent orchestration. It preserves a focused, reusable part of the Evolith/Hermes engineering work: deterministic research queues, bounded autonomy, fail-closed safety checks, owner approval gates, append-only audit records, and dry-run execution.

The unusual spelling of **Porject** is intentional and follows the project owner's chosen name.

## What this repository demonstrates

- explicit capability levels instead of implicit agent authority;
- deterministic candidate and status models;
- owner-controlled approval transitions;
- policy-enforced writable roots;
- stop conditions that pause rather than silently retry;
- audit records and deterministic reports;
- a runner whose default mode performs no external work;
- structural tests that prohibit broker, order, messaging, and execution surfaces.

## What it does not do

This repository does not connect to a broker, MetaTrader, trading terminal, private market-data store, native gateway, or messaging service. It cannot submit, modify, or close orders. It contains no credentials, private runtime state, or recorded market data.

The project is an engineering portfolio artifact. It makes no claim of trading profitability, predictive edge, or production readiness.

## Layout

```text
evolith_core/shared/                    deterministic canonical JSON helper
integrations/hermes_research_orchestrator/
                                        governed research orchestration
integrations/intraday_research/         minimal shared contracts and path policy
tests/hermes_research_orchestrator/      safety, firewall, and runner tests
docs/                                   architecture and project retrospective
```

## Requirements

- Python 3.12 or later
- pytest 8 or later for tests

## Run the tests

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest
```

The sanitized release candidate was verified with Python 3.12: **185 tests passed**.

## Safety posture

The central invariant is `execution_authority = NONE`. A promising result may be prepared for owner review; it cannot become an external action through this package. See [SECURITY.md](SECURITY.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Project status

This is a preserved and sanitized portfolio edition of discontinued experimental work. The original private system was larger and included local operational components that are intentionally absent here.

## License

No reuse license has been granted yet. The code is publicly viewable for portfolio and evaluation purposes. A formal license can be added later by the owner.
