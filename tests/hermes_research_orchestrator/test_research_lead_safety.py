"""The research lead's eight required properties. HERMES-AUTONOMOUS-RESEARCH-001 tests A through H.

Nothing is started, no loop runs, no lock is taken and every fixture is constructed in-process. The
only filesystem this file touches is pytest's ``tmp_path``, which stands in for a lead root.

The eight are the owner's list, in the owner's order:

  A. LEVEL_2 cannot create live signals.
  B. LEVEL_2 cannot set execution authority.
  C. Broker and MetaTrader fields are forbidden.
  D. A candidate must be owner-approved for research before running.
  E. Missing data pauses instead of fabricating.
  F. Failed tests pause the pipeline.
  G. A promising result becomes an owner review, not a live signal.
  H. The audit log is written.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from integrations.hermes_research_orchestrator import (
    FABRICATION_FIELDS,
    FORBIDDEN_OPERATIONS,
    LEVEL_OPERATIONS,
    AuditLog,
    AuditOutcome,
    AuditRefused,
    AutomationLevel,
    CandidateQueue,
    CandidateQueueRefused,
    CandidateStatus,
    DryRunReport,
    ForbiddenOperation,
    HermesLeadRootPolicy,
    HermesWriteTargetRefused,
    LevelNotDesigned,
    LevelRefused,
    PreflightEnvironment,
    ResearchCandidate,
    ResearchOperation,
    StopAction,
    StopCondition,
    active_level,
    daily_research_report,
    dry_run,
    escalation_status,
    evaluate_preflight,
    governance_matrix,
    governance_matrix_digest,
    heartbeat_document,
    load_audit_log,
    load_candidate_queue,
    record_for,
    refuse_forbidden_operation,
    render_daily_report,
    task_brief_for,
    volatility_normalized_session_breakout,
)
from integrations.hermes_research_orchestrator import (
    RejectedLine,
    TickObservations,
    decode_candidate,
    encode_candidate,
)
from integrations.hermes_research_orchestrator.levels import (
    APPROVAL_MARKER_NAME,
    APPROVED_DIGEST_KEY,
)

NOW = "2026-08-21T09:00:00+00:00"
LEVEL_2 = AutomationLevel.LEVEL_2_AUTONOMOUS_RESEARCH


def _policy(tmp_path):
    return HermesLeadRootPolicy.owning(tmp_path)


def _candidate(**changes) -> ResearchCandidate:
    fields = dict(
        candidate_id="CAND-TEST-001", candidate_name="test candidate",
        status=CandidateStatus.READY_FOR_EVENT_STUDY, priority=0,
        assets=("EURUSD",), timeframes=("15m",), context_timeframes=("4H",),
        hypothesis="a refutable claim",
        owner_approved_for_research=True, data_required=("bars",), cost_model_required=True,
        max_runtime_minutes=30,
        allowed_operations=(ResearchOperation.PREPARE_RESEARCH_TASK,),
        forbidden_operations=tuple(ForbiddenOperation),
        selected_skill_bundle=("quant/statistical-reasoning",),
        stop_conditions=("tests_failing",), latest_result_path="", next_action="run the study",
        owner_gate_required=False, recorded_at=NOW, recorded_by="test")
    fields.update(changes)
    return ResearchCandidate(**fields)


def _environment(**changes) -> PreflightEnvironment:
    fields = dict(level=LEVEL_2, candidate_is_owner_approved=True, candidate_is_ready=True,
                  required_data_present=True, cost_model_present=True, cost_model_required=True,
                  tests_passing=True, audit_log_writable=True, max_runtime_minutes=30)
    fields.update(changes)
    return PreflightEnvironment(**fields)


# -- A. LEVEL_2 cannot create live signals -------------------------------------------------------

def test_level_2_permits_no_operation_that_creates_a_live_signal():
    """The matrix is the whole permission set, and signal emission is not in it at any level."""
    permitted = LEVEL_OPERATIONS[LEVEL_2]
    assert permitted <= frozenset(ResearchOperation)
    assert ResearchOperation.LAUNCH_BOUNDED_RESEARCH_JOB in permitted
    # There is no member of the permitted vocabulary that emits, confirms or grades anything.
    assert not any("signal" in op.value or "grade" in op.value or "confirm" in op.value
                   for op in permitted)
    assert ForbiddenOperation.LIVE_SIGNAL_EMISSION in FORBIDDEN_OPERATIONS
    assert LEVEL_2.permitted_operations == permitted


def test_the_prohibitions_do_not_vary_by_level():
    """All ten hold at LEVEL_0 and at LEVEL_2. A per-level table would invite an omission."""
    assert len(FORBIDDEN_OPERATIONS) == 10
    for level in (AutomationLevel.LEVEL_0_MANUAL, AutomationLevel.LEVEL_1_SUPERVISED, LEVEL_2):
        assert not (level.permitted_operations & {ResearchOperation(op.value)
                                                  for op in ()})
        assert FORBIDDEN_OPERATIONS == frozenset(ForbiddenOperation)


@pytest.mark.parametrize("name", sorted(op.value for op in ForbiddenOperation))
def test_every_forbidden_operation_is_refused_by_name(name):
    """A caller that builds an operation name from text is refused as loudly as one that imports."""
    with pytest.raises(LevelRefused, match="FORBIDDEN_OPERATION"):
        refuse_forbidden_operation(name)


def test_an_unknown_operation_name_is_not_silently_treated_as_forbidden():
    """The refusal names the ten; it is not a general-purpose allow-list."""
    refuse_forbidden_operation("prepare_research_task")


# -- B. LEVEL_2 cannot set execution authority ---------------------------------------------------

def test_no_level_grants_execution_authority():
    """Every rung, including the two that are not designed."""
    for level in AutomationLevel:
        assert level.grants_execution_authority is False
    assert governance_matrix()["levels"][LEVEL_2.value]["grants_execution_authority"] is False


def test_no_status_outcome_or_operation_implies_authority():
    """Three vocabularies, one answer. A status is a place in a queue, never a permission."""
    for status in CandidateStatus:
        assert status.implies_authority is False
    for outcome in AuditOutcome:
        assert outcome.implies_authority is False
    for operation in ResearchOperation:
        assert operation.grants_execution_authority is False


def test_the_candidate_record_reports_no_authority():
    assert _candidate().implies_authority is False
    assert _candidate().as_dict()["implies_authority"] is False


def test_the_undesigned_levels_refuse_to_answer_rather_than_answering_none():
    """An empty permission set would read as 'may do nothing'; the truth is 'not yet decided'."""
    for level in (AutomationLevel.LEVEL_3_PAPER_ONLY, AutomationLevel.LEVEL_4_LIMITED_LIVE):
        assert level.is_designed is False
        with pytest.raises(LevelNotDesigned, match="LEVEL_NOT_DESIGNED"):
            _ = level.permitted_operations


def test_the_governance_digest_changes_when_the_matrix_changes():
    """The digest is what stops a lead running under looser rules than the ones it published."""
    before = governance_matrix_digest()
    assert len(before) == 64
    assert before == governance_matrix_digest()
    matrix = governance_matrix()
    matrix["levels"][LEVEL_2.value]["permitted_operations"].append("something_new")
    import hashlib

    from evolith_core.shared.canonical_json import canonical_bytes
    assert hashlib.sha256(canonical_bytes(matrix)).hexdigest() != before


# -- C. Broker and MetaTrader fields are forbidden -----------------------------------------------

BROKER_FIELD_TOKENS = (
    "broker", "mt5", "metatrader", "terminal64", "account", "login", "server",
    "order", "position", "ticket", "lot", "volume", "magic", "slippage",
    "stop_loss", "take_profit", "balance", "equity", "margin", "leverage",
    # HERMES-AUTONOMOUS-RESEARCH-001P: the emission-shaped names too. A record field called
    # signal_export_path or telegram_alert is not a trade, but it is the door a trade walks through.
    "signal", "export", "grade", "alert", "telegram",
)
"""Any field name a record would need in order to describe, reach or place a trade -- or to emit,
grade or alert on one. The sweep is over *field names*, deliberately: prose and evidence strings may
say "signal" while promising never to emit one, and a sweep over text would fail the promise for
naming the thing it forbids."""

RECORD_TYPES = (ResearchCandidate, PreflightEnvironment, DryRunReport,
                TickObservations, RejectedLine)


@pytest.mark.parametrize("record_type", RECORD_TYPES)
def test_no_record_carries_a_broker_or_terminal_field(record_type):
    """Enforcement by absence. A field that was never added cannot be populated."""
    names = {f.name.lower() for f in dataclasses.fields(record_type)}
    offending = {n for n in names if any(token in n for token in BROKER_FIELD_TOKENS)}
    assert not offending, f"{record_type.__name__} carries broker-shaped fields: {sorted(offending)}"


def test_the_serialised_candidate_carries_no_broker_key():
    """The wire form too, because a key absent from the dataclass could still be added at encode."""
    document = _candidate().as_dict()
    offending = {k for k in document
                 if any(token in k.lower() for token in BROKER_FIELD_TOKENS)}
    assert not offending, f"serialised candidate carries {sorted(offending)}"


def test_the_lead_may_not_write_into_a_live_evidence_root(tmp_path):
    """Five roots, refused by destination before anything is created."""
    policy = _policy(tmp_path)
    for name in ("EvolithShadowStore", "EvolithSignals", "EvolithResearch",
                 "EvolithGovernance", "EvolithExternalTools"):
        target = tmp_path / name / "queue.jsonl"
        with pytest.raises(HermesWriteTargetRefused, match="HERMES_WRITE_TARGET_REFUSED"):
            policy.write_target(target, what="candidate queue")
        assert not target.exists()
        assert not target.parent.exists()          # the guard created nothing on its way to refusing


def test_the_lead_may_not_write_into_an_evolith_checkout(tmp_path):
    """Recognised by content, so it holds for the main checkout and for every worktree alike."""
    checkout = tmp_path / "some-worktree"
    (checkout / "evolith_core").mkdir(parents=True)
    (checkout / "integrations").mkdir()
    (checkout / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    policy = _policy(tmp_path)
    with pytest.raises(HermesWriteTargetRefused, match="Evolith checkout or worktree"):
        policy.write_target(checkout / "integrations" / "sneaky.py", what="audit log")


def test_the_lead_may_not_write_outside_its_own_root(tmp_path):
    """One place, so everything the lead ever wrote can be found and deleted in one place."""
    policy = HermesLeadRootPolicy.owning(tmp_path / "lead")
    with pytest.raises(HermesWriteTargetRefused, match="outside the research lead"):
        policy.write_target(tmp_path / "elsewhere" / "audit.jsonl", what="audit log")


def test_a_traversal_is_judged_on_where_it_lands(tmp_path):
    """Resolution first, then judgement -- the released rule, which defeats ``..`` and a junction."""
    policy = HermesLeadRootPolicy.owning(tmp_path / "lead")
    (tmp_path / "lead").mkdir()
    with pytest.raises(HermesWriteTargetRefused):
        policy.write_target(tmp_path / "lead" / ".." / "escape.jsonl", what="audit log")


# -- D. A candidate must be owner-approved before running ----------------------------------------

def test_a_runnable_status_without_owner_approval_is_refused_at_construction():
    """Not a guard that could be bypassed by a second path: the record cannot exist."""
    with pytest.raises(CandidateQueueRefused, match="UNAPPROVED_RUNNABLE"):
        _candidate(status=CandidateStatus.READY_FOR_EVENT_STUDY,
                   owner_approved_for_research=False)


def test_a_running_candidate_without_owner_approval_is_refused_at_construction():
    with pytest.raises(CandidateQueueRefused, match="UNAPPROVED_RUNNING"):
        _candidate(status=CandidateStatus.RUNNING_RESEARCH, owner_approved_for_research=False)


def test_approval_alone_does_not_make_a_candidate_runnable():
    """Approval says a question may be asked; it does not say the data to ask it with is present."""
    approved_but_not_ready = _candidate(status=CandidateStatus.OWNER_APPROVED_RESEARCH,
                                        owner_approved_for_research=True)
    assert approved_but_not_ready.may_start_research is False


def test_the_preflight_pauses_when_owner_approval_is_absent():
    decision = evaluate_preflight(_environment(candidate_is_owner_approved=False))
    assert decision.action is StopAction.PAUSE
    assert StopCondition.OWNER_APPROVAL_ABSENT in decision.conditions


def test_level_2_is_never_inferred_without_the_owner_marker(tmp_path):
    """Autonomy is granted by a person creating a file, and by nothing else."""
    assert active_level(tmp_path) is AutomationLevel.LEVEL_1_SUPERVISED
    (tmp_path / APPROVAL_MARKER_NAME).write_text("", encoding="utf-8")
    assert active_level(tmp_path) is AutomationLevel.LEVEL_1_SUPERVISED   # empty is not approval
    # Plain approval text stopped being approval in HERMES-AUTONOMOUS-RESEARCH-001P: an approval
    # that names no matrix digest would keep approving after the matrix changed under it.
    (tmp_path / APPROVAL_MARKER_NAME).write_text("owner approves research-only", encoding="utf-8")
    assert active_level(tmp_path) is AutomationLevel.LEVEL_1_SUPERVISED
    (tmp_path / APPROVAL_MARKER_NAME).write_text(
        f"owner approves research-only\n{APPROVED_DIGEST_KEY}: {governance_matrix_digest()}\n",
        encoding="utf-8")
    assert active_level(tmp_path) is LEVEL_2


def test_a_marker_naming_a_stale_digest_is_treated_as_absent(tmp_path):
    """An approval is an approval of a specific matrix. A stale digest is somebody else's."""
    (tmp_path / APPROVAL_MARKER_NAME).write_text(
        f"{APPROVED_DIGEST_KEY}: {'0' * 64}\n", encoding="utf-8")
    assert active_level(tmp_path) is AutomationLevel.LEVEL_1_SUPERVISED
    (tmp_path / APPROVAL_MARKER_NAME).write_text(
        f"{APPROVED_DIGEST_KEY}:\n", encoding="utf-8")                    # blank value
    assert active_level(tmp_path) is AutomationLevel.LEVEL_1_SUPERVISED
    (tmp_path / APPROVAL_MARKER_NAME).write_text(
        f"{APPROVED_DIGEST_KEY} = {governance_matrix_digest()}", encoding="utf-8")
    assert active_level(tmp_path) is LEVEL_2                              # '=' form accepted


def test_a_candidate_declaring_fewer_than_ten_prohibitions_is_refused():
    partial = tuple(op for op in ForbiddenOperation
                    if op is not ForbiddenOperation.TRADE_EXECUTION)
    with pytest.raises(CandidateQueueRefused, match="UNDERSTATED_PROHIBITIONS"):
        _candidate(forbidden_operations=partial)


def test_an_unbounded_runtime_is_refused():
    """'Bounded' is the entire licence LEVEL_2 has."""
    with pytest.raises(CandidateQueueRefused, match="UNBOUNDED_RUNTIME"):
        _candidate(max_runtime_minutes=0)


# -- E. Missing data pauses instead of fabricating -----------------------------------------------

def test_missing_data_pauses():
    decision = evaluate_preflight(_environment(required_data_present=False))
    assert decision.action is StopAction.PAUSE
    assert StopCondition.REQUIRED_DATA_MISSING in decision.conditions
    assert StopCondition.REQUIRED_DATA_MISSING.action is StopAction.PAUSE


def test_a_missing_cost_model_is_distinct_from_missing_data():
    """Two refusals to start; only one of them can be fixed without waiting for a feed."""
    decision = evaluate_preflight(_environment(cost_model_present=False))
    assert StopCondition.COST_MODEL_MISSING in decision.conditions
    assert StopCondition.REQUIRED_DATA_MISSING not in decision.conditions


def test_every_stop_condition_pauses_and_none_degrades():
    """Thirteen conditions, one action. There is no severity below which a loop may carry on."""
    assert {c.action for c in StopCondition} == {StopAction.PAUSE}
    assert len(list(StopCondition)) == 13


def test_a_pause_that_cannot_say_why_is_refused():
    from integrations.hermes_research_orchestrator.stops import StopDecision, StopRefused
    with pytest.raises(StopRefused, match="PAUSE_WITHOUT_CONDITION"):
        StopDecision(action=StopAction.PAUSE,
                     operation=ResearchOperation.LAUNCH_BOUNDED_RESEARCH_JOB)


def test_proceeding_while_a_condition_fired_is_refused():
    from integrations.hermes_research_orchestrator.stops import StopDecision, StopRefused
    with pytest.raises(StopRefused, match="PROCEED_WITH_CONDITION"):
        StopDecision(action=StopAction.PROCEED,
                     operation=ResearchOperation.LAUNCH_BOUNDED_RESEARCH_JOB,
                     conditions=(StopCondition.TESTS_FAILING,), evidence=("x",))


def test_a_dry_run_report_carries_no_performance_claim():
    """No field for a win rate, an edge or a probability. Absence, not a caption."""
    names = {f.name.lower() for f in dataclasses.fields(DryRunReport)}
    assert not (names & set(FABRICATION_FIELDS))
    report = dry_run(_candidate(), _environment())
    serialised = json.dumps(report.as_dict())
    for banned in FABRICATION_FIELDS:
        assert f'"{banned}"' not in serialised


def test_the_daily_report_invents_no_number():
    report = daily_research_report((_candidate(),), (), covering="2026-08-21", level=LEVEL_2)
    for banned in FABRICATION_FIELDS:
        assert banned not in report


# -- F. Failed tests pause the pipeline ----------------------------------------------------------

def test_failing_tests_pause_and_stop_the_whole_lead():
    """Not a skip to the next candidate: the next candidate would run against the same broken tree."""
    decision = evaluate_preflight(_environment(tests_passing=False))
    assert decision.action is StopAction.PAUSE
    assert StopCondition.TESTS_FAILING in decision.conditions
    assert decision.blocks_the_whole_lead is True


def test_a_dirty_protected_path_pauses_and_stops_the_whole_lead():
    decision = evaluate_preflight(
        _environment(git_dirty_protected_paths=("integrations/research_orchestration/queue.py",)))
    assert StopCondition.GIT_DIRTY_IN_PROTECTED_PATH in decision.conditions
    assert decision.blocks_the_whole_lead is True


def test_an_overlapping_edit_in_another_terminal_pauses():
    decision = evaluate_preflight(_environment(overlapping_paths=("integrations/foo.py",)))
    assert StopCondition.OVERLAPPING_EDIT_IN_ANOTHER_TERMINAL in decision.conditions


def test_being_full_is_not_a_reason_to_stop_supervising():
    """The lead is healthy and simply has no slot; it waits rather than halting."""
    decision = evaluate_preflight(_environment(running_jobs=1, max_concurrent_jobs=1))
    assert StopCondition.MAX_CONCURRENT_JOBS_REACHED in decision.conditions
    assert decision.blocks_the_whole_lead is False


def test_every_condition_that_fired_is_reported_not_just_the_first():
    """An owner fixing one at a time against a first-only report finds the next a poll later."""
    decision = evaluate_preflight(
        _environment(tests_passing=False, required_data_present=False, cost_model_present=False,
                     git_dirty_protected_paths=("a.py",)))
    assert {StopCondition.TESTS_FAILING, StopCondition.REQUIRED_DATA_MISSING,
            StopCondition.COST_MODEL_MISSING,
            StopCondition.GIT_DIRTY_IN_PROTECTED_PATH} <= set(decision.conditions)
    assert len(decision.evidence) == len(decision.conditions)


def test_a_clean_environment_proceeds():
    """The guarantees are refusals; this proves they are not refusals of everything."""
    decision = evaluate_preflight(_environment())
    assert decision.action is StopAction.PROCEED
    assert decision.conditions == ()


# -- G. A promising result becomes an owner review -----------------------------------------------

def test_a_promising_result_becomes_an_owner_review():
    status = escalation_status(promising=True)
    assert status is CandidateStatus.PROMISING_OWNER_REVIEW_REQUIRED
    assert status.requires_owner is True
    assert status.implies_authority is False
    assert status.may_start_research is False


def test_an_unpromising_result_is_rejected_and_the_rejection_is_also_owner_gated():
    """A lead that could un-reject its own rejections could retry until something looked good."""
    status = escalation_status(promising=False)
    assert status is CandidateStatus.REJECTED
    assert status.is_rejection is True
    assert status.requires_owner is True


def test_failed_tests_are_not_recorded_as_a_scientific_rejection():
    """A broken harness must not be readable afterwards as a broken hypothesis."""
    assert CandidateStatus.FAILED_TESTS.is_rejection is False
    assert CandidateStatus.PAUSED_GOVERNANCE_RISK.is_rejection is False


def test_an_owner_gated_status_must_declare_its_gate():
    with pytest.raises(CandidateQueueRefused, match="owner_gate_required=False"):
        _candidate(status=CandidateStatus.PROMISING_OWNER_REVIEW_REQUIRED,
                   owner_gate_required=False)


def test_paper_only_review_is_a_place_in_a_queue_and_not_a_permission():
    """It names LEVEL_3, which this task did not design."""
    assert CandidateStatus.READY_FOR_PAPER_ONLY_REVIEW.implies_authority is False
    assert CandidateStatus.READY_FOR_PAPER_ONLY_REVIEW.requires_owner is True


# -- H. The audit log is written -----------------------------------------------------------------

def test_the_audit_log_is_written_and_reads_back(tmp_path):
    policy = _policy(tmp_path)
    log = AuditLog(policy=policy)
    target = log.bind_path(tmp_path / "audit" / "research_lead.jsonl")
    decision = evaluate_preflight(_environment(tests_passing=False))
    record = record_for(decision, record_id="TICK-0001", occurred_at=NOW, level=LEVEL_2,
                        candidate_id="CAND-TEST-001")
    stored, appended = log.append(record)
    assert appended is True
    assert target.exists()

    reloaded = load_audit_log(target, policy)
    assert len(reloaded.records) == 1
    assert reloaded.records[0].record_id == "TICK-0001"
    assert reloaded.records[0].outcome is AuditOutcome.PAUSED
    assert reloaded.records[0].conditions == ("tests_failing",)
    assert reloaded.records[0].content_digest == stored.content_digest


def test_every_audit_record_carries_the_governance_digest_in_force(tmp_path):
    """Without it, loosening a level would silently reinterpret the entire history."""
    decision = evaluate_preflight(_environment())
    record = record_for(decision, record_id="TICK-0002", occurred_at=NOW, level=LEVEL_2)
    assert record.governance_digest == governance_matrix_digest()
    assert record.outcome is AuditOutcome.PERMITTED


def test_a_refusal_that_names_no_condition_is_refused():
    from integrations.hermes_research_orchestrator.audit import AuditRecord
    with pytest.raises(AuditRefused, match="REFUSAL_WITHOUT_CONDITION"):
        AuditRecord(record_id="X", occurred_at=NOW, level=LEVEL_2,
                    operation=ResearchOperation.LAUNCH_BOUNDED_RESEARCH_JOB,
                    outcome=AuditOutcome.REFUSED, detail="because",
                    governance_digest=governance_matrix_digest())


def test_a_hand_edited_audit_log_is_refused_rather_than_partly_read(tmp_path):
    policy = _policy(tmp_path)
    log = AuditLog(policy=policy)
    target = log.bind_path(tmp_path / "audit.jsonl")
    log.append(record_for(evaluate_preflight(_environment()), record_id="TICK-0003",
                          occurred_at=NOW, level=LEVEL_2))
    tampered = json.loads(target.read_text(encoding="utf-8").splitlines()[0])
    tampered["detail"] = "nothing to see here"
    target.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
    with pytest.raises(AuditRefused, match="AUDIT_DIGEST_MISMATCH"):
        load_audit_log(target, policy)


def test_a_conflicting_audit_identity_is_refused_and_the_later_writer_does_not_win(tmp_path):
    policy = _policy(tmp_path)
    log = AuditLog(policy=policy)
    log.bind_path(tmp_path / "audit.jsonl")
    first = record_for(evaluate_preflight(_environment()), record_id="TICK-0004",
                       occurred_at=NOW, level=LEVEL_2, detail="one")
    log.append(first)
    assert log.append(first)[1] is False                      # identical append is idempotent
    second = record_for(evaluate_preflight(_environment()), record_id="TICK-0004",
                        occurred_at=NOW, level=LEVEL_2, detail="two")
    with pytest.raises(AuditRefused, match="CONFLICTING_RECORD_IDENTITY"):
        log.append(second)
    assert len(log.records) == 1


def test_the_audit_log_cannot_be_bound_inside_evolith(tmp_path):
    """The one write this package performs is judged by the same door as everything else."""
    policy = _policy(tmp_path)
    log = AuditLog(policy=policy)
    with pytest.raises(HermesWriteTargetRefused):
        log.bind_path(tmp_path / "EvolithResearch" / "audit.jsonl")


# -- the candidate queue -------------------------------------------------------------------------

def test_the_candidate_queue_appends_advances_and_reads_back(tmp_path):
    policy = _policy(tmp_path)
    queue = CandidateQueue(policy=policy)
    target = queue.bind_path(tmp_path / "candidates.jsonl")

    proposed = volatility_normalized_session_breakout()
    queue.append(proposed)
    assert queue.append(proposed)[1] is False                 # re-appending the head is a no-op

    approved = dataclasses.replace(
        proposed, status=CandidateStatus.OWNER_APPROVED_RESEARCH,
        owner_approved_for_research=True, next_action="check data availability")
    queue.append(approved)

    reloaded = load_candidate_queue(target, policy)
    assert len(reloaded.records) == 2
    assert reloaded.latest(proposed.candidate_id).status is CandidateStatus.OWNER_APPROVED_RESEARCH
    assert len(reloaded.open_candidates()) == 1


def test_a_mis_versioned_candidate_line_fails_closed(tmp_path):
    policy = _policy(tmp_path)
    target = tmp_path / "candidates.jsonl"
    target.write_text(json.dumps({"schema_version": 99, "candidate_id": "X"}) + "\n",
                      encoding="utf-8")
    with pytest.raises(CandidateQueueRefused, match="CANDIDATE_SCHEMA_VERSION_UNKNOWN"):
        load_candidate_queue(target, policy)


# -- the dry run for EVOLITH-RESEARCH-CANDIDATE-001 ----------------------------------------------

def test_candidate_001_is_proposed_and_not_owner_approved():
    """The task permits OWNER_APPROVED_RESEARCH only on explicit approval, and none exists."""
    candidate = volatility_normalized_session_breakout()
    assert candidate.candidate_id == "EVOLITH-RESEARCH-CANDIDATE-001"
    assert candidate.status is CandidateStatus.PROPOSED
    assert candidate.owner_approved_for_research is False
    assert candidate.may_start_research is False
    assert candidate.owner_gate_required is True


def test_candidate_001_declares_a_bound_and_a_cost_model():
    candidate = volatility_normalized_session_breakout()
    assert candidate.max_runtime_minutes == 90
    assert candidate.cost_model_required is True
    assert candidate.data_required


def test_candidate_001_dry_run_would_not_start_and_says_why():
    """The example the owner asked for. It runs nothing and states four separate blockers."""
    candidate = volatility_normalized_session_breakout()
    report = dry_run(candidate, _environment(
        candidate_is_owner_approved=candidate.owner_approved_for_research,
        candidate_is_ready=candidate.status.may_start_research,
        required_data_present=False, cost_model_present=False,
        cost_model_required=candidate.cost_model_required,
        max_runtime_minutes=candidate.max_runtime_minutes))
    assert report.would_start is False
    assert set(report.decision.conditions) == {
        StopCondition.OWNER_APPROVAL_ABSENT, StopCondition.CANDIDATE_NOT_READY,
        StopCondition.REQUIRED_DATA_MISSING, StopCondition.COST_MODEL_MISSING}
    assert report.governance_digest == governance_matrix_digest()


def test_the_brief_is_produced_even_when_the_candidate_is_blocked():
    """Reviewing the question is most of the value of a supervised level."""
    candidate = volatility_normalized_session_breakout()
    brief = task_brief_for(candidate, AutomationLevel.LEVEL_1_SUPERVISED)
    assert candidate.hypothesis in brief
    assert "FORBIDDEN, AT EVERY LEVEL" in brief
    for op in ForbiddenOperation:
        assert op.value in brief
    assert "not authority to trade" in brief


def test_the_dry_run_writes_nothing(tmp_path):
    """Pure by construction: the lead root is untouched after a full dry run."""
    candidate = volatility_normalized_session_breakout()
    before = sorted(p.name for p in tmp_path.iterdir())
    dry_run(candidate, _environment(candidate_is_owner_approved=False, candidate_is_ready=False))
    assert sorted(p.name for p in tmp_path.iterdir()) == before


# -- the heartbeat and the daily report ----------------------------------------------------------

def test_the_heartbeat_distinguishes_idle_from_paused():
    """An operator needs to tell 'nothing to do' from 'cannot proceed'."""
    idle = heartbeat_document(observed_at=NOW, level=LEVEL_2, tick=7, running_jobs=0)
    assert idle["state"] == "idle" and idle["paused_reason"] == ""
    paused = heartbeat_document(observed_at=NOW, level=LEVEL_2, tick=8, running_jobs=0,
                                paused_reason="tests_failing")
    assert paused["state"] == "paused"
    assert paused["execution_authority"] == "NONE"
    assert paused["selection_authorised"] is False
    assert paused["confirmation_authorised"] is False


def test_the_daily_report_prints_every_denominator_including_the_zeros():
    """A report showing one promising candidate is a different document from one out of nineteen."""
    report = daily_research_report(
        (volatility_normalized_session_breakout(),), (), covering="2026-08-21", level=LEVEL_2)
    assert set(report["candidates_by_status"]) == {s.value for s in CandidateStatus}
    assert report["candidates_by_status"]["promising_owner_review_required"] == 0
    assert report["signals_emitted"] == 0
    assert report["grades_assigned"] == 0
    assert report["orders_placed"] == 0
    assert report["execution_authority"] == "NONE"

    text = render_daily_report(report)
    assert "signals emitted: 0" in text
    assert "grades assigned: 0" in text
    assert "orders placed: 0" in text
    assert "execution authority: NONE" in text


def test_a_proposed_candidate_awaiting_approval_appears_in_front_of_the_owner():
    """Day one of the queue is entirely PROPOSED candidates, and the only thing they need is a
    person. A report driven by status alone would print 'awaiting owner: none' on exactly the day
    the owner was the sole blocker."""
    candidate = volatility_normalized_session_breakout()
    assert candidate.status.requires_owner is False       # PROPOSED is not an owner-gated *state*
    assert candidate.owner_gate_required is True          # but this candidate declares the gate
    report = daily_research_report((candidate,), (), covering="2026-08-21", level=LEVEL_2)
    assert [e["candidate_id"] for e in report["awaiting_owner"]] == [candidate.candidate_id]
    assert "AWAITING OWNER: none" not in render_daily_report(report)


def test_the_daily_report_reports_results_by_location_not_by_value(tmp_path):
    """Nothing is read from the artifact; a summary that quoted a figure would be a second store."""
    promising = _candidate(status=CandidateStatus.PROMISING_OWNER_REVIEW_REQUIRED,
                           owner_gate_required=True,
                           latest_result_path="results/study-001.json")
    report = daily_research_report((promising,), (), covering="2026-08-21", level=LEVEL_2)
    assert report["awaiting_owner"][0]["latest_result_path"] == "results/study-001.json"
    assert "study-001.json" in render_daily_report(report)


# -- HERMES-AUTONOMOUS-RESEARCH-001P: the owner's decisions --------------------------------------

def test_the_seed_surface_is_the_owners_gold_and_nasdaq():
    """The owner rejected the EURUSD substitution. The surface is theirs and is not negotiable."""
    candidate = volatility_normalized_session_breakout()
    assert candidate.assets == ("XAUUSD", "NAS100")
    assert "EURUSD" not in candidate.assets
    assert candidate.timeframes == ("15m", "1h")
    assert candidate.context_timeframes == ("4H", "1D")


def test_a_candidate_without_a_skill_bundle_is_refused():
    with pytest.raises(CandidateQueueRefused, match="UNDECLARED_SKILL_BUNDLE"):
        _candidate(selected_skill_bundle=())
    with pytest.raises(CandidateQueueRefused, match="UNDECLARED_SKILL_BUNDLE"):
        _candidate(selected_skill_bundle=("  ",))


def test_the_skill_bundle_and_context_timeframes_survive_the_ledger_roundtrip():
    decoded, _ = decode_candidate(encode_candidate(_candidate()))
    assert decoded.selected_skill_bundle == ("quant/statistical-reasoning",)
    assert decoded.context_timeframes == ("4H",)


def test_the_seed_bundle_is_research_design_only():
    """No skill name in the seed bundle is shaped like emission, execution or alerting."""
    candidate = volatility_normalized_session_breakout()
    assert candidate.selected_skill_bundle
    for name in candidate.selected_skill_bundle:
        offending = [t for t in BROKER_FIELD_TOKENS if t in name.lower()]
        assert not offending, f"{name} carries {offending}"


def test_a_running_native_gateway_pauses_as_a_governance_risk():
    decision = evaluate_preflight(_environment(native_gateway_running=True))
    assert decision.action is StopAction.PAUSE
    assert StopCondition.GOVERNANCE_RISK in decision.conditions
    assert decision.blocks_the_whole_lead


def test_an_open_gateway_port_pauses_as_a_governance_risk():
    decision = evaluate_preflight(_environment(gateway_port_open=True))
    assert decision.action is StopAction.PAUSE
    assert StopCondition.GOVERNANCE_RISK in decision.conditions
    evidence = dict(zip(decision.conditions, decision.evidence))[StopCondition.GOVERNANCE_RISK]
    assert "8644" in evidence


def test_every_gateway_and_caller_risk_is_reported_not_just_the_first():
    """One condition, one evidence line, all three reasons -- the dedup may drop none of them."""
    decision = evaluate_preflight(_environment(
        native_gateway_running=True, gateway_port_open=True,
        governance_risk="a marker was hand-edited"))
    assert decision.conditions.count(StopCondition.GOVERNANCE_RISK) == 1
    evidence = dict(zip(decision.conditions, decision.evidence))[StopCondition.GOVERNANCE_RISK]
    for expected in ("gateway process is running", "8644", "hand-edited"):
        assert expected in evidence


def test_the_field_token_sweep_catches_an_emission_shaped_field():
    """The negative control for the extended tokens: each new token bites on a realistic name."""
    for token in ("signal", "export", "grade", "alert", "telegram"):
        assert token in BROKER_FIELD_TOKENS

    @dataclasses.dataclass
    class Sneaky:
        signal_export_path: str
        assigned_grade: str
        telegram_alert_target: str

    names = {f.name.lower() for f in dataclasses.fields(Sneaky)}
    offending = {n for n in names if any(t in n for t in BROKER_FIELD_TOKENS)}
    assert offending == names
