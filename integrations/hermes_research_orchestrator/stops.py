"""Why the lead stops, and what stopping means. HERMES-AUTONOMOUS-RESEARCH-001 PART 4.

**Every stop condition pauses. None of them skips, retries or degrades.** That is the single most
important property in this package and it is why :class:`StopAction` has two members rather than four.
A supervisor with a "continue with a warning" branch will eventually take it at three in the morning
against a dirty working tree, and the resulting research will be attributed to a commit that was never
what was running. There is no such branch here.

**Thirteen conditions, and the distinctions between them are the point.** "The data is missing" and "the
cost model is missing" are both refusals to start, but only the first is a statement about the market
data and only the second can be fixed without waiting for a feed. "Tests are failing" and "another
terminal is editing overlapping files" both mean the repository is not in a state to research against,
but the first is a defect and the second is a person at work. Collapsing them would give the owner a
pause reason that could not be acted on.

**A pause is recorded and then held, not recorded and then re-evaluated in a tight loop.**
:class:`StopDecision` carries the condition, the evidence and the moment; what it does not carry is a
retry count, because a counter would make "how many times have we tried" a thing the loop could grow
out of. The lead pauses until the next scheduled poll finds the condition gone, and the audit log
shows one record per poll rather than one per attempt.

**The preflight is pure.** :func:`evaluate_preflight` takes a description of the environment and
returns a decision; it reads no filesystem, runs no subprocess and asks no clock. The process that
gathers ``git status``, the test result and the lock state owns the operating system, and this module
owns only the judgement -- which is what lets every one of the thirteen be tested without a machine, a
repository or a failing test suite to hand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Final

from integrations.hermes_research_orchestrator.levels import (
    AutomationLevel,
    ResearchOperation,
)
from integrations.intraday_research.contract import ResearchRefused

__all__ = [
    "STOP_POLICY_ID",
    "PreflightEnvironment",
    "StopAction",
    "StopCondition",
    "StopDecision",
    "StopRefused",
    "evaluate_preflight",
]

STOP_POLICY_ID: Final = "HRO-STOP-v1"
"""Thirteen conditions, all of which pause. None of which degrades."""


class StopRefused(ResearchRefused):
    """A stop decision was constructed inconsistently."""


class StopAction(Enum):
    """What the lead does about a condition. Two members, and that is deliberate."""

    PROCEED = "proceed"
    PAUSE = "pause"

    @property
    def may_start_work(self) -> bool:
        return self is StopAction.PROCEED


class StopCondition(Enum):
    """Why the lead is not starting anything. Every member pauses."""

    LEVEL_NOT_AUTHORISED = "level_not_authorised"
    OWNER_APPROVAL_ABSENT = "owner_approval_absent"
    CANDIDATE_NOT_READY = "candidate_not_ready"
    GIT_DIRTY_IN_PROTECTED_PATH = "git_dirty_in_protected_path"
    OVERLAPPING_EDIT_IN_ANOTHER_TERMINAL = "overlapping_edit_in_another_terminal"
    TESTS_FAILING = "tests_failing"
    REQUIRED_DATA_MISSING = "required_data_missing"
    COST_MODEL_MISSING = "cost_model_missing"
    MAX_CONCURRENT_JOBS_REACHED = "max_concurrent_jobs_reached"
    RUNTIME_BUDGET_EXCEEDED = "runtime_budget_exceeded"
    CONFLICTING_LOCK_HELD = "conflicting_lock_held"
    AUDIT_LOG_UNWRITABLE = "audit_log_unwritable"
    GOVERNANCE_RISK = "governance_risk"

    @property
    def action(self) -> StopAction:
        """``PAUSE``, for every member. There is no condition here that a loop may work around."""
        return StopAction.PAUSE

    @property
    def is_about_the_repository(self) -> bool:
        """Whether clearing this needs the repository tidied rather than the world to change."""
        return self in _REPOSITORY_CONDITIONS

    @property
    def is_about_the_candidate(self) -> bool:
        """Whether clearing this needs something about this candidate specifically."""
        return self in _CANDIDATE_CONDITIONS

    @property
    def blocks_the_whole_lead(self) -> bool:
        """Whether the lead stops entirely rather than skipping one candidate.

        A dirty repository, a failing suite, an unwritable audit log or a governance risk are
        properties of the whole environment: moving to the next candidate would run the same work
        against the same broken world and record it as if the world were fine.
        """
        return self in _GLOBAL_CONDITIONS


_REPOSITORY_CONDITIONS: Final = frozenset({
    StopCondition.GIT_DIRTY_IN_PROTECTED_PATH,
    StopCondition.OVERLAPPING_EDIT_IN_ANOTHER_TERMINAL,
    StopCondition.TESTS_FAILING,
})

_CANDIDATE_CONDITIONS: Final = frozenset({
    StopCondition.OWNER_APPROVAL_ABSENT,
    StopCondition.CANDIDATE_NOT_READY,
    StopCondition.REQUIRED_DATA_MISSING,
    StopCondition.COST_MODEL_MISSING,
    StopCondition.RUNTIME_BUDGET_EXCEEDED,
})

_GLOBAL_CONDITIONS: Final = frozenset(
    _REPOSITORY_CONDITIONS | {
        StopCondition.LEVEL_NOT_AUTHORISED,
        StopCondition.AUDIT_LOG_UNWRITABLE,
        StopCondition.GOVERNANCE_RISK,
        StopCondition.CONFLICTING_LOCK_HELD,
    })
"""``MAX_CONCURRENT_JOBS_REACHED`` is not global: the lead is healthy and simply full, and the right
response is to wait for a slot rather than to stop supervising."""


@dataclass(frozen=True, slots=True)
class PreflightEnvironment:
    """What the calling process observed. Supplied, never gathered here.

    Attributes:
        level: The automation level the lead is running at.
        candidate_is_owner_approved: The candidate's ``owner_approved_for_research`` field.
        candidate_is_ready: Whether the candidate's status permits starting research.
        required_data_present: Whether every entry in ``data_required`` was found.
        cost_model_present: Whether a cost model was found, when the candidate requires one.
        cost_model_required: The candidate's ``cost_model_required`` field.
        git_dirty_protected_paths: Protected paths reported dirty by ``git status``. Empty is clean.
        overlapping_paths: Paths another terminal or agent is known to be editing.
        tests_passing: Whether the declared test selection passed on this working tree.
        running_jobs: How many research jobs the lead already has in flight.
        max_concurrent_jobs: The ceiling for that number.
        elapsed_minutes: Minutes already spent on this candidate.
        max_runtime_minutes: The candidate's declared ceiling.
        audit_log_writable: Whether the audit log target was resolved and is writable.
        conflicting_lock_holder: A description of a lock another runtime holds, or empty.
        native_gateway_running: Whether a native chat-gateway process was observed running
            (HERMES-AUTONOMOUS-RESEARCH-001P). The gateway fronts an agent that holds a shell under
            the unhardened root profile, and it has started itself once already; a lead operating
            beside it is a governance risk, never a neutral fact. The HERMES-002 runner gathers this
            observation -- nothing in this package looks.
        gateway_port_open: Whether the gateway's port (8644) was observed listening. Reported
            separately from the process check because the port can be reachable when the process
            observation is wrong, and either alone is reason to pause.
        governance_risk: A description of a governance risk the caller identified, or empty.
    """

    level: AutomationLevel
    candidate_is_owner_approved: bool
    candidate_is_ready: bool
    required_data_present: bool
    cost_model_present: bool
    cost_model_required: bool
    tests_passing: bool
    audit_log_writable: bool
    running_jobs: int = 0
    max_concurrent_jobs: int = 1
    elapsed_minutes: int = 0
    max_runtime_minutes: int = 0
    git_dirty_protected_paths: tuple[str, ...] = ()
    overlapping_paths: tuple[str, ...] = ()
    conflicting_lock_holder: str = ""
    native_gateway_running: bool = False
    gateway_port_open: bool = False
    governance_risk: str = ""

    def __post_init__(self) -> None:
        if self.max_concurrent_jobs < 1:
            raise StopRefused("max_concurrent_jobs is at least 1")
        if self.running_jobs < 0 or self.elapsed_minutes < 0 or self.max_runtime_minutes < 0:
            raise StopRefused("counts and durations may not be negative")


@dataclass(frozen=True, slots=True)
class StopDecision:
    """The preflight answer. Carries no retry count, by design.

    Attributes:
        action: ``PROCEED`` or ``PAUSE``.
        conditions: Every condition that fired, in evaluation order. All of them, not the first --
            an owner fixing one at a time against a decision that reported one at a time would
            discover the next only after another poll.
        evidence: Human-readable evidence per condition, for the audit log and the daily report.
        operation: What the lead intended to do. Recorded so a pause says what was prevented.
    """

    action: StopAction
    operation: ResearchOperation
    conditions: tuple[StopCondition, ...] = ()
    evidence: tuple[str, ...] = ()
    _unused: list = field(default_factory=list, compare=False, repr=False, init=False)

    def __post_init__(self) -> None:
        if self.action is StopAction.PAUSE and not self.conditions:
            raise StopRefused(
                "PAUSE_WITHOUT_CONDITION: a pause that cannot say why is the failure the twelve "
                "distinct conditions exist to prevent")
        if self.action is StopAction.PROCEED and self.conditions:
            raise StopRefused(
                f"PROCEED_WITH_CONDITION: {[c.value for c in self.conditions]} fired and the decision "
                f"is to proceed. Every condition pauses; there is no severity below which one does "
                f"not")
        if len(self.evidence) != len(self.conditions):
            raise StopRefused("every condition carries exactly one line of evidence")

    @property
    def blocks_the_whole_lead(self) -> bool:
        return any(c.blocks_the_whole_lead for c in self.conditions)

    def as_dict(self) -> dict:
        return {"policy": STOP_POLICY_ID, "action": self.action.value,
                "operation": self.operation.value,
                "conditions": [c.value for c in self.conditions],
                "evidence": list(self.evidence)}


def evaluate_preflight(environment: PreflightEnvironment,
                       operation: ResearchOperation = ResearchOperation
                       .LAUNCH_BOUNDED_RESEARCH_JOB) -> StopDecision:
    """Decide whether ``operation`` may start, given what the caller observed.

    Order matters only for readability -- every condition is evaluated and all of them are reported.
    The level check is first because it is the one an operator is most likely to have got wrong, and
    a decision that led with "the data is missing" when the real answer was "you are at LEVEL_1"
    would send them looking in the wrong place.
    """
    conditions: list = []
    evidence: list = []

    def fired(condition: StopCondition, why: str) -> None:
        conditions.append(condition)
        evidence.append(why)

    if operation not in environment.level.permitted_operations:
        fired(StopCondition.LEVEL_NOT_AUTHORISED,
              f"{operation.value} is not permitted at {environment.level.value}")
    if not environment.candidate_is_owner_approved:
        fired(StopCondition.OWNER_APPROVAL_ABSENT,
              "the candidate is not owner_approved_for_research")
    if not environment.candidate_is_ready:
        fired(StopCondition.CANDIDATE_NOT_READY,
              "the candidate's status does not permit starting research")
    if not environment.required_data_present:
        fired(StopCondition.REQUIRED_DATA_MISSING,
              "at least one entry in data_required was not found")
    if environment.cost_model_required and not environment.cost_model_present:
        fired(StopCondition.COST_MODEL_MISSING,
              "the candidate requires a cost model and none was found")
    if environment.git_dirty_protected_paths:
        fired(StopCondition.GIT_DIRTY_IN_PROTECTED_PATH,
              f"dirty: {list(environment.git_dirty_protected_paths)}")
    if environment.overlapping_paths:
        fired(StopCondition.OVERLAPPING_EDIT_IN_ANOTHER_TERMINAL,
              f"another terminal is editing: {list(environment.overlapping_paths)}")
    if not environment.tests_passing:
        fired(StopCondition.TESTS_FAILING, "the declared test selection did not pass")
    if environment.running_jobs >= environment.max_concurrent_jobs:
        fired(StopCondition.MAX_CONCURRENT_JOBS_REACHED,
              f"{environment.running_jobs} running, ceiling {environment.max_concurrent_jobs}")
    if (environment.max_runtime_minutes
            and environment.elapsed_minutes >= environment.max_runtime_minutes):
        fired(StopCondition.RUNTIME_BUDGET_EXCEEDED,
              f"{environment.elapsed_minutes} minutes spent of "
              f"{environment.max_runtime_minutes}")
    if environment.conflicting_lock_holder.strip():
        fired(StopCondition.CONFLICTING_LOCK_HELD, environment.conflicting_lock_holder.strip())
    if not environment.audit_log_writable:
        fired(StopCondition.AUDIT_LOG_UNWRITABLE,
              "the audit log target is not writable, so nothing done next could be recorded")
    # One GOVERNANCE_RISK condition, one evidence line naming every reason. Fired separately, the
    # de-duplication below would keep the first reason and silently drop the rest.
    risks = []
    if environment.native_gateway_running:
        risks.append("the native chat gateway process is running while the lead operates")
    if environment.gateway_port_open:
        risks.append("the gateway port 8644 is listening, so the gateway is reachable")
    if environment.governance_risk.strip():
        risks.append(environment.governance_risk.strip())
    if risks:
        fired(StopCondition.GOVERNANCE_RISK, "; ".join(risks))

    # De-duplicate while preserving order: one condition may be reached by two routes and an owner
    # reading two identical lines would reasonably wonder which one they had already fixed.
    seen: dict = {}
    for condition, why in zip(conditions, evidence):
        seen.setdefault(condition, why)

    if not seen:
        return StopDecision(action=StopAction.PROCEED, operation=operation)
    return StopDecision(action=StopAction.PAUSE, operation=operation,
                        conditions=tuple(seen), evidence=tuple(seen.values()))
