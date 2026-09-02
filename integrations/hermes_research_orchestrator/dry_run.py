"""What would happen, without anything happening. HERMES-AUTONOMOUS-RESEARCH-001 PART 6.

**The validator is the whole of what this task activates.** Everything else in the package is a
schema, a policy or a writer that a future runner will call; :func:`dry_run` is the one function an
owner can usefully run today, and running it changes nothing. It opens no file, starts no job, takes
no lock and asks no clock. Given a candidate and an observed environment it answers one question --
*would this start, and if not, why not* -- and the answer is a document.

**A dry run never invents a number.** :class:`DryRunReport` has no field for an expected win rate, an
edge, a Sharpe ratio or a probability, and :data:`FABRICATION_FIELDS` lists the names it refuses to
carry so that a future field with one of those names fails a released test rather than a review. A
supervisor's report is a statement about *readiness*, and a readiness report that quoted a performance
figure would be quoting a figure nobody measured.

**The prepared brief is text for a person or a coding agent, not an instruction to a runtime.**
:attr:`DryRunReport.task_brief` is what the lead hands to Claude Code, Codex or the owner. It names
the candidate, the surface, the bounded operations and every prohibition; it contains no path into a
live evidence root and no command line. LEVEL_2 turns this brief into a *job request* written in the
lead's own root -- and a separate runner, which HERMES-AUTONOMOUS-RESEARCH-002 will build, is what
turns a job request into a running job. Two components, so that "the lead decided to research this"
and "a process started" are two records rather than one.

**Refusals are reported in full, never first-only.** The environment usually has more than one thing
wrong with it, and an owner fixing one at a time against a report that named one at a time would
discover the next only on the following poll.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from integrations.hermes_research_orchestrator.levels import (
    FORBIDDEN_OPERATIONS,
    AutomationLevel,
    ResearchOperation,
    governance_matrix_digest,
)
from integrations.hermes_research_orchestrator.queue import CandidateStatus, ResearchCandidate
from integrations.hermes_research_orchestrator.stops import (
    PreflightEnvironment,
    StopDecision,
    evaluate_preflight,
)

__all__ = [
    "DRY_RUN_POLICY_ID",
    "FABRICATION_FIELDS",
    "DryRunReport",
    "dry_run",
    "escalation_status",
    "task_brief_for",
]

DRY_RUN_POLICY_ID: Final = "HRO-DRYRUN-v1"
"""A pure readiness answer. No side effect, no performance claim."""

FABRICATION_FIELDS: Final[tuple[str, ...]] = (
    "win_rate", "expectancy", "sharpe", "sortino", "profit_factor", "edge",
    "probability", "confidence", "expected_return", "hit_rate", "accuracy",
    "backtest_result", "projected_pnl",
)
"""Names a readiness report may never carry.

Held as a constant so the prohibition is checkable by a test rather than by a reviewer noticing. The
same discipline the released ``PERFORMANCE_CLAIM_FIELDS`` applies to a research orchestrator's
records; this is the supervisor-level equivalent and it exists for the same reason -- a number in a
supervisor's report is read as a finding no matter how it was captioned.
"""


@dataclass(frozen=True, slots=True)
class DryRunReport:
    """What a launch attempt would do. A document, not an action.

    Attributes:
        candidate_id: The candidate examined.
        level: The automation level assumed.
        would_start: Whether the candidate would start under this level and environment.
        decision: The full preflight decision, including every condition that fired.
        planned_operations: The operations the lead would perform, in order, if it proceeded.
        refused_operations: Operations the candidate declared that this level does not permit.
        task_brief: The text the lead would hand to a person or a coding agent.
        governance_digest: The matrix digest in force when the report was built.
    """

    candidate_id: str
    level: AutomationLevel
    would_start: bool
    decision: StopDecision
    planned_operations: tuple[ResearchOperation, ...]
    refused_operations: tuple[ResearchOperation, ...]
    task_brief: str
    governance_digest: str

    def as_dict(self) -> dict:
        return {"policy": DRY_RUN_POLICY_ID, "candidate_id": self.candidate_id,
                "level": self.level.value, "would_start": self.would_start,
                "decision": self.decision.as_dict(),
                "planned_operations": [op.value for op in self.planned_operations],
                "refused_operations": [op.value for op in self.refused_operations],
                "task_brief": self.task_brief,
                "governance_digest": self.governance_digest,
                "implies_authority": False}


def task_brief_for(candidate: ResearchCandidate, level: AutomationLevel) -> str:
    """The handoff text for one candidate.

    Written for a reader who has not seen the queue: it names the hypothesis in full, the surface, the
    bound, and every prohibition. The prohibitions are included even though they never vary, because
    a brief that omitted them would be read by an agent that had never seen this package.
    """
    permitted = sorted(op.value for op in level.permitted_operations
                       if op in set(candidate.allowed_operations))
    lines = [
        f"CANDIDATE {candidate.candidate_id} -- {candidate.candidate_name}",
        f"status: {candidate.status.value}",
        f"owner_approved_for_research: {candidate.owner_approved_for_research}",
        f"automation level: {level.value}",
        "",
        "HYPOTHESIS",
        candidate.hypothesis,
        "",
        f"surface: {', '.join(candidate.assets)} on {', '.join(candidate.timeframes)}",
        (f"context timeframes: {', '.join(candidate.context_timeframes)}"
         if candidate.context_timeframes else "context timeframes: (none declared)"),
        "data required:",
        # One per line. Joined on a comma these read as a single run-on requirement, and a reader
        # checking availability needs to be able to tick them off one at a time.
        *(f"  - {item}" for item in candidate.data_required),
        f"cost model required: {candidate.cost_model_required}",
        f"runtime ceiling: {candidate.max_runtime_minutes} minutes",
        "",
        "SELECTED SKILL BUNDLE (research-design skills only; the router loads nothing else)",
        *(f"  - {name}" for name in candidate.selected_skill_bundle),
        "",
        "PERMITTED AT THIS LEVEL",
        *(f"  - {name}" for name in permitted or ["  (none)"]),
        "",
        "FORBIDDEN, AT EVERY LEVEL AND IN EVERY STATE",
        *(f"  - {op.value}" for op in sorted(FORBIDDEN_OPERATIONS, key=lambda o: o.value)),
        "",
        "STOP CONDITIONS",
        *(f"  - {name}" for name in candidate.stop_conditions or ["  (none declared)"]),
        "",
        f"next action: {candidate.next_action}",
        f"owner gate required: {candidate.owner_gate_required}",
        "",
        "This brief is a research instruction. It is not a signal, not a grade, and not authority to "
        "trade, confirm or emit anything. A promising result becomes an owner review, never a "
        "position.",
    ]
    return "\n".join(lines)


def dry_run(candidate: ResearchCandidate, environment: PreflightEnvironment) -> DryRunReport:
    """Answer whether ``candidate`` would start, and hand back the brief either way.

    The brief is produced even when the answer is no. An owner whose candidate is blocked on missing
    data still wants to read what would have been asked -- reviewing the question is most of the value
    of a supervised level, and withholding it until the blockers cleared would make the review happen
    at the least convenient moment.

    Raises:
        LevelNotDesigned: The environment names a level this build has not designed.
    """
    decision = evaluate_preflight(environment, ResearchOperation.LAUNCH_BOUNDED_RESEARCH_JOB)
    permitted = environment.level.permitted_operations

    declared = tuple(candidate.allowed_operations)
    planned = tuple(op for op in declared if op in permitted)
    refused = tuple(op for op in declared if op not in permitted)

    would_start = decision.action.may_start_work and candidate.may_start_research
    return DryRunReport(
        candidate_id=candidate.candidate_id,
        level=environment.level,
        would_start=would_start,
        decision=decision,
        planned_operations=planned,
        refused_operations=refused,
        task_brief=task_brief_for(candidate, environment.level),
        governance_digest=governance_matrix_digest())


def escalation_status(promising: bool) -> CandidateStatus:
    """Where a finished, promising research job sends a candidate.

    :attr:`CandidateStatus.PROMISING_OWNER_REVIEW_REQUIRED` and nothing else. There is no branch here
    that produces a signal, a grade or a paper-only decision, because a promising research result is
    an argument for a person to consider and not a conclusion the lead is entitled to draw. A result
    that is not promising goes to :attr:`CandidateStatus.REJECTED`, which is equally an owner-gated
    state -- reversing a rejection is the owner's call too.
    """
    return (CandidateStatus.PROMISING_OWNER_REVIEW_REQUIRED if promising
            else CandidateStatus.REJECTED)
