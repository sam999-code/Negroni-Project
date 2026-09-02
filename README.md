# Negroni Project

Negroni Project is a compact, open-source case study and portable skill for governed AI-agent orchestration across LLM systems. It works natively with Claude Code, Hermes Agent, and OpenAI Codex, with a universal prompt fallback for ChatGPT, Gemini, Llama, Mistral, DeepSeek, Qwen, Ollama-based models, and other LLM hosts.

It preserves a focused, public-safe part of the Evolith/Hermes engineering work: deterministic research queues, bounded autonomy, fail-closed safety checks, owner approval gates, append-only audit records, and dry-run execution.

[![Tests](https://github.com/sam999-code/Negroni-Project/actions/workflows/tests.yml/badge.svg)](https://github.com/sam999-code/Negroni-Project/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

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
skills/negroni-governed-agents/         portable Agent Skill source
.claude-plugin/                         Claude Code plugin and marketplace metadata
UNIVERSAL_PROMPT.md                     fallback for any system-instruction LLM
```

## Use it with your LLM

The skill has no runtime dependency on this Python package.

- **Claude Code:** install this repository as a plugin or copy the skill into `~/.claude/skills/`.
- **Hermes Agent:** `hermes skills install sam999-code/Negroni-Project/skills/negroni-governed-agents`
- **OpenAI Codex:** copy the skill into `~/.codex/skills/`.
- **Any other LLM:** use [UNIVERSAL_PROMPT.md](UNIVERSAL_PROMPT.md) as system, custom, or project instructions.

See the complete [installation and invocation guide](docs/INSTALLATION.md).

Example invocation:

```text
Use Negroni Governed Agents to audit this workflow and return an evidence-backed readiness verdict.
```

The skill helps design or review local assistants, MCP integrations, research pipelines, and automations that need explicit authority, owner approvals, safe roots, dry-run defaults, and stop conditions. It never grants tools or execution authority by itself.

## Requirements

- Python 3.12 or later
- pytest 8 or later for tests

## Run the tests

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest
```

The portable release was verified with Python 3.12: **190 tests passed**.

## Safety posture

The central invariant is `execution_authority = NONE`. A promising result may be prepared for owner review; it cannot become an external action through this package. See [SECURITY.md](SECURITY.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Project status

This is a preserved and sanitized portfolio edition of discontinued experimental work. The original private system was larger and included local operational components that are intentionally absent here.

## License

Released under the [MIT License](LICENSE).
