"""What the lead did, and under which rules. HERMES-AUTONOMOUS-RESEARCH-001 PART 5.

**The audit log records refusals as carefully as actions.** A log that only recorded what happened
would make a lead that refused everything indistinguishable from a lead that was never asked, and the
overwhelmingly common record in a healthy supervised loop is a refusal: the level was not authorised,
the candidate was not approved, the tree was dirty. Those are the records an owner reads.

**Every record carries the governance digest it was written under.** ``governance_digest`` is the
SHA-256 of :func:`~integrations.hermes_research_orchestrator.levels.governance_matrix`, so a reader
can tell whether the rules in force when a record was written are the rules in force now. Without it,
loosening a level's permissions would silently reinterpret the entire history: every past record would
read as if it had been taken under the new, wider rules.

**Nothing here writes an outcome.** An audit record says an operation was attempted, permitted or
refused; it never says a hypothesis worked. Results live in the artifacts the research job produced,
at the path the candidate names, and the lead reports where they are rather than what they showed.
That separation is what keeps a supervisor's log from becoming a second, unreviewed evidence store.

**The clock is injected.** This module has no ``datetime`` import. The process that owns the loop owns
the clock, which is the released convention -- ``research_lock`` states it plainly -- and it is what
makes an append testable without a wall-clock second.

**An unwritable audit log is a stop condition, not a warning.** The append path raises, the caller
pauses, and no work proceeds unrecorded. A loop that carried on when it could not write down what it
was doing would be the one configuration in which none of the other guarantees could be checked
afterwards.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Final

from evolith_core.shared.canonical_json import canonical_bytes
from integrations.hermes_research_orchestrator.levels import (
    AutomationLevel,
    ResearchOperation,
    governance_matrix_digest,
)
from integrations.hermes_research_orchestrator.roots import HermesLeadRootPolicy
from integrations.hermes_research_orchestrator.stops import StopDecision
from integrations.intraday_research.contract import ResearchRefused

__all__ = [
    "AUDIT_POLICY_ID",
    "AUDIT_SCHEMA_VERSION",
    "AuditLog",
    "AuditOutcome",
    "AuditRecord",
    "AuditRefused",
    "decode_audit_record",
    "encode_audit_record",
    "load_audit_log",
    "record_for",
]

AUDIT_POLICY_ID: Final = "HRO-AUDIT-v1"
"""Append-only, digest at write, governance digest on every line."""

AUDIT_SCHEMA_VERSION: Final = 2
"""A line without this, or with a version this build does not know, is refused rather than guessed at.

Version 2 added ``decision``, ``selected_skill_bundle``, ``owner_gate_required`` and
``execution_authority`` under HERMES-AUTONOMOUS-RESEARCH-002, so a runner tick's audit line carries
the owner's contract fields. Version-1 lines are refused rather than upgraded; none were ever
written -- the format changed before the first live audit file existed.
"""


class AuditRefused(ResearchRefused):
    """An audit operation was refused. Always fatal to the tick that caused it."""


class AuditOutcome(Enum):
    """What became of an attempt. Four members; only one of them is work being done."""

    PERMITTED = "permitted"
    REFUSED = "refused"
    PAUSED = "paused"
    ESCALATED_TO_OWNER = "escalated_to_owner"

    @property
    def implies_authority(self) -> bool:
        """``False`` for every outcome. ``PERMITTED`` means a *research* operation was allowed to
        proceed under a level's matrix -- never that anything was authorised to trade, confirm or
        emit a signal, none of which is an operation this package can express."""
        return False

    @property
    def is_work(self) -> bool:
        return self is AuditOutcome.PERMITTED


@dataclass(frozen=True, slots=True)
class AuditRecord:
    """One line of the audit log. Frozen; a correction is a new record, never an edit.

    Attributes:
        record_id: Unique within the log. Derived by the caller from the tick and the candidate, so a
            restart that re-reaches the same step computes the same id instead of allocating a new
            one -- the convention the autonomous runtime already follows.
        occurred_at: ISO-8601 with an offset, supplied by the calling process.
        level: The automation level in force.
        operation: What was attempted.
        outcome: What became of it.
        candidate_id: The candidate concerned, or empty for a lead-wide record.
        detail: One line of human-readable explanation.
        conditions: The stop conditions that fired, if any.
        governance_digest: SHA-256 of the governance matrix in force at write time.
        decision: The runner decision token for this candidate, or empty for a non-runner record.
        selected_skill_bundle: The candidate's declared bundle, carried so the audit line shows what
            a research job would have been allowed to load.
        owner_gate_required: The candidate's declared gate, carried for the same reason.
        execution_authority: Always ``"NONE"``. A field rather than a constant so that the refusal
            of any other value is a released behaviour a test can demonstrate, not a habit.
    """

    record_id: str
    occurred_at: str
    level: AutomationLevel
    operation: ResearchOperation
    outcome: AuditOutcome
    detail: str
    governance_digest: str
    candidate_id: str = ""
    conditions: tuple[str, ...] = ()
    decision: str = ""
    selected_skill_bundle: tuple[str, ...] = ()
    owner_gate_required: bool = False
    execution_authority: str = "NONE"
    _digest_cache: list = field(default_factory=list, compare=False, repr=False, init=False)

    def __post_init__(self) -> None:
        for name in ("record_id", "occurred_at", "detail", "governance_digest"):
            if not str(getattr(self, name)).strip():
                raise AuditRefused(f"audit record {name!r} is required")
        if len(str(self.governance_digest).strip()) != 64:
            raise AuditRefused("governance_digest must be a 64-character digest")
        if self.outcome is not AuditOutcome.PERMITTED and not self.conditions:
            if self.outcome is AuditOutcome.REFUSED or self.outcome is AuditOutcome.PAUSED:
                raise AuditRefused(
                    f"REFUSAL_WITHOUT_CONDITION: {self.record_id} is {self.outcome.value} and names "
                    f"no condition. A stop nobody can attribute is the record an owner cannot act on")
        if str(self.execution_authority) != "NONE":
            raise AuditRefused(
                f"EXECUTION_AUTHORITY_ASSERTED: {self.record_id} claims execution_authority "
                f"{self.execution_authority!r}. An audit record of this lead can state NONE and "
                f"nothing else; there is no path by which the lead could have acquired one")
        if self.outcome is AuditOutcome.PERMITTED and self.conditions:
            raise AuditRefused(
                f"{self.record_id}: permitted, yet {list(self.conditions)} fired. Every condition "
                f"pauses; a permitted record that names one is two facts that contradict each other")

    @property
    def implies_authority(self) -> bool:
        return False

    def as_dict(self) -> dict:
        return {"policy": AUDIT_POLICY_ID, "schema_version": AUDIT_SCHEMA_VERSION,
                "record_id": self.record_id, "occurred_at": self.occurred_at,
                "level": self.level.value, "operation": self.operation.value,
                "outcome": self.outcome.value, "candidate_id": self.candidate_id,
                "detail": self.detail, "conditions": list(self.conditions),
                "decision": self.decision,
                "selected_skill_bundle": list(self.selected_skill_bundle),
                "owner_gate_required": self.owner_gate_required,
                "execution_authority": self.execution_authority,
                "governance_digest": self.governance_digest,
                "implies_authority": self.implies_authority}

    @property
    def content_digest(self) -> str:
        if not self._digest_cache:
            self._digest_cache.append(hashlib.sha256(canonical_bytes(self.as_dict())).hexdigest())
        return self._digest_cache[0]


def record_for(decision: StopDecision, *, record_id: str, occurred_at: str,
               level: AutomationLevel, candidate_id: str = "",
               detail: str = "", runner_decision: str = "",
               selected_skill_bundle: tuple[str, ...] = (),
               owner_gate_required: bool = False) -> AuditRecord:
    """Build the audit record a :class:`StopDecision` implies.

    Derived rather than hand-written so that a decision and the record of it cannot disagree -- the
    failure mode where a loop pauses and logs that it proceeded is exactly the one an audit exists to
    make impossible.
    """
    paused = not decision.action.may_start_work
    return AuditRecord(
        record_id=record_id, occurred_at=occurred_at, level=level,
        operation=decision.operation,
        outcome=AuditOutcome.PAUSED if paused else AuditOutcome.PERMITTED,
        candidate_id=candidate_id,
        detail=detail or ("; ".join(decision.evidence) if paused else "preflight clear"),
        conditions=tuple(c.value for c in decision.conditions),
        decision=runner_decision,
        selected_skill_bundle=selected_skill_bundle,
        owner_gate_required=owner_gate_required,
        governance_digest=governance_matrix_digest())


def encode_audit_record(record: AuditRecord) -> bytes:
    """One record as a canonical line, digest computed here and never accepted from a caller."""
    payload = dict(record.as_dict())
    payload["content_digest"] = hashlib.sha256(canonical_bytes(record.as_dict())).hexdigest()
    return canonical_bytes(payload)


def decode_audit_record(raw: bytes) -> tuple[AuditRecord, str]:
    """Parse one line into a record and the digest the file claims for it.

    Raises:
        AuditRefused: Unreadable, an unknown schema version, or an unrecognised enum value.
    """
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AuditRefused(f"AUDIT_LINE_UNREADABLE: {error}") from error
    if not isinstance(payload, dict):
        raise AuditRefused("AUDIT_LINE_UNREADABLE: line is not a JSON object")
    if payload.get("schema_version") != AUDIT_SCHEMA_VERSION:
        raise AuditRefused(
            f"AUDIT_SCHEMA_VERSION_UNKNOWN: line declares {payload.get('schema_version')!r}, this "
            f"build writes {AUDIT_SCHEMA_VERSION}")
    try:
        level = AutomationLevel(str(payload.get("level", "")))
        operation = ResearchOperation(str(payload.get("operation", "")))
        outcome = AuditOutcome(str(payload.get("outcome", "")))
    except ValueError as error:
        raise AuditRefused(f"AUDIT_ENUM_UNKNOWN: {error}") from error
    record = AuditRecord(
        record_id=str(payload.get("record_id", "")),
        occurred_at=str(payload.get("occurred_at", "")),
        level=level, operation=operation, outcome=outcome,
        candidate_id=str(payload.get("candidate_id", "")),
        detail=str(payload.get("detail", "")),
        conditions=tuple(payload.get("conditions") or ()),
        decision=str(payload.get("decision", "")),
        selected_skill_bundle=tuple(payload.get("selected_skill_bundle") or ()),
        owner_gate_required=bool(payload.get("owner_gate_required", False)),
        execution_authority=str(payload.get("execution_authority", "NONE")),
        governance_digest=str(payload.get("governance_digest", "")))
    return record, str(payload.get("content_digest", ""))


@dataclass(slots=True)
class AuditLog:
    """Append-only audit records in the lead's own root."""

    policy: HermesLeadRootPolicy
    records: list = field(default_factory=list)
    path: pathlib.Path | None = None
    ids: set = field(default_factory=set)

    def bind_path(self, path: str | pathlib.Path) -> pathlib.Path:
        """Choose where records are written, refusing a forbidden destination before creating it."""
        target = self.policy.write_target(path, what="audit log")
        self.path = target
        return target

    def append(self, record: AuditRecord) -> tuple[AuditRecord, bool]:
        """Append, acknowledge an identical record, or refuse a conflicting identity.

        Raises:
            AuditRefused: ``record_id`` already exists with different content. The later writer does
                not win: a corrected account is appended under its own id, so the original claim and
                the correction are both readable.
        """
        for existing in self.records:
            if existing.record_id == record.record_id:
                if existing.content_digest == record.content_digest:
                    return (existing, False)
                raise AuditRefused(
                    f"CONFLICTING_RECORD_IDENTITY: audit record {record.record_id!r} already exists "
                    f"with digest {existing.content_digest[:16]}... and this one is "
                    f"{record.content_digest[:16]}.... Append a correction under its own id")
        self.records.append(record)
        self.ids.add(record.record_id)
        if self.path is not None:
            try:
                self._flush()
            except BaseException:
                self.records.pop()
                self.ids.discard(record.record_id)
                raise
        return (record, True)

    def _flush(self) -> None:
        assert self.path is not None
        target = self.policy.write_target(self.path, what="audit log")
        self.path = target
        target.parent.mkdir(parents=True, exist_ok=True)
        lines = b"\n".join(encode_audit_record(r) for r in self.records) + b"\n"
        staging = target.with_name(target.name + ".partial")
        staging.write_bytes(lines)
        staging.replace(target)


def load_audit_log(path: str | pathlib.Path, policy: HermesLeadRootPolicy) -> AuditLog:
    """Read an audit log, verifying every recorded digest.

    Raises:
        AuditRefused: A line is unreadable, mis-versioned, or digest-mismatched. An audit log that
            has been edited by hand is not an audit log, and reading the part that still verifies
            would be deciding that the edited part did not matter.
    """
    target = policy.write_target(path, what="audit log")
    log = AuditLog(policy=policy, path=target)
    if not target.exists():
        return log
    for number, raw in enumerate(target.read_bytes().splitlines(), start=1):
        if not raw.strip():
            continue
        record, claimed = decode_audit_record(raw)
        if claimed != record.content_digest:
            raise AuditRefused(
                f"AUDIT_DIGEST_MISMATCH: line {number} of {str(target)!r} claims {claimed[:16]}... "
                f"and its content hashes to {record.content_digest[:16]}...")
        log.records.append(record)
        log.ids.add(record.record_id)
    return log
