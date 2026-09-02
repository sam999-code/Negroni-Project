"""The heartbeat and the daily research report. HERMES-AUTONOMOUS-RESEARCH-001 PART 7.

**A heartbeat is overwritten; an audit record is appended.** The released runtime states the rule this
resolves: *an idle tick writes nothing*, because a loop that journalled its own boredom would bury the
research in it. A 24/7 supervisor still has to prove it is alive, and the answer is that liveness is
*status* -- one small file, rewritten in place, holding only the current state -- while everything that
happened goes to the append-only log. Reading the heartbeat changes nothing and its history is not
kept, because the history of "still running" is not information.

**Every denominator, always, including the zeros.** :func:`daily_research_report` prints
``promising_owner_review_required`` even when it is zero, which it will normally be, and it prints
``rejected`` beside it. A report showing one promising candidate is a very different document from one
showing one promising candidate out of nineteen examined, eleven rejected and four paused on missing
data -- and only the second is honest. This is the released ``CampaignReport`` discipline applied to a
supervisor's day.

**The counts are computed from the queue, never accumulated.** A hand-maintained tally drifts in the
direction of whoever last updated it. Building the report from the durable records means the
denominators cannot quietly diverge from what the queue says happened.

**The report states results by location, not by value.** ``latest_result_path`` is carried through and
nothing is read from it. A daily summary that quoted a figure out of an artifact would be a second,
unreviewed evidence store, and its numbers would circulate without the controls the artifact was
produced under. The owner opens the artifact.

**No clock, no filesystem.** Both functions are pure and take the moment from the caller, so a day's
report can be reproduced exactly from the same queue and the same timestamp.
"""

from __future__ import annotations

from typing import Final

from integrations.hermes_research_orchestrator.audit import AuditOutcome
from integrations.hermes_research_orchestrator.levels import (
    AutomationLevel,
    governance_matrix_digest,
)
from integrations.hermes_research_orchestrator.queue import CandidateStatus

__all__ = [
    "STATUS_POLICY_ID",
    "daily_research_report",
    "heartbeat_document",
    "render_daily_report",
]

STATUS_POLICY_ID: Final = "HRO-STATUS-v1"
"""Heartbeat overwritten in place; report computed from the queue with every denominator."""


def heartbeat_document(*, observed_at: str, level: AutomationLevel, tick: int,
                       running_jobs: int, paused_reason: str = "") -> dict:
    """The current state of the lead. Overwritten in place at every poll, idle or not.

    ``paused_reason`` is empty when the lead is simply idle, and populated when it stopped. The
    distinction matters more than it looks: an operator glancing at a heartbeat needs to tell "nothing
    to do" from "cannot proceed", and a loop that reported both as ``idle`` would make a governance
    pause look like a quiet night.
    """
    return {
        "policy": STATUS_POLICY_ID,
        "observed_at": observed_at,
        "level": level.value,
        "tick": tick,
        "running_jobs": running_jobs,
        "state": "paused" if paused_reason.strip() else "idle" if not running_jobs else "working",
        "paused_reason": paused_reason.strip(),
        "governance_digest": governance_matrix_digest(),
        "execution_authority": "NONE",
        "selection_authorised": False,
        "confirmation_authorised": False,
    }


def daily_research_report(candidates: tuple, records: tuple, *,
                          covering: str, level: AutomationLevel) -> dict:
    """The day's report, computed from the queue and the audit log.

    Args:
        candidates: The latest record of every candidate. Not the full history -- a day's report
            counts candidates, and a candidate that moved three times is still one candidate.
        records: The audit records written during the period.
        covering: What period this covers, as text supplied by the caller.
        level: The level the lead ran at.
    """
    by_status = {status.value: 0 for status in CandidateStatus}
    for candidate in candidates:
        by_status[candidate.status.value] += 1

    outcomes = {outcome.value: 0 for outcome in AuditOutcome}
    conditions: dict = {}
    for record in records:
        outcomes[record.outcome.value] += 1
        for condition in record.conditions:
            conditions[condition] = conditions.get(condition, 0) + 1

    # Either half puts a candidate in front of a person. The status half catches the four
    # owner-gated states; the field half catches a candidate that is merely PROPOSED and waiting to
    # be approved -- which is the whole of the queue on day one, and would otherwise report as
    # "awaiting owner: none" while the only thing it needed was the owner.
    owner_gated = tuple(c for c in candidates if c.status.requires_owner or c.owner_gate_required)
    return {
        "policy": STATUS_POLICY_ID,
        "covering": covering,
        "level": level.value,
        "governance_digest": governance_matrix_digest(),
        "candidates_total": len(candidates),
        "candidates_by_status": by_status,
        "audit_outcomes": outcomes,
        "stop_conditions_seen": dict(sorted(conditions.items())),
        "awaiting_owner": [
            {"candidate_id": c.candidate_id, "candidate_name": c.candidate_name,
             "status": c.status.value, "next_action": c.next_action,
             "latest_result_path": c.latest_result_path}
            for c in owner_gated
        ],
        "execution_authority": "NONE",
        "selection_authorised": False,
        "confirmation_authorised": False,
        "signals_emitted": 0,
        "grades_assigned": 0,
        "orders_placed": 0,
    }


def render_daily_report(report: dict) -> str:
    """The report as text, for Telegram, a file, or an owner reading it in a terminal.

    The three trailing zeros are printed rather than omitted. A daily report that simply did not
    mention signals would leave a reader to infer that none were emitted; a report that prints
    ``signals emitted: 0`` states it. Over months of quiet output the difference between an inference
    and a statement is the whole value of the line.
    """
    lines = [
        f"EVOLITH RESEARCH LEAD -- {report['covering']}",
        f"level: {report['level']}   governance: {report['governance_digest'][:16]}...",
        "",
        f"candidates: {report['candidates_total']}",
    ]
    for status, count in report["candidates_by_status"].items():
        lines.append(f"  {status}: {count}")
    lines.append("")
    lines.append("audit outcomes:")
    for outcome, count in report["audit_outcomes"].items():
        lines.append(f"  {outcome}: {count}")
    if report["stop_conditions_seen"]:
        lines.append("")
        lines.append("stop conditions seen:")
        for condition, count in report["stop_conditions_seen"].items():
            lines.append(f"  {condition}: {count}")
    lines.append("")
    if report["awaiting_owner"]:
        lines.append("AWAITING OWNER:")
        for entry in report["awaiting_owner"]:
            lines.append(f"  {entry['candidate_id']} ({entry['status']}) -- {entry['next_action']}")
            if entry["latest_result_path"]:
                lines.append(f"      result: {entry['latest_result_path']}")
    else:
        lines.append("AWAITING OWNER: none")
    lines += [
        "",
        f"execution authority: {report['execution_authority']}",
        f"selection authorised: {report['selection_authorised']}",
        f"confirmation authorised: {report['confirmation_authorised']}",
        f"signals emitted: {report['signals_emitted']}",
        f"grades assigned: {report['grades_assigned']}",
        f"orders placed: {report['orders_placed']}",
    ]
    return "\n".join(lines)
