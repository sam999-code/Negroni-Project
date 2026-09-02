"""The first candidate, as proposed and no further. HERMES-AUTONOMOUS-RESEARCH-001 PART 8.

**EVOLITH-RESEARCH-CANDIDATE-001 is PROPOSED, not approved.** The task allows
``OWNER_APPROVED_RESEARCH`` *only if the owner explicitly approved research-only work* for this
candidate, and no such approval exists. The ``autonomous_discovery.approved`` marker in the research
root covers bounded Campaign 001 gene discovery -- a different programme, approved before this
candidate was written -- and reading it as approval here would be exactly the kind of inference an
unattended loop must never make. So the seed is ``PROPOSED``, ``owner_approved_for_research`` is
``False``, and :func:`volatility_normalized_session_breakout` has no parameter that would let a caller
set either. Approval is granted by a person editing the queue, and the only thing this module can
build is a proposal.

**The hypothesis is stated so that it can fail.** "Volatility-normalized session breakout" is a name,
not a hypothesis; the text below names the normalisation, the session boundary, the direction-free
claim and the control it would be measured against, because a candidate phrased loosely enough to
survive any result is not a candidate. It carries no threshold and no parameter value: choosing those
is the research, and a seed that pre-committed to them would be handing the search its answer.

**The surface is the owner's, and the owner has already corrected it once.** The original build
seeded this candidate on EURUSD; the owner rejected that substitution in
HERMES-AUTONOMOUS-RESEARCH-001P and set the surface they had asked for -- gold and the Nasdaq index,
on 15m and 1h, with 4H and 1D as context. The symbols are the broker-CFD identities ``XAUUSD`` and
``NAS100``, deliberately not the ``GC``/``NQ`` futures the owner named as aliases: the instrument
vocabulary in ``integrations/confirmation_evidence`` treats a future and a CFD as distinct
identities, and keeping them in one vocabulary is how a study of one silently becomes a claim about
the other. Both instruments carry a daily session break -- the C08 lesson -- which is why the session
calendar sits in ``data_required`` as its own line rather than inside the bars line.

**Nothing here claims the idea is good.** Session breakouts are among the most heavily mined patterns
in retail literature and the prior should be that the effect is already priced or is an artifact of
the session definition. The candidate is written to be *tested*, and its most likely honest outcome is
``REJECTED``. That expectation belongs in the record at proposal time, not discovered afterwards.
"""

from __future__ import annotations

from typing import Final

from integrations.hermes_research_orchestrator.levels import ForbiddenOperation, ResearchOperation
from integrations.hermes_research_orchestrator.queue import CandidateStatus, ResearchCandidate

__all__ = [
    "CANDIDATE_001_ID",
    "CANDIDATE_001_HYPOTHESIS",
    "CANDIDATE_001_SKILL_BUNDLE",
    "volatility_normalized_session_breakout",
]

CANDIDATE_001_ID: Final = "EVOLITH-RESEARCH-CANDIDATE-001"

CANDIDATE_001_SKILL_BUNDLE: Final[tuple[str, ...]] = (
    "quant/statistical-reasoning",
    "quant/forward-return-analysis",
    "quant/backtesting-validation",
    "quant/rejection-discipline",
    "quant/risk-expectancy",
    "quant/time-series-market-structure",
    "evolith/candidate-mechanism-evaluation",
    "evolith/source-review-evidence-lineage",
    "evolith/governance-authority-boundaries",
)
"""Research-design skills only, selected by the owner in HERMES-AUTONOMOUS-RESEARCH-001P. Nothing
here executes, alerts or grades, and the field-name sweep in the safety tests refuses a record that
tried to carry a skill field shaped like one."""

CANDIDATE_001_HYPOTHESIS: Final = (
    "Within a fixed window after a session open, the distribution of the first range expansion "
    "beyond a volatility-normalized band differs from the distribution of an equivalent expansion "
    "sampled at matched non-session-open times on the same instrument. The normalisation is by a "
    "trailing realised-range statistic computed only from bars closed before the window begins, so "
    "the band is knowable at the moment it is used. The claim is direction-free: it is about whether "
    "an expansion at the session boundary is distinguishable at all, not about which way it goes. "
    "It is measured against a matched-time control on the same instrument and the same period, and "
    "it is refuted if the session-open sample is indistinguishable from that control under the "
    "declared cost model. No threshold, lookback or window length is fixed here; choosing them is "
    "the research, and a candidate that named them would be answering its own question."
)
"""Direction-free, control-anchored, refutable, and free of any parameter value."""

_STOP_CONDITIONS: Final[tuple[str, ...]] = (
    "git_dirty_in_protected_path",
    "overlapping_edit_in_another_terminal",
    "tests_failing",
    "required_data_missing",
    "cost_model_missing",
    "runtime_budget_exceeded",
    "governance_risk",
)
"""The candidate's own declared stops, a subset of ``HRO-STOP-v1``. The lead-wide conditions --
``level_not_authorised``, ``audit_log_unwritable``, ``conflicting_lock_held`` -- are not repeated here
because they are not properties of this candidate and listing them per-candidate would suggest a
candidate could opt out of one."""


def volatility_normalized_session_breakout() -> ResearchCandidate:
    """The first candidate, as a ``PROPOSED`` record with no owner approval.

    Takes no arguments on purpose. A ``status`` or ``approved`` parameter would make it possible to
    construct an approved candidate by calling a function, and approval is a person's act.

    Args:
        None.

    Returns:
        The proposal. ``recorded_at`` is a fixed proposal timestamp rather than a clock reading, so
        the record is reproducible and this module needs no clock.
    """
    return ResearchCandidate(
        candidate_id=CANDIDATE_001_ID,
        candidate_name="Volatility-normalized session breakout",
        status=CandidateStatus.PROPOSED,
        priority=0,
        assets=("XAUUSD", "NAS100"),
        timeframes=("15m", "1h"),
        context_timeframes=("4H", "1D"),
        hypothesis=CANDIDATE_001_HYPOTHESIS,
        owner_approved_for_research=False,
        data_required=(
            "intraday bars for each declared instrument, on every execution and context timeframe, "
            "from a governed research source",
            "a session calendar for each instrument, with its daily break stated explicitly",
            "matched-time control windows drawn from the same instrument and period",
        ),
        cost_model_required=True,
        max_runtime_minutes=90,
        allowed_operations=(
            ResearchOperation.MAINTAIN_CANDIDATE_QUEUE,
            ResearchOperation.PREPARE_RESEARCH_TASK,
            ResearchOperation.MONITOR_JOB_STATUS,
            ResearchOperation.COLLECT_OUTPUTS_AND_TEST_REPORTS,
            ResearchOperation.WRITE_RESEARCH_SUMMARY,
            ResearchOperation.REJECT_WEAK_CANDIDATE,
            ResearchOperation.ESCALATE_TO_OWNER_REVIEW,
            ResearchOperation.PREPARE_NEXT_AGENT_TASK,
        ),
        forbidden_operations=tuple(sorted(ForbiddenOperation, key=lambda op: op.value)),
        selected_skill_bundle=CANDIDATE_001_SKILL_BUNDLE,
        stop_conditions=_STOP_CONDITIONS,
        latest_result_path="",
        next_action=(
            "Owner decision: approve as research-only, or reject. Data availability for the "
            "declared surfaces is unverified, so approval is followed by an availability check, "
            "never by a start. Nothing runs until owner_approved_for_research is True and the "
            "bars, session calendars and cost model are present."
        ),
        owner_gate_required=True,
        recorded_at="2026-08-22T00:00:00+00:00",
        recorded_by="hermes_research_lead_design")
