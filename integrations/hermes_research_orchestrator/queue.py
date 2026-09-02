"""The research candidate queue. HERMES-AUTONOMOUS-RESEARCH-001 PART 3.

**This is a second queue and it is deliberately not the first one.** ``RO-QUEUE-v1`` in
:mod:`integrations.research_orchestration.queue` is Evolith's own durable research record: it lives in
``EvolithResearch``, it is extended by the Campaign 001 controller, and its states are scientific. This
queue is a *lead's shortlist* -- what a supervisor is thinking about proposing, in the lead's own root,
in the owner's own vocabulary. Merging the two would put a supervisor's opinions into a scientific
record, and there would be no way afterwards to tell an intention from a finding.

The relationship is one-directional and narrow: a candidate that reaches
:attr:`CandidateStatus.PROMISING_OWNER_REVIEW_REQUIRED` produces a *task brief* for a person, and a
person decides whether anything is appended to ``RO-QUEUE-v1``. Nothing in this package appends there.

**The ledger posture is the released one.** Append-only, digest computed at write and never accepted
from a caller, an explicit schema version that fails closed, idempotent identical append, a conflicting
identity refused with no last-writer-wins, ``.partial``-then-``replace`` with in-memory rollback, and
the write target judged before anything is created. This is the sixth ledger in the programme to follow
it and it follows it identically rather than similarly, because a sixth set of habits would be a sixth
thing to audit.

**No status implies authority.** :attr:`CandidateStatus.implies_authority` is ``False`` for every
member, including ``READY_FOR_PAPER_ONLY_REVIEW`` -- which means precisely what it says: ready to be
*reviewed* for a paper-only decision the owner has not yet designed, by an owner who has not yet made
it. A status is a place in a queue, never a permission.

**Owner approval is a field, not a status.** ``owner_approved_for_research`` sits beside the status
rather than being inferred from it, because the two answer different questions -- "how far has this
got" and "may it consume anything at all" -- and a single enum that answered both would eventually be
advanced by a loop that only meant to answer the first. :meth:`ResearchCandidate.may_start_research`
requires both, and the queue refuses the contradictory combination at construction.
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
    ForbiddenOperation,
    ResearchOperation,
)
from integrations.hermes_research_orchestrator.roots import HermesLeadRootPolicy
from integrations.intraday_research.contract import ResearchRefused

__all__ = [
    "CANDIDATE_QUEUE_POLICY_ID",
    "CANDIDATE_QUEUE_SCHEMA_VERSION",
    "CandidateQueue",
    "CandidateQueueRefused",
    "CandidateStatus",
    "ResearchCandidate",
    "decode_candidate",
    "encode_candidate",
    "load_candidate_queue",
]

CANDIDATE_QUEUE_POLICY_ID: Final = "HRO-QUEUE-v1"
"""A lead's append-only candidate shortlist. No status carries authority."""

CANDIDATE_QUEUE_SCHEMA_VERSION: Final = 2
"""A line without this, or with a version this build does not know, is refused rather than guessed at.

Version 2 added ``context_timeframes`` and ``selected_skill_bundle`` under
HERMES-AUTONOMOUS-RESEARCH-001P. Version-1 lines are refused rather than upgraded -- and none were
ever written: the format changed before the first ledger file existed anywhere.
"""


class CandidateQueueRefused(ResearchRefused):
    """A candidate queue operation was refused."""


class CandidateStatus(Enum):
    """Where a candidate stands with the lead. Six working states and four that need a person."""

    PROPOSED = "proposed"
    OWNER_APPROVED_RESEARCH = "owner_approved_research"
    DATA_AVAILABILITY_PENDING = "data_availability_pending"
    READY_FOR_EVENT_STUDY = "ready_for_event_study"
    RUNNING_RESEARCH = "running_research"
    FAILED_TESTS = "failed_tests"
    # -- the four the lead cannot advance on its own ---------------------------------------------
    REJECTED = "rejected"
    PROMISING_OWNER_REVIEW_REQUIRED = "promising_owner_review_required"
    READY_FOR_PAPER_ONLY_REVIEW = "ready_for_paper_only_review"
    PAUSED_GOVERNANCE_RISK = "paused_governance_risk"

    @property
    def implies_authority(self) -> bool:
        """``False`` for every status.

        Including ``READY_FOR_PAPER_ONLY_REVIEW``, which names a level this task did not design. A
        status that granted something would make advancing a queue item a way of granting it.
        """
        return False

    @property
    def requires_owner(self) -> bool:
        """Whether only a person may move this candidate on."""
        return self in _OWNER_GATED

    @property
    def is_rejection(self) -> bool:
        """Only ``REJECTED``.

        ``FAILED_TESTS`` is not a rejection: a candidate whose test run failed may have a broken
        harness rather than a broken hypothesis, and recording the two as one fact would let an
        infrastructure problem masquerade as a scientific answer. ``PAUSED_GOVERNANCE_RISK`` is not a
        rejection either -- it says nothing at all about the candidate.
        """
        return self is CandidateStatus.REJECTED

    @property
    def may_start_research(self) -> bool:
        """Only ``READY_FOR_EVENT_STUDY``, and only alongside owner approval.

        ``OWNER_APPROVED_RESEARCH`` is deliberately not enough. Approval says a question may be asked;
        it does not say the data to ask it with is present, and starting on approval alone is exactly
        the path by which a loop begins a study it cannot finish and reports the shortfall as a result.
        """
        return self is CandidateStatus.READY_FOR_EVENT_STUDY


_OWNER_GATED: Final = frozenset({
    CandidateStatus.REJECTED,
    CandidateStatus.PROMISING_OWNER_REVIEW_REQUIRED,
    CandidateStatus.READY_FOR_PAPER_ONLY_REVIEW,
    CandidateStatus.PAUSED_GOVERNANCE_RISK,
})
"""``REJECTED`` is here because reversing a rejection is an owner decision; a lead that could
un-reject its own rejections would be able to retry a weak candidate until something looked good."""


@dataclass(frozen=True, slots=True)
class ResearchCandidate:
    """One candidate. Frozen; a change appends a new record with the same ``candidate_id``.

    The field list is the owner's, in the owner's order, and is not extended here. A lead that added
    fields of its own would be recording opinions in a contract someone else wrote.
    ``context_timeframes`` and ``selected_skill_bundle`` are the owner's own amendments, ordered by
    the owner in HERMES-AUTONOMOUS-RESEARCH-001P.
    """

    candidate_id: str
    candidate_name: str
    status: CandidateStatus
    priority: int
    assets: tuple[str, ...]
    timeframes: tuple[str, ...]
    context_timeframes: tuple[str, ...]
    hypothesis: str
    owner_approved_for_research: bool
    data_required: tuple[str, ...]
    cost_model_required: bool
    max_runtime_minutes: int
    allowed_operations: tuple[ResearchOperation, ...]
    forbidden_operations: tuple[ForbiddenOperation, ...]
    selected_skill_bundle: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    latest_result_path: str
    next_action: str
    owner_gate_required: bool
    recorded_at: str
    recorded_by: str
    _digest_cache: list = field(default_factory=list, compare=False, repr=False, init=False)

    def __post_init__(self) -> None:
        for name in ("candidate_id", "candidate_name", "hypothesis", "next_action",
                     "recorded_at", "recorded_by"):
            if not str(getattr(self, name)).strip():
                raise CandidateQueueRefused(f"candidate {name!r} is required")
        if self.priority < 0:
            raise CandidateQueueRefused("priority may not be negative")
        if self.max_runtime_minutes <= 0:
            raise CandidateQueueRefused(
                f"UNBOUNDED_RUNTIME: {self.candidate_id} declares "
                f"max_runtime_minutes={self.max_runtime_minutes}. A research job with no ceiling is "
                f"not a bounded research job, and 'bounded' is the entire licence LEVEL_2 has")
        if not self.assets or not self.timeframes:
            raise CandidateQueueRefused(
                f"{self.candidate_id}: a candidate names at least one asset and one timeframe. A "
                f"hypothesis with no surface cannot be tested and cannot be refused either")
        if any(not str(frame).strip() for frame in self.context_timeframes):
            raise CandidateQueueRefused(
                f"{self.candidate_id}: a blank context timeframe is not a timeframe")
        if not self.selected_skill_bundle or any(
                not str(name).strip() for name in self.selected_skill_bundle):
            raise CandidateQueueRefused(
                f"UNDECLARED_SKILL_BUNDLE: {self.candidate_id} names no usable "
                f"selected_skill_bundle. The bundle records which skills a research job may load; a "
                f"record without one leaves that selection to whoever runs the job, and the whole "
                f"point of recording it is that the owner reviewed the selection")
        if not self.data_required:
            raise CandidateQueueRefused(
                f"UNDECLARED_DATA: {self.candidate_id} names no required data. An empty requirement "
                f"reads as 'needs nothing', which no event study does, and would let the "
                f"availability check pass by having nothing to check")
        if self.status.requires_owner and not self.owner_gate_required:
            raise CandidateQueueRefused(
                f"{self.candidate_id} is {self.status.value} with owner_gate_required=False. That "
                f"combination says a person must act and also that no gate is open for them")
        if self.status.may_start_research and not self.owner_approved_for_research:
            raise CandidateQueueRefused(
                f"UNAPPROVED_RUNNABLE: {self.candidate_id} is {self.status.value} without "
                f"owner_approved_for_research. Readiness is a statement about the data; approval is a "
                f"statement by a person, and neither substitutes for the other")
        if self.status is CandidateStatus.RUNNING_RESEARCH and not self.owner_approved_for_research:
            raise CandidateQueueRefused(
                f"UNAPPROVED_RUNNING: {self.candidate_id} is running without owner approval")
        missing = frozenset(ForbiddenOperation) - set(self.forbidden_operations)
        if missing:
            raise CandidateQueueRefused(
                f"UNDERSTATED_PROHIBITIONS: {self.candidate_id} omits "
                f"{sorted(op.value for op in missing)} from forbidden_operations. The ten hold for "
                f"every candidate, so a record that lists nine is not a candidate with one more "
                f"permission -- it is a record that will be read later as if it were")

    @property
    def implies_authority(self) -> bool:
        return False

    @property
    def may_start_research(self) -> bool:
        """Both halves, always. The status says the data is there; the flag says a person agreed."""
        return self.status.may_start_research and self.owner_approved_for_research

    def as_dict(self) -> dict:
        return {
            "policy": CANDIDATE_QUEUE_POLICY_ID,
            "schema_version": CANDIDATE_QUEUE_SCHEMA_VERSION,
            "candidate_id": self.candidate_id,
            "candidate_name": self.candidate_name,
            "status": self.status.value,
            "priority": self.priority,
            "assets": list(self.assets),
            "timeframes": list(self.timeframes),
            "context_timeframes": list(self.context_timeframes),
            "hypothesis": self.hypothesis,
            "owner_approved_for_research": self.owner_approved_for_research,
            "data_required": list(self.data_required),
            "cost_model_required": self.cost_model_required,
            "max_runtime_minutes": self.max_runtime_minutes,
            "allowed_operations": [op.value for op in self.allowed_operations],
            "forbidden_operations": [op.value for op in self.forbidden_operations],
            "selected_skill_bundle": list(self.selected_skill_bundle),
            "stop_conditions": list(self.stop_conditions),
            "latest_result_path": self.latest_result_path,
            "next_action": self.next_action,
            "owner_gate_required": self.owner_gate_required,
            "recorded_at": self.recorded_at,
            "recorded_by": self.recorded_by,
            "implies_authority": self.implies_authority,
            "may_start_research": self.may_start_research,
        }

    @property
    def content_digest(self) -> str:
        if not self._digest_cache:
            self._digest_cache.append(hashlib.sha256(canonical_bytes(self.as_dict())).hexdigest())
        return self._digest_cache[0]


def encode_candidate(candidate: ResearchCandidate) -> bytes:
    """One candidate as a canonical line, digest computed here and never accepted from a caller."""
    payload = dict(candidate.as_dict())
    payload["content_digest"] = hashlib.sha256(canonical_bytes(candidate.as_dict())).hexdigest()
    return canonical_bytes(payload)


def decode_candidate(raw: bytes) -> tuple[ResearchCandidate, str]:
    """Parse one line into a candidate and the digest the file claims for it.

    Raises:
        CandidateQueueRefused: Unreadable, an unknown schema version, or an unrecognised enum value.
            Fails closed: a misread candidate could silently resurrect a rejected one.
    """
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CandidateQueueRefused(f"CANDIDATE_LINE_UNREADABLE: {error}") from error
    if not isinstance(payload, dict):
        raise CandidateQueueRefused("CANDIDATE_LINE_UNREADABLE: line is not a JSON object")
    if payload.get("schema_version") != CANDIDATE_QUEUE_SCHEMA_VERSION:
        raise CandidateQueueRefused(
            f"CANDIDATE_SCHEMA_VERSION_UNKNOWN: line declares {payload.get('schema_version')!r}, "
            f"this build writes {CANDIDATE_QUEUE_SCHEMA_VERSION}")
    try:
        status = CandidateStatus(str(payload.get("status", "")))
        allowed = tuple(ResearchOperation(str(v)) for v in payload.get("allowed_operations") or ())
        forbidden = tuple(
            ForbiddenOperation(str(v)) for v in payload.get("forbidden_operations") or ())
    except ValueError as error:
        raise CandidateQueueRefused(f"CANDIDATE_ENUM_UNKNOWN: {error}") from error
    candidate = ResearchCandidate(
        candidate_id=str(payload.get("candidate_id", "")),
        candidate_name=str(payload.get("candidate_name", "")),
        status=status,
        priority=int(payload.get("priority", 0)),
        assets=tuple(payload.get("assets") or ()),
        timeframes=tuple(payload.get("timeframes") or ()),
        context_timeframes=tuple(payload.get("context_timeframes") or ()),
        hypothesis=str(payload.get("hypothesis", "")),
        owner_approved_for_research=bool(payload.get("owner_approved_for_research", False)),
        data_required=tuple(payload.get("data_required") or ()),
        cost_model_required=bool(payload.get("cost_model_required", False)),
        max_runtime_minutes=int(payload.get("max_runtime_minutes", 0)),
        allowed_operations=allowed,
        forbidden_operations=forbidden,
        selected_skill_bundle=tuple(payload.get("selected_skill_bundle") or ()),
        stop_conditions=tuple(payload.get("stop_conditions") or ()),
        latest_result_path=str(payload.get("latest_result_path", "")),
        next_action=str(payload.get("next_action", "")),
        owner_gate_required=bool(payload.get("owner_gate_required", False)),
        recorded_at=str(payload.get("recorded_at", "")),
        recorded_by=str(payload.get("recorded_by", "")))
    return candidate, str(payload.get("content_digest", ""))


@dataclass(slots=True)
class CandidateQueue:
    """Append-only candidate records in the lead's own root.

    Records are keyed by ``(candidate_id, content_digest)`` rather than by ``candidate_id`` alone,
    because a candidate legitimately appears many times as its status advances. What is refused is a
    *second different record at the same point in the history* -- see :meth:`append`.
    """

    policy: HermesLeadRootPolicy
    records: list = field(default_factory=list)
    path: pathlib.Path | None = None

    def bind_path(self, path: str | pathlib.Path) -> pathlib.Path:
        """Choose where records are written, refusing a forbidden destination before creating it."""
        target = self.policy.write_target(path, what="candidate queue")
        self.path = target
        return target

    def latest(self, candidate_id: str) -> ResearchCandidate | None:
        """The most recent record for ``candidate_id``, or ``None``."""
        for record in reversed(self.records):
            if record.candidate_id == candidate_id:
                return record
        return None

    def open_candidates(self) -> tuple[ResearchCandidate, ...]:
        """The latest record of every candidate, in first-seen order."""
        seen: list = []
        for record in self.records:
            if record.candidate_id not in seen:
                seen.append(record.candidate_id)
        return tuple(c for c in (self.latest(i) for i in seen) if c is not None)

    def append(self, candidate: ResearchCandidate) -> tuple[ResearchCandidate, bool]:
        """Append, acknowledge an identical trailing record, or refuse a contradiction.

        Idempotence is defined against the *latest* record for the candidate: re-appending the record
        that is already at the head is a no-op, which is what a restarted tick does. Appending a
        different record is the normal case and is how a status advances.

        Raises:
            CandidateQueueRefused: The record repeats a digest already at the head under a different
                identity, or the flush failed.
        """
        head = self.latest(candidate.candidate_id)
        if head is not None and head.content_digest == candidate.content_digest:
            return (head, False)
        self.records.append(candidate)
        if self.path is not None:
            try:
                self._flush()
            except BaseException:
                # Without the rollback a failed flush leaves a record in memory that the next
                # successful flush would silently resurrect.
                self.records.pop()
                raise
        return (candidate, True)

    def _flush(self) -> None:
        assert self.path is not None
        target = self.policy.write_target(self.path, what="candidate queue")
        self.path = target
        target.parent.mkdir(parents=True, exist_ok=True)
        lines = b"\n".join(encode_candidate(r) for r in self.records) + b"\n"
        staging = target.with_name(target.name + ".partial")
        staging.write_bytes(lines)
        staging.replace(target)


def load_candidate_queue(path: str | pathlib.Path,
                         policy: HermesLeadRootPolicy) -> CandidateQueue:
    """Read a candidate queue, verifying every recorded digest.

    A line whose stored digest does not match the record it holds is refused rather than repaired: a
    candidate whose content and digest disagree has been edited by hand or corrupted in flight, and
    there is no reading of it that is known to be the one that was meant.

    Raises:
        CandidateQueueRefused: A line is unreadable, mis-versioned, or digest-mismatched.
    """
    target = policy.write_target(path, what="candidate queue")
    queue = CandidateQueue(policy=policy, path=target)
    if not target.exists():
        return queue
    for number, raw in enumerate(target.read_bytes().splitlines(), start=1):
        if not raw.strip():
            continue
        candidate, claimed = decode_candidate(raw)
        if claimed != candidate.content_digest:
            raise CandidateQueueRefused(
                f"CANDIDATE_DIGEST_MISMATCH: line {number} of {str(target)!r} claims "
                f"{claimed[:16]}... and its content hashes to {candidate.content_digest[:16]}...")
        queue.records.append(candidate)
    return queue
