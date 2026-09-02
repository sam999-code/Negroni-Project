"""One tick of the research lead, dry-run only. HERMES-AUTONOMOUS-RESEARCH-002.

**A tick function, not a loop.** One call reads the queue, evaluates governance, writes the
heartbeat, the audit records and the dry-run report, and returns. The calling process owns the
clock, the sleeping and every operating-system observation; this module reads no clock, opens no
socket, starts no process and contains no loop over time. That split is what makes an unattended
supervisor testable -- every scenario is one ``tick`` call with injected observations -- and it is
also what makes activation an owner act: a function that runs once cannot keep itself running.

**The mode is DRY_RUN and there is no other member.** A mode that does not exist cannot be invoked,
which is the same enforcement-by-absence the package uses for broker surfaces. A future live mode is
a future owner decision and would arrive as a visible diff to :class:`RunnerMode`, not as a flag.

**The ceiling is LEVEL_1_SUPERVISED by default, on top of the G2 marker.** ``tick`` passes its
``ceiling`` to :func:`~integrations.hermes_research_orchestrator.levels.active_level`, so even a
valid digest-bound marker yields LEVEL_1 through this runner. Raising the lead to LEVEL_2 therefore
requires two visible acts -- the owner writing the marker, and an owner-ordered change to this
default -- which is owner decision 2 of HERMES-AUTONOMOUS-RESEARCH-002 made structural.

**Decision tokens are the owner's, verbatim.** The seven members of :class:`RunnerDecision` are the
exact status strings the owner specified. ``LEVEL_NOT_AUTHORISED`` and ``CANDIDATE_NOT_READY``
deliberately do not downgrade a decision: at LEVEL_1 the launch operation is *designed* to be
unauthorised, and a dry run starts nothing whatever the queue says, so the decision token names the
most actionable blocker instead -- an audit line may honestly read ``outcome: paused`` with
``level_not_authorised`` among its conditions while the decision says ``DATA_REQUIRED``.

**One bad queue line rejects the tick, not just the line.** The ledger discipline everywhere else in
the programme refuses a file whose digest chain fails, because reading the part that still verifies
would be deciding the edited part did not matter. The runner matches it: any unreadable, tampered or
unknown-key line makes the whole tick ``REJECTED_GOVERNANCE_RISK`` and no candidate is evaluated.
Unknown keys are judged against an allowlist of the schema's own key names rather than a blocklist
of forbidden vocabularies -- strictly stronger, and it keeps forbidden spellings out of this file.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from enum import Enum
from typing import Final

from integrations.hermes_research_orchestrator.audit import (
    AuditOutcome,
    AuditRecord,
    load_audit_log,
    record_for,
)
from integrations.hermes_research_orchestrator.levels import (
    AutomationLevel,
    ResearchOperation,
    active_level,
    governance_matrix_digest,
)
from integrations.hermes_research_orchestrator.queue import (
    ResearchCandidate,
    decode_candidate,
)
from integrations.hermes_research_orchestrator.roots import HermesLeadRootPolicy
from integrations.hermes_research_orchestrator.stops import (
    PreflightEnvironment,
    StopCondition,
    StopDecision,
    evaluate_preflight,
)
from integrations.intraday_research.contract import ResearchRefused

__all__ = [
    "AUDIT_FILE",
    "DRY_RUN_REPORT_FILE",
    "HEARTBEAT_FILE",
    "LOCK_DIR",
    "LOCK_FILE",
    "QUEUE_ALLOWED_KEYS",
    "QUEUE_FILE",
    "RUNNER_POLICY_ID",
    "RejectedLine",
    "RunnerDecision",
    "RunnerMode",
    "RunnerRefused",
    "TickObservations",
    "acquire_runner_lock",
    "decision_for",
    "release_runner_lock",
    "runner_heartbeat",
    "scan_queue",
    "tick",
]

RUNNER_POLICY_ID: Final = "HRO-RUNNER-v1"
"""One tick, dry-run only, everything written inside the lead's own root."""

QUEUE_FILE: Final = "queue.jsonl"
HEARTBEAT_FILE: Final = "heartbeat.json"
AUDIT_FILE: Final = "audit.jsonl"
DRY_RUN_REPORT_FILE: Final = "dry_run_report.json"
LOCK_DIR: Final = "locks"
LOCK_FILE: Final = "runner.lock"

QUEUE_ALLOWED_KEYS: Final[frozenset] = frozenset({
    "policy", "schema_version", "candidate_id", "candidate_name", "status", "priority",
    "assets", "timeframes", "context_timeframes", "hypothesis", "owner_approved_for_research",
    "data_required", "cost_model_required", "max_runtime_minutes", "allowed_operations",
    "forbidden_operations", "selected_skill_bundle", "stop_conditions", "latest_result_path",
    "next_action", "owner_gate_required", "recorded_at", "recorded_by", "implies_authority",
    "may_start_research", "content_digest",
})
"""Every key a queue line may carry -- the serialised schema and nothing else. A key outside this
set is refused whatever it is called, which covers every forbidden field family without this module
having to spell any of their names. A test pins this set to the seed's actual serialised form, so
schema drift fails a test rather than silently widening what a line may say."""


class RunnerRefused(ResearchRefused):
    """A runner operation was refused. Always fatal to the tick that caused it."""


class RunnerMode(Enum):
    """The only mode there is."""

    DRY_RUN = "DRY_RUN"

    @property
    def starts_research(self) -> bool:
        """``False``. A dry run answers what would happen; it never makes anything happen."""
        return False


class RunnerDecision(Enum):
    """The owner's seven decision tokens, verbatim. None of them starts, grades or emits anything."""

    DRY_RUN_OK = "DRY_RUN_OK"
    OWNER_APPROVAL_REQUIRED = "OWNER_APPROVAL_REQUIRED"
    DATA_REQUIRED = "DATA_REQUIRED"
    COST_MODEL_REQUIRED = "COST_MODEL_REQUIRED"
    PAUSED_GOVERNANCE_RISK = "PAUSED_GOVERNANCE_RISK"
    REJECTED_GOVERNANCE_RISK = "REJECTED_GOVERNANCE_RISK"
    FAILED_TESTS = "FAILED_TESTS"

    @property
    def implies_authority(self) -> bool:
        return False


_RISK_CONDITIONS: Final = frozenset({
    StopCondition.GOVERNANCE_RISK,
    StopCondition.CONFLICTING_LOCK_HELD,
    StopCondition.AUDIT_LOG_UNWRITABLE,
    StopCondition.GIT_DIRTY_IN_PROTECTED_PATH,
    StopCondition.OVERLAPPING_EDIT_IN_ANOTHER_TERMINAL,
})
"""The conditions that make a tick a governance pause rather than a candidate shortfall."""


def decision_for(stop: StopDecision) -> RunnerDecision:
    """The owner's token for a preflight decision. Severity order, most blocking first."""
    fired = set(stop.conditions)
    if fired & _RISK_CONDITIONS:
        return RunnerDecision.PAUSED_GOVERNANCE_RISK
    if StopCondition.TESTS_FAILING in fired:
        return RunnerDecision.FAILED_TESTS
    if StopCondition.OWNER_APPROVAL_ABSENT in fired:
        return RunnerDecision.OWNER_APPROVAL_REQUIRED
    if StopCondition.REQUIRED_DATA_MISSING in fired:
        return RunnerDecision.DATA_REQUIRED
    if StopCondition.COST_MODEL_MISSING in fired:
        return RunnerDecision.COST_MODEL_REQUIRED
    return RunnerDecision.DRY_RUN_OK


@dataclass(frozen=True, slots=True)
class TickObservations:
    """What the calling shell observed. Supplied, never gathered here.

    ``required_data_present`` and ``cost_model_present`` default to ``False`` because unverified
    data is absent data: a runner that assumed presence would start (at some future level) a study
    it could not finish and report the shortfall as a result.

    Attributes:
        observed_at: ISO-8601 with an offset, from the caller's clock.
        tests_passing: Whether the declared test selection passed on this working tree.
        native_gateway_running: Whether a native chat-gateway process was observed.
        gateway_port_open: Whether port 8644 was observed listening.
        git_dirty_protected_paths: Protected paths reported dirty. Empty is clean.
        overlapping_paths: Paths another terminal or agent is known to be editing.
        required_data_present: Whether every entry in ``data_required`` was verified present.
        cost_model_present: Whether a declared cost model was verified present.
    """

    observed_at: str
    tests_passing: bool
    native_gateway_running: bool
    gateway_port_open: bool
    git_dirty_protected_paths: tuple[str, ...] = ()
    overlapping_paths: tuple[str, ...] = ()
    required_data_present: bool = False
    cost_model_present: bool = False

    def __post_init__(self) -> None:
        if not str(self.observed_at).strip():
            raise RunnerRefused("observed_at is required; the caller owns the clock")


@dataclass(frozen=True, slots=True)
class RejectedLine:
    """One queue line the tick refused, and why."""

    line_number: int
    reason: str
    candidate_id: str = ""


def acquire_runner_lock(policy: HermesLeadRootPolicy, lead_root: str | pathlib.Path,
                        *, pid: int, start_token: str, acquired_at: str) -> pathlib.Path:
    """Take the single-instance lock in the lead's own root.

    The pid is paired with an opaque start token because Windows reuses process ids. An existing
    lock with a different token refuses -- no lock is ever broken automatically, no process is ever
    killed, and an unreadable lock refuses too: a lock that cannot say who holds it is held.

    Raises:
        RunnerRefused: The lock is held by someone else, or unreadable.
    """
    target = policy.write_target(
        pathlib.Path(lead_root) / LOCK_DIR / LOCK_FILE, what="runner lock")
    if target.exists():
        try:
            holder = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RunnerRefused(
                f"CONFLICTING_LOCK: the runner lock at {str(target)!r} is unreadable ({error}). "
                f"An unreadable lock is held; releasing it is an explicit owner act") from error
        if (holder.get("pid"), holder.get("start_token")) == (pid, start_token):
            return target
        raise RunnerRefused(
            f"CONFLICTING_LOCK: held by pid {holder.get('pid')!r} since "
            f"{holder.get('acquired_at')!r}. No lock is broken automatically")
    target.parent.mkdir(parents=True, exist_ok=True)
    document = {"policy": RUNNER_POLICY_ID, "pid": pid, "start_token": start_token,
                "acquired_at": acquired_at}
    staging = target.with_name(target.name + ".partial")
    staging.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    staging.replace(target)
    return target


def release_runner_lock(policy: HermesLeadRootPolicy, lead_root: str | pathlib.Path,
                        *, start_token: str) -> bool:
    """Release the lock, only if this holder took it. A foreign or unreadable lock is left alone."""
    target = policy.write_target(
        pathlib.Path(lead_root) / LOCK_DIR / LOCK_FILE, what="runner lock")
    if not target.exists():
        return False
    try:
        holder = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if holder.get("start_token") != start_token:
        return False
    target.unlink()
    return True


def scan_queue(policy: HermesLeadRootPolicy, lead_root: str | pathlib.Path
               ) -> tuple[tuple[ResearchCandidate, ...], tuple[RejectedLine, ...]]:
    """Read the queue, returning the latest record per candidate and every line it refused.

    A refused line does not crash the tick -- the tick must still write its heartbeat and audit --
    but the caller treats any refusal as rejecting the whole tick, per the module docstring.
    """
    target = policy.write_target(pathlib.Path(lead_root) / QUEUE_FILE, what="candidate queue")
    if not target.exists():
        return ((), ())
    latest: dict = {}
    order: list = []
    rejected: list = []
    for number, raw in enumerate(target.read_bytes().splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            rejected.append(RejectedLine(number, f"QUEUE_LINE_UNREADABLE: {error}"))
            continue
        if not isinstance(payload, dict):
            rejected.append(RejectedLine(number, "QUEUE_LINE_UNREADABLE: not a JSON object"))
            continue
        unknown = sorted(set(payload) - QUEUE_ALLOWED_KEYS)
        if unknown:
            rejected.append(RejectedLine(
                number,
                f"FORBIDDEN_OR_UNKNOWN_KEY: {unknown}. The schema's own key names are the whole "
                f"of what a queue line may say",
                candidate_id=str(payload.get("candidate_id", ""))))
            continue
        try:
            candidate, claimed = decode_candidate(raw)
        except ResearchRefused as error:
            rejected.append(RejectedLine(
                number, str(error), candidate_id=str(payload.get("candidate_id", ""))))
            continue
        if claimed != candidate.content_digest:
            rejected.append(RejectedLine(
                number,
                f"QUEUE_DIGEST_MISMATCH: line claims {claimed[:16]}... and its content hashes to "
                f"{candidate.content_digest[:16]}...",
                candidate_id=candidate.candidate_id))
            continue
        if candidate.candidate_id not in latest:
            order.append(candidate.candidate_id)
        latest[candidate.candidate_id] = candidate
    return (tuple(latest[i] for i in order), tuple(rejected))


def runner_heartbeat(*, observed_at: str, level: AutomationLevel, tick_number: int,
                     decisions: dict, rejected_lines: tuple,
                     observations: TickObservations) -> dict:
    """The E-contract heartbeat, overwritten in place. Every denominator, always.

    ``accepted + paused + rejected + awaiting == candidate_count`` by construction, and a test
    holds it there: a heartbeat whose counts do not sum is a heartbeat hiding a candidate.
    """
    values = list(decisions.values())
    accepted = sum(1 for d in values if d is RunnerDecision.DRY_RUN_OK)
    paused = sum(1 for d in values if d in (RunnerDecision.PAUSED_GOVERNANCE_RISK,
                                            RunnerDecision.FAILED_TESTS))
    rejected = (sum(1 for d in values if d is RunnerDecision.REJECTED_GOVERNANCE_RISK)
                + len(rejected_lines))
    awaiting = sum(1 for d in values if d in (RunnerDecision.OWNER_APPROVAL_REQUIRED,
                                              RunnerDecision.DATA_REQUIRED,
                                              RunnerDecision.COST_MODEL_REQUIRED))
    paused_reason = ""
    if rejected:
        paused_reason = "queue line refused; see the dry-run report"
    elif paused:
        paused_reason = "governance pause; see the audit log"
    return {
        "policy": RUNNER_POLICY_ID,
        "last_tick_at": observed_at,
        "mode": RunnerMode.DRY_RUN.value,
        "level": level.value,
        "tick": tick_number,
        "candidate_count": len(values) + len(rejected_lines),
        "accepted_count": accepted,
        "paused_count": paused,
        "rejected_count": rejected,
        "awaiting_owner_or_inputs_count": awaiting,
        "state": "paused" if paused_reason else "idle",
        "paused_reason": paused_reason,
        "native_gateway_running": observations.native_gateway_running,
        "gateway_port_open": observations.gateway_port_open,
        "governance_digest": governance_matrix_digest(),
        "execution_authority": "NONE",
        "selection_authorised": False,
        "confirmation_authorised": False,
    }


def _overwrite_json(policy: HermesLeadRootPolicy, path: pathlib.Path, document: dict) -> None:
    target = policy.write_target(path, what="runner status")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(target.name + ".partial")
    staging.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
    staging.replace(target)


def tick(*, lead_root: str | pathlib.Path, observations: TickObservations,
         pid: int, start_token: str,
         ceiling: AutomationLevel = AutomationLevel.LEVEL_1_SUPERVISED) -> dict:
    """One dry-run tick. Reads the queue, decides, records, exits.

    Writes exactly four things, all inside the lead's own root: the lock, the audit records, the
    dry-run report, and the heartbeat. It appends nothing to the queue -- advancing a candidate is
    the lead's work at a level this runner does not reach, and the owner's by hand today.

    Args:
        lead_root: The directory the research lead owns. Never defaulted; a target outside it is
            refused by the root policy however this function is called.
        observations: What the calling shell observed; see :class:`TickObservations`.
        pid: The calling process id, for the lock.
        start_token: An opaque token from the caller, paired with the pid in the lock.
        ceiling: The highest level this tick will run at. Defaults to LEVEL_1_SUPERVISED --
            owner decision 2 of HERMES-AUTONOMOUS-RESEARCH-002. Raising it is an owner-ordered
            code change, on top of the digest-bound G2 marker.

    Returns:
        A summary: the per-candidate decisions, the rejected lines, and where everything was
        written. The summary is a report of what was recorded, never an instruction.
    """
    root = pathlib.Path(lead_root)
    policy = HermesLeadRootPolicy.owning(root)
    level = active_level(root, ceiling=ceiling)
    acquire_runner_lock(policy, root, pid=pid, start_token=start_token,
                        acquired_at=observations.observed_at)
    try:
        heartbeat_path = policy.write_target(root / HEARTBEAT_FILE, what="runner status")
        tick_number = 1
        if heartbeat_path.exists():
            try:
                tick_number = int(json.loads(
                    heartbeat_path.read_text(encoding="utf-8")).get("tick", 0)) + 1
            except (OSError, json.JSONDecodeError, ValueError):
                tick_number = 1

        candidates, rejected_lines = scan_queue(policy, root)
        audit_log = load_audit_log(root / AUDIT_FILE, policy)

        decisions: dict = {}
        entries: list = []
        if rejected_lines:
            # One bad line rejects the tick: no candidate is evaluated against a ledger that has
            # stopped verifying, and every refused line is audited so the owner can act on it.
            for line in rejected_lines:
                audit_log.append(AuditRecord(
                    record_id=f"TICK-{tick_number:04d}-LINE-{line.line_number:04d}",
                    occurred_at=observations.observed_at,
                    level=level,
                    operation=ResearchOperation.MAINTAIN_CANDIDATE_QUEUE,
                    outcome=AuditOutcome.REFUSED,
                    candidate_id=line.candidate_id,
                    detail=line.reason,
                    conditions=(StopCondition.GOVERNANCE_RISK.value,),
                    decision=RunnerDecision.REJECTED_GOVERNANCE_RISK.value,
                    governance_digest=governance_matrix_digest()))
                entries.append({"line_number": line.line_number,
                                "candidate_id": line.candidate_id,
                                "decision": RunnerDecision.REJECTED_GOVERNANCE_RISK.value,
                                "reason": line.reason})
        else:
            for candidate in candidates:
                environment = PreflightEnvironment(
                    level=level,
                    candidate_is_owner_approved=candidate.owner_approved_for_research,
                    candidate_is_ready=candidate.status.may_start_research,
                    required_data_present=observations.required_data_present,
                    cost_model_present=observations.cost_model_present,
                    cost_model_required=candidate.cost_model_required,
                    tests_passing=observations.tests_passing,
                    audit_log_writable=True,
                    max_runtime_minutes=candidate.max_runtime_minutes,
                    git_dirty_protected_paths=observations.git_dirty_protected_paths,
                    overlapping_paths=observations.overlapping_paths,
                    native_gateway_running=observations.native_gateway_running,
                    gateway_port_open=observations.gateway_port_open)
                stop = evaluate_preflight(
                    environment, ResearchOperation.LAUNCH_BOUNDED_RESEARCH_JOB)
                decision = decision_for(stop)
                decisions[candidate.candidate_id] = decision
                audit_log.append(record_for(
                    stop,
                    record_id=f"TICK-{tick_number:04d}-{candidate.candidate_id}",
                    occurred_at=observations.observed_at,
                    level=level,
                    candidate_id=candidate.candidate_id,
                    runner_decision=decision.value,
                    selected_skill_bundle=candidate.selected_skill_bundle,
                    owner_gate_required=candidate.owner_gate_required))
                entries.append({"candidate_id": candidate.candidate_id,
                                "decision": decision.value,
                                "would_start": False,
                                "blockers": [c.value for c in stop.conditions],
                                "evidence": list(stop.evidence)})

        report = {"policy": RUNNER_POLICY_ID, "generated_at": observations.observed_at,
                  "mode": RunnerMode.DRY_RUN.value, "level": level.value, "tick": tick_number,
                  "entries": entries, "execution_authority": "NONE",
                  "governance_digest": governance_matrix_digest()}
        _overwrite_json(policy, root / DRY_RUN_REPORT_FILE, report)
        heartbeat = runner_heartbeat(
            observed_at=observations.observed_at, level=level, tick_number=tick_number,
            decisions=decisions, rejected_lines=rejected_lines, observations=observations)
        _overwrite_json(policy, root / HEARTBEAT_FILE, heartbeat)
        return {"tick": tick_number, "level": level.value, "mode": RunnerMode.DRY_RUN.value,
                "decisions": {i: d.value for i, d in decisions.items()},
                "rejected_lines": [
                    {"line_number": r.line_number, "reason": r.reason,
                     "candidate_id": r.candidate_id} for r in rejected_lines],
                "heartbeat": heartbeat,
                "written": [HEARTBEAT_FILE, AUDIT_FILE, DRY_RUN_REPORT_FILE]}
    finally:
        release_runner_lock(policy, root, start_token=start_token)
