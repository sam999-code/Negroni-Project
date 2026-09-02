"""Five automation levels, and what each one may do. HERMES-AUTONOMOUS-RESEARCH-001 PART 2.

**The governance matrix is data, not prose.** :data:`LEVEL_OPERATIONS` is the whole of what a level
permits, and every other module asks it rather than deciding again. A second place that decided what
LEVEL_2 may do would eventually decide something different, and the two would disagree quietly.

**Two levels are named and not designed, deliberately.** LEVEL_3_PAPER_ONLY and LEVEL_4_LIMITED_LIVE
appear in this enum because the owner asked for the ladder to be visible -- an operator who cannot see
the rungs above cannot tell whether the one they are standing on is the top. Asking either of them for
its permitted operations raises :class:`LevelNotDesigned`. They are a plan, and a plan that answered
questions about its own permissions would be indistinguishable from an implementation.

**No level grants execution authority, and there is no code here that could.**
:attr:`AutomationLevel.grants_execution_authority` returns ``False`` for every member including the
two undesigned ones, and this module has no setter, no authority field and no import of the authority
vocabulary. That is the enforcement style the repository already uses for the watcher: a symbol that
was never imported cannot be called, whereas a guard can be bypassed by a second code path.

**The forbidden set does not vary by level.** :data:`FORBIDDEN_OPERATIONS` is a module constant rather
than a per-level entry, because a per-level table invites a future row that omits one. The ten
prohibitions hold at LEVEL_0 and they hold at LEVEL_4; what changes between levels is only how much of
the *permitted* set is reachable without asking the owner first.

**LEVEL_2 is designed here and activated nowhere.** :func:`active_level` reads a marker file the owner
writes by hand, defaults to LEVEL_1_SUPERVISED when it is absent, and refuses to infer LEVEL_2 from
anything else. This mirrors the ``autonomous_discovery.approved`` convention the Campaign 001
controller already answers to, which is the closest released precedent for "an unattended loop may
begin" and the reason there is no second convention here.
"""

from __future__ import annotations

import hashlib
import pathlib
from enum import Enum
from typing import Final

from evolith_core.shared.canonical_json import canonical_bytes
from integrations.intraday_research.contract import ResearchRefused

__all__ = [
    "LEVEL_POLICY_ID",
    "APPROVAL_MARKER_NAME",
    "APPROVED_DIGEST_KEY",
    "FORBIDDEN_OPERATIONS",
    "LEVEL_OPERATIONS",
    "AutomationLevel",
    "ForbiddenOperation",
    "LevelNotDesigned",
    "LevelRefused",
    "ResearchOperation",
    "active_level",
    "governance_matrix",
    "governance_matrix_digest",
    "refuse_forbidden_operation",
]

LEVEL_POLICY_ID: Final = "HRO-LEVELS-v1"
"""What each automation level permits. Frozen and digest-bound: see :func:`governance_matrix_digest`."""

APPROVAL_MARKER_NAME: Final = "hermes_autonomous_research.approved"
"""The file an owner writes by hand to raise the lead to LEVEL_2, in the lead's own root.

Named for the ``autonomous_discovery.approved`` marker the Campaign 001 controller already uses, and
placed in the lead's root rather than beside it so that revoking autonomy is deleting one file in one
known place.

Since HERMES-AUTONOMOUS-RESEARCH-001P the marker is digest-bound: it must contain a line
``approved_governance_digest: <hex>`` naming the digest of the governance matrix in force, or it is
treated as absent. Plain approval text approves nothing, because it would keep approving after the
matrix changed under it.
"""

APPROVED_DIGEST_KEY: Final = "approved_governance_digest"
"""The key the G2 marker must carry. Its value is compared to :func:`governance_matrix_digest`, so an
approval is an approval *of a specific matrix*: loosen a level and every existing marker reads as
absent until an owner looks at the new matrix and writes a new one."""


class LevelRefused(ResearchRefused):
    """An automation level was asked for something it does not permit."""


class LevelNotDesigned(LevelRefused):
    """A level that exists on the ladder but has not been designed.

    Raised rather than returning an empty permission set, because an empty set reads as "this level
    may do nothing", and the truth is "nobody has decided yet what this level may do". Those are
    different facts and only the second one is a reason to stop.
    """


class ResearchOperation(Enum):
    """The nine things a research lead may do. Nothing here consumes evidence or grants authority."""

    MAINTAIN_CANDIDATE_QUEUE = "maintain_candidate_queue"
    PREPARE_RESEARCH_TASK = "prepare_research_task"
    LAUNCH_BOUNDED_RESEARCH_JOB = "launch_bounded_research_job"
    MONITOR_JOB_STATUS = "monitor_job_status"
    COLLECT_OUTPUTS_AND_TEST_REPORTS = "collect_outputs_and_test_reports"
    WRITE_RESEARCH_SUMMARY = "write_research_summary"
    REJECT_WEAK_CANDIDATE = "reject_weak_candidate"
    ESCALATE_TO_OWNER_REVIEW = "escalate_to_owner_review"
    PREPARE_NEXT_AGENT_TASK = "prepare_next_agent_task"

    @property
    def grants_execution_authority(self) -> bool:
        """``False`` for every operation. Preparing a task is not authority to run its conclusion."""
        return False


class ForbiddenOperation(Enum):
    """The ten things a research lead may never do, at any level, in any state.

    These are governance names rather than the names of the functions that would perform them. The
    lead has no route to those functions and this package imports none of them; naming a broker call
    here in order to forbid it would put the name inside the package that must not contain it.
    """

    LIVE_SIGNAL_EMISSION = "live_signal_emission"
    SIGNAL_CONFIRMATION = "signal_confirmation"
    GRADE_ASSIGNMENT = "grade_assignment"
    TRADE_EXECUTION = "trade_execution"
    ORDER_SUBMISSION = "order_submission"
    BROKER_SURFACE_MUTATION = "broker_surface_mutation"
    CAMPAIGN_AUTHORITY_CHANGE = "campaign_authority_change"
    NEWS_DIRECTION_AS_SIGNAL = "news_direction_as_signal"
    FABRICATED_PROBABILITY = "fabricated_probability"
    CONTINUATION_AFTER_SAFETY_FAILURE = "continuation_after_safety_failure"


FORBIDDEN_OPERATIONS: Final = frozenset(ForbiddenOperation)
"""All ten, at every level. A per-level table would invite a row that omitted one."""


class AutomationLevel(Enum):
    """How much the research lead may do without asking. Five rungs; three are designed."""

    LEVEL_0_MANUAL = "level_0_manual"
    LEVEL_1_SUPERVISED = "level_1_supervised"
    LEVEL_2_AUTONOMOUS_RESEARCH = "level_2_autonomous_research"
    LEVEL_3_PAPER_ONLY = "level_3_paper_only"
    LEVEL_4_LIMITED_LIVE = "level_4_limited_live"

    @property
    def is_designed(self) -> bool:
        """Whether this task designed the level. LEVEL_3 and LEVEL_4 are named and not designed."""
        return self in _DESIGNED

    @property
    def grants_execution_authority(self) -> bool:
        """``False`` for every level, including the two that are not designed.

        LEVEL_4_LIMITED_LIVE will one day sit beside an execution capability; it will not *be* one.
        Authority is granted by the released execution architecture and by nothing in this package,
        so the answer here is ``False`` now and stays ``False`` however the ladder grows.
        """
        return False

    @property
    def may_launch_without_asking(self) -> bool:
        """Only LEVEL_2. LEVEL_1 may queue a job and must put it in front of the owner first."""
        return self is AutomationLevel.LEVEL_2_AUTONOMOUS_RESEARCH

    @property
    def permitted_operations(self) -> frozenset:
        """What this level may do.

        Raises:
            LevelNotDesigned: The level is on the ladder but has not been designed.
        """
        if not self.is_designed:
            raise LevelNotDesigned(
                f"LEVEL_NOT_DESIGNED: {self.value} is named on the ladder so the rungs above are "
                f"visible, and HERMES-AUTONOMOUS-RESEARCH-001 designed up to "
                f"{AutomationLevel.LEVEL_2_AUTONOMOUS_RESEARCH.value} only. It has no permissions "
                f"yet -- which is not the same as having none")
        return LEVEL_OPERATIONS[self]


_DESIGNED: Final = frozenset({
    AutomationLevel.LEVEL_0_MANUAL,
    AutomationLevel.LEVEL_1_SUPERVISED,
    AutomationLevel.LEVEL_2_AUTONOMOUS_RESEARCH,
})

_LEVEL_0_OPERATIONS: Final = frozenset({
    ResearchOperation.MAINTAIN_CANDIDATE_QUEUE,
    ResearchOperation.PREPARE_RESEARCH_TASK,
    ResearchOperation.PREPARE_NEXT_AGENT_TASK,
})
"""LEVEL_0 prepares and does nothing else. It does not even read a job's status, because at LEVEL_0
there is no job the lead started to read the status of."""

_LEVEL_1_OPERATIONS: Final = _LEVEL_0_OPERATIONS | frozenset({
    ResearchOperation.MONITOR_JOB_STATUS,
    ResearchOperation.COLLECT_OUTPUTS_AND_TEST_REPORTS,
    ResearchOperation.WRITE_RESEARCH_SUMMARY,
    ResearchOperation.REJECT_WEAK_CANDIDATE,
    ResearchOperation.ESCALATE_TO_OWNER_REVIEW,
})
"""LEVEL_1 does everything except start a job. Rejecting and escalating are both here: neither
consumes evidence, and a supervised lead that could not reject a weak candidate would hand the owner
a queue instead of a shortlist, which is the work it exists to do."""

LEVEL_OPERATIONS: Final[dict] = {
    AutomationLevel.LEVEL_0_MANUAL: _LEVEL_0_OPERATIONS,
    AutomationLevel.LEVEL_1_SUPERVISED: _LEVEL_1_OPERATIONS,
    AutomationLevel.LEVEL_2_AUTONOMOUS_RESEARCH:
        _LEVEL_1_OPERATIONS | frozenset({ResearchOperation.LAUNCH_BOUNDED_RESEARCH_JOB}),
}
"""The governance matrix. LEVEL_2 adds exactly one operation to LEVEL_1, and that is the entire
difference between supervised and autonomous: who presses start."""


def governance_matrix() -> dict:
    """The matrix as a plain document, for a report, a digest, or an owner to read."""
    return {
        "policy": LEVEL_POLICY_ID,
        "levels": {
            level.value: {
                "designed": level.is_designed,
                "grants_execution_authority": level.grants_execution_authority,
                "may_launch_without_asking": level.may_launch_without_asking,
                "permitted_operations": sorted(op.value for op in LEVEL_OPERATIONS[level])
                if level.is_designed else None,
            }
            for level in AutomationLevel
        },
        "forbidden_operations": sorted(op.value for op in FORBIDDEN_OPERATIONS),
    }


def governance_matrix_digest() -> str:
    """SHA-256 of the matrix.

    Bound into every audit record and every daily report, so a lead cannot silently run under looser
    rules than the ones it published. Changing what a level may do changes this digest, which changes
    what the audit log says the lead was operating under -- the same discipline the frozen transition
    policy in ``RO-GATES-v1`` uses, and for the same reason.
    """
    return hashlib.sha256(canonical_bytes(governance_matrix())).hexdigest()


def active_level(lead_root: str | pathlib.Path,
                 *, ceiling: AutomationLevel = AutomationLevel.LEVEL_2_AUTONOMOUS_RESEARCH
                 ) -> AutomationLevel:
    """The level the lead is actually running at, read from the owner's marker file.

    Absent marker means LEVEL_1_SUPERVISED. That default is the interesting decision: the safe default
    is not LEVEL_0, because a lead that could not even read a job's status would be useless the moment
    the marker was deleted, and an operator who deletes a marker wants the loop to *stop starting
    things*, not to go blind. LEVEL_1 is the strongest level that starts nothing.

    An unreadable or empty marker is treated as absent rather than as approval, and no marker is ever
    written by this function. Autonomy is granted by a person creating a file, and revoked by a person
    deleting it; nothing in this package does either.

    The marker is digest-bound (HERMES-AUTONOMOUS-RESEARCH-001P). It must carry
    ``approved_governance_digest: <hex>`` matching :func:`governance_matrix_digest` for the matrix
    currently in force; a marker without the key, or naming a stale digest, is treated as absent.
    Without the binding, an approval granted under one matrix would silently survive the matrix being
    loosened -- the lead would run under looser rules than the ones the owner looked at.

    Args:
        lead_root: The directory the research lead owns.
        ceiling: The highest level this build will report however the marker reads. Defaults to
            LEVEL_2, the highest level HERMES-AUTONOMOUS-RESEARCH-001 designed.

    Raises:
        LevelNotDesigned: ``ceiling`` names a level this build has not designed.
    """
    if not ceiling.is_designed:
        raise LevelNotDesigned(
            f"LEVEL_NOT_DESIGNED: {ceiling.value} cannot be a ceiling; it has no permissions to cap")
    try:
        marker = pathlib.Path(lead_root) / APPROVAL_MARKER_NAME
        text = marker.read_text(encoding="utf-8") if marker.is_file() else ""
    except OSError:
        text = ""                  # unreadable is not approval
    if not _marker_approves_current_matrix(text):
        return AutomationLevel.LEVEL_1_SUPERVISED
    return ceiling


def _marker_approves_current_matrix(text: str) -> bool:
    """Whether marker text approves the matrix currently in force, and no other.

    Accepts ``approved_governance_digest: <hex>`` or ``approved_governance_digest = <hex>`` on any
    line. Anything else -- no such line, a blank value, a digest of some other matrix -- is not
    approval. Fail closed is the whole design: the two mistakes this function can make are unequal,
    and running autonomously under rules nobody approved is the one that cannot be taken back.
    """
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            key, separator, value = line.partition("=")
        if separator and key.strip().lower() == APPROVED_DIGEST_KEY:
            return value.strip().lower() == governance_matrix_digest()
    return False


def refuse_forbidden_operation(name: str) -> None:
    """Refuse if ``name`` is one of the ten prohibitions.

    A belt-and-braces check for a caller that builds an operation name from text -- a task brief, a
    queue field, an owner instruction. The structural guarantee is that this package imports nothing
    that could perform any of them; this function catches the case where something merely *asks*.

    Raises:
        LevelRefused: ``name`` names a forbidden operation.
    """
    try:
        forbidden = ForbiddenOperation(str(name).strip().lower())
    except ValueError:
        return
    raise LevelRefused(
        f"FORBIDDEN_OPERATION: {forbidden.value!r} is refused at every automation level and in every "
        f"candidate state. The research lead has no route to it, and asking for it is a governance "
        f"event rather than a mistake -- it is recorded and the pipeline pauses")
