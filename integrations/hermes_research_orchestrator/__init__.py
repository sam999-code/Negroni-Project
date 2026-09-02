"""Hermes as Evolith's research lead: the design, and nothing running.

HERMES-AUTONOMOUS-RESEARCH-001. The full rationale is in
``docs/HERMES — Autonomous Research Lead.md``; what follows is what a reader of the code needs.

**This package supervises research. It does not perform it, and it cannot reach anything that
executes.** Evolith already has an autonomous research runtime -- the Campaign 001 controller,
runtime, lock and prospective evaluator in :mod:`integrations.research_orchestration` -- and this is
deliberately not a second one. The lead maintains a shortlist, decides whether a candidate is ready,
prepares the brief, and hands it to a person or a coding agent. Everything scientific still happens
in the released packages, under the released gates, against the released evidence.

**The lead writes in exactly one place.** :class:`~.roots.HermesLeadRootPolicy` is the only door, and
it refuses the Evolith repository, the vault, all five ``Evolith*`` live evidence roots and an Algory
checkout, before creating anything. That is a code-level property rather than a caller's discipline,
which is the distinction TASK-085B was written to establish.

**Nothing in this package is running.** There is no loop, no scheduler, no Startup entry, no lock
acquisition and no process. :func:`~.dry_run.dry_run` is the one function that does useful work today,
and it is pure. Activating LEVEL_2 is an owner act -- creating one marker file -- and building the
runner that acts on a LEVEL_2 decision is HERMES-AUTONOMOUS-RESEARCH-002.

**Read these first.** :mod:`~.levels` for what each automation level may do and the governance digest
that binds it; :mod:`~.stops` for the thirteen conditions, every one of which pauses;
:mod:`~.queue` for the candidate schema and why no status implies authority.
"""

from __future__ import annotations

from integrations.hermes_research_orchestrator.audit import (
    AUDIT_POLICY_ID,
    AUDIT_SCHEMA_VERSION,
    AuditLog,
    AuditOutcome,
    AuditRecord,
    AuditRefused,
    decode_audit_record,
    encode_audit_record,
    load_audit_log,
    record_for,
)
from integrations.hermes_research_orchestrator.dry_run import (
    DRY_RUN_POLICY_ID,
    FABRICATION_FIELDS,
    DryRunReport,
    dry_run,
    escalation_status,
    task_brief_for,
)
from integrations.hermes_research_orchestrator.levels import (
    APPROVAL_MARKER_NAME,
    APPROVED_DIGEST_KEY,
    FORBIDDEN_OPERATIONS,
    LEVEL_OPERATIONS,
    LEVEL_POLICY_ID,
    AutomationLevel,
    ForbiddenOperation,
    LevelNotDesigned,
    LevelRefused,
    ResearchOperation,
    active_level,
    governance_matrix,
    governance_matrix_digest,
    refuse_forbidden_operation,
)
from integrations.hermes_research_orchestrator.queue import (
    CANDIDATE_QUEUE_POLICY_ID,
    CANDIDATE_QUEUE_SCHEMA_VERSION,
    CandidateQueue,
    CandidateQueueRefused,
    CandidateStatus,
    ResearchCandidate,
    decode_candidate,
    encode_candidate,
    load_candidate_queue,
)
from integrations.hermes_research_orchestrator.report import (
    STATUS_POLICY_ID,
    daily_research_report,
    heartbeat_document,
    render_daily_report,
)
from integrations.hermes_research_orchestrator.runner import (
    RUNNER_POLICY_ID,
    RejectedLine,
    RunnerDecision,
    RunnerMode,
    RunnerRefused,
    TickObservations,
    acquire_runner_lock,
    decision_for,
    release_runner_lock,
    runner_heartbeat,
    scan_queue,
    tick,
)
from integrations.hermes_research_orchestrator.roots import (
    EVIDENCE_ROOT_NAMES,
    HERMES_WRITE_TARGET_REFUSED,
    HermesLeadRootPolicy,
    HermesWriteTargetRefused,
    looks_like_evolith_repository,
)
from integrations.hermes_research_orchestrator.seed import (
    CANDIDATE_001_HYPOTHESIS,
    CANDIDATE_001_ID,
    CANDIDATE_001_SKILL_BUNDLE,
    volatility_normalized_session_breakout,
)
from integrations.hermes_research_orchestrator.stops import (
    STOP_POLICY_ID,
    PreflightEnvironment,
    StopAction,
    StopCondition,
    StopDecision,
    StopRefused,
    evaluate_preflight,
)

__all__ = [
    "APPROVAL_MARKER_NAME",
    "APPROVED_DIGEST_KEY",
    "AUDIT_POLICY_ID",
    "AUDIT_SCHEMA_VERSION",
    "CANDIDATE_001_HYPOTHESIS",
    "CANDIDATE_001_ID",
    "CANDIDATE_001_SKILL_BUNDLE",
    "CANDIDATE_QUEUE_POLICY_ID",
    "CANDIDATE_QUEUE_SCHEMA_VERSION",
    "DRY_RUN_POLICY_ID",
    "EVIDENCE_ROOT_NAMES",
    "FABRICATION_FIELDS",
    "FORBIDDEN_OPERATIONS",
    "HERMES_WRITE_TARGET_REFUSED",
    "LEVEL_OPERATIONS",
    "LEVEL_POLICY_ID",
    "RUNNER_POLICY_ID",
    "STATUS_POLICY_ID",
    "STOP_POLICY_ID",
    "AuditLog",
    "AuditOutcome",
    "AuditRecord",
    "AuditRefused",
    "AutomationLevel",
    "CandidateQueue",
    "CandidateQueueRefused",
    "CandidateStatus",
    "DryRunReport",
    "ForbiddenOperation",
    "HermesLeadRootPolicy",
    "HermesWriteTargetRefused",
    "LevelNotDesigned",
    "LevelRefused",
    "PreflightEnvironment",
    "RejectedLine",
    "ResearchCandidate",
    "ResearchOperation",
    "RunnerDecision",
    "RunnerMode",
    "RunnerRefused",
    "StopAction",
    "StopCondition",
    "StopDecision",
    "StopRefused",
    "TickObservations",
    "acquire_runner_lock",
    "active_level",
    "daily_research_report",
    "decision_for",
    "decode_audit_record",
    "decode_candidate",
    "dry_run",
    "encode_audit_record",
    "encode_candidate",
    "escalation_status",
    "evaluate_preflight",
    "governance_matrix",
    "governance_matrix_digest",
    "heartbeat_document",
    "load_audit_log",
    "load_candidate_queue",
    "looks_like_evolith_repository",
    "record_for",
    "refuse_forbidden_operation",
    "release_runner_lock",
    "render_daily_report",
    "runner_heartbeat",
    "scan_queue",
    "task_brief_for",
    "tick",
    "volatility_normalized_session_breakout",
]
