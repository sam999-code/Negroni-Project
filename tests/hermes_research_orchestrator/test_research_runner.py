"""The dry-run runner's fourteen required properties. HERMES-AUTONOMOUS-RESEARCH-002.

Nothing is started and no scheduler exists to test. The tick is called directly with injected
observations; the shell script is parsed, never executed. ``tmp_path`` stands in for the lead root.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import pathlib

import pytest

from integrations.hermes_research_orchestrator import (
    AuditRecord,
    AuditRefused,
    AutomationLevel,
    AuditOutcome,
    CandidateQueue,
    CandidateStatus,
    HermesLeadRootPolicy,
    ResearchOperation,
    RunnerDecision,
    RunnerMode,
    RunnerRefused,
    TickObservations,
    acquire_runner_lock,
    encode_candidate,
    load_audit_log,
    tick,
    volatility_normalized_session_breakout,
)
from integrations.hermes_research_orchestrator.runner import (
    AUDIT_FILE,
    DRY_RUN_REPORT_FILE,
    HEARTBEAT_FILE,
    LOCK_DIR,
    LOCK_FILE,
    QUEUE_ALLOWED_KEYS,
    QUEUE_FILE,
)

NOW = "2026-08-22T18:00:00+00:00"
RUNNER_MODULE = pathlib.Path("integrations/hermes_research_orchestrator/runner.py")
SHELL_SCRIPT = pathlib.Path("scripts/hermes_research_tick.py")


def _observations(**changes) -> TickObservations:
    fields = dict(observed_at=NOW, tests_passing=True, native_gateway_running=False,
                  gateway_port_open=False)
    fields.update(changes)
    return TickObservations(**fields)


def _seed_queue(lead_root, *candidates) -> pathlib.Path:
    policy = HermesLeadRootPolicy.owning(lead_root)
    queue = CandidateQueue(policy=policy)
    queue.bind_path(lead_root / QUEUE_FILE)
    for candidate in candidates:
        queue.append(candidate)
    return lead_root / QUEUE_FILE


def _approved(candidate=None):
    proposed = candidate or volatility_normalized_session_breakout()
    return dataclasses.replace(
        proposed, status=CandidateStatus.OWNER_APPROVED_RESEARCH,
        owner_approved_for_research=True, owner_gate_required=False,
        next_action="verify data availability and the cost model")


def _tick(lead_root, **obs_changes) -> dict:
    return tick(lead_root=lead_root, observations=_observations(**obs_changes),
                pid=4242, start_token="test-token")


# -- 1..3: no loop, dry-run default, no scheduler ------------------------------------------------

@pytest.mark.parametrize("module", [RUNNER_MODULE, SHELL_SCRIPT], ids=lambda p: p.name)
def test_the_runner_contains_no_unbounded_loop_and_no_loop_at_all_over_time(module):
    """No ``while`` of any kind. A tick that wanted to wait would be a tick that wanted to be a
    daemon, and keeping something running is the owner's act, not this code's."""
    for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
        assert not isinstance(node, ast.While), f"{module} contains a while loop"


def test_dry_run_is_the_default_and_the_only_mode():
    assert [m.value for m in RunnerMode] == ["DRY_RUN"]
    assert RunnerMode.DRY_RUN.starts_research is False
    # The shell's parser accepts exactly one choice and defaults to it.
    tree = ast.parse(SHELL_SCRIPT.read_text(encoding="utf-8"))
    mode_defaults = [kw.value.value for node in ast.walk(tree)
                     if isinstance(node, ast.Call)
                     and getattr(node.func, "attr", "") == "add_argument"
                     and any(isinstance(a, ast.Constant) and a.value == "--mode"
                             for a in node.args)
                     for kw in node.keywords if kw.arg == "default"]
    assert mode_defaults == ["DRY_RUN"]


@pytest.mark.parametrize("module", [RUNNER_MODULE, SHELL_SCRIPT], ids=lambda p: p.name)
def test_the_runner_installs_no_scheduler_and_registers_nothing(module):
    """The words are absent, not guarded. This mirrors the package firewall, which already sweeps
    runner.py; the shell is outside that glob and gets the same sweep here."""
    tree = ast.parse(module.read_text(encoding="utf-8"))
    constants = {node.value.lower() for node in ast.walk(tree)
                 if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    names = {node.id.lower() for node in ast.walk(tree) if isinstance(node, ast.Name)}
    for banned in ("schtasks", "register-scheduledtask", "start" + "up"):
        assert not any(banned in c for c in constants | names), f"{module} names {banned}"


# -- 4..5: gateway and port pause ----------------------------------------------------------------

def test_a_running_native_gateway_pauses_the_tick_with_governance_risk(tmp_path):
    _seed_queue(tmp_path, volatility_normalized_session_breakout(), _approved())
    summary = _tick(tmp_path, native_gateway_running=True)
    assert summary["decisions"] == {
        "EVOLITH-RESEARCH-CANDIDATE-001": RunnerDecision.PAUSED_GOVERNANCE_RISK.value}
    assert summary["heartbeat"]["state"] == "paused"
    assert summary["heartbeat"]["native_gateway_running"] is True


def test_an_open_gateway_port_pauses_the_tick_with_governance_risk(tmp_path):
    _seed_queue(tmp_path, _approved())
    summary = _tick(tmp_path, gateway_port_open=True)
    assert summary["decisions"] == {
        "EVOLITH-RESEARCH-CANDIDATE-001": RunnerDecision.PAUSED_GOVERNANCE_RISK.value}
    assert summary["heartbeat"]["gateway_port_open"] is True


# -- 6..7: bad queue lines reject the tick -------------------------------------------------------

def test_a_queue_line_without_a_skill_bundle_is_rejected(tmp_path):
    document = json.loads(encode_candidate(volatility_normalized_session_breakout()))
    del document["selected_skill_bundle"]
    (tmp_path / QUEUE_FILE).write_text(json.dumps(document) + "\n", encoding="utf-8")
    summary = _tick(tmp_path)
    assert summary["decisions"] == {}                      # nothing evaluated over a bad ledger
    assert len(summary["rejected_lines"]) == 1
    assert summary["heartbeat"]["rejected_count"] == 1


def test_a_queue_line_with_a_forbidden_or_unknown_key_is_rejected(tmp_path):
    document = json.loads(encode_candidate(volatility_normalized_session_breakout()))
    document["broker_login"] = "12345"
    (tmp_path / QUEUE_FILE).write_text(json.dumps(document) + "\n", encoding="utf-8")
    summary = _tick(tmp_path)
    assert summary["decisions"] == {}
    assert "FORBIDDEN_OR_UNKNOWN_KEY" in summary["rejected_lines"][0]["reason"]
    assert "broker_login" in summary["rejected_lines"][0]["reason"]


def test_the_key_allowlist_is_pinned_to_the_schema_and_cannot_drift_silently():
    document = json.loads(encode_candidate(volatility_normalized_session_breakout()))
    assert QUEUE_ALLOWED_KEYS == frozenset(document)


# -- 8..10: approval, data, cost model -----------------------------------------------------------

def test_an_unapproved_candidate_cannot_run_and_awaits_the_owner(tmp_path):
    _seed_queue(tmp_path, volatility_normalized_session_breakout())
    summary = _tick(tmp_path, required_data_present=True, cost_model_present=True)
    assert summary["decisions"] == {
        "EVOLITH-RESEARCH-CANDIDATE-001": RunnerDecision.OWNER_APPROVAL_REQUIRED.value}


def test_missing_data_returns_data_required(tmp_path):
    _seed_queue(tmp_path, volatility_normalized_session_breakout(), _approved())
    summary = _tick(tmp_path, required_data_present=False, cost_model_present=True)
    assert summary["decisions"] == {
        "EVOLITH-RESEARCH-CANDIDATE-001": RunnerDecision.DATA_REQUIRED.value}


def test_missing_cost_model_returns_cost_model_required(tmp_path):
    _seed_queue(tmp_path, volatility_normalized_session_breakout(), _approved())
    summary = _tick(tmp_path, required_data_present=True, cost_model_present=False)
    assert summary["decisions"] == {
        "EVOLITH-RESEARCH-CANDIDATE-001": RunnerDecision.COST_MODEL_REQUIRED.value}


# -- 11..13: writes stay home, no signal export, authority NONE ----------------------------------

def test_the_tick_writes_only_the_allowed_files_inside_the_lead_root(tmp_path):
    lead = tmp_path / "lead"
    lead.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _seed_queue(lead, _approved())
    _tick(lead)
    written = {str(p.relative_to(lead)).replace("\\", "/")
               for p in lead.rglob("*") if p.is_file()}
    assert written == {QUEUE_FILE, HEARTBEAT_FILE, AUDIT_FILE, DRY_RUN_REPORT_FILE}
    assert list(outside.iterdir()) == []                   # nothing escaped the root
    assert not (lead / LOCK_DIR / LOCK_FILE).exists()      # released, not leaked


def test_the_tick_writes_no_signal_export(tmp_path):
    _seed_queue(tmp_path, _approved())
    _tick(tmp_path)
    names = {p.name.lower() for p in tmp_path.rglob("*")}
    assert not any("signal" in n or "summary" in n for n in names)


def test_the_heartbeat_and_audit_state_authority_none_and_a_record_cannot_state_otherwise(tmp_path):
    _seed_queue(tmp_path, _approved())
    summary = _tick(tmp_path)
    assert summary["heartbeat"]["execution_authority"] == "NONE"
    log = load_audit_log(tmp_path / AUDIT_FILE, HermesLeadRootPolicy.owning(tmp_path))
    assert log.records and all(r.execution_authority == "NONE" for r in log.records)
    with pytest.raises(AuditRefused, match="EXECUTION_AUTHORITY_ASSERTED"):
        AuditRecord(record_id="X", occurred_at=NOW,
                    level=AutomationLevel.LEVEL_1_SUPERVISED,
                    operation=ResearchOperation.MAINTAIN_CANDIDATE_QUEUE,
                    outcome=AuditOutcome.PERMITTED, detail="x",
                    governance_digest="0" * 64, execution_authority="FULL")


# -- 14: candidate 001 stays research-only -------------------------------------------------------

def test_candidate_001_remains_research_only_through_a_tick(tmp_path):
    """No decision token promises anything, no promising state is reachable, and the queue file is
    byte-identical after the tick -- the runner reads the ledger and never advances it."""
    path = _seed_queue(tmp_path, volatility_normalized_session_breakout(), _approved())
    before = path.read_bytes()
    summary = _tick(tmp_path, required_data_present=True, cost_model_present=True)
    assert path.read_bytes() == before
    assert set(summary["decisions"].values()) <= {d.value for d in RunnerDecision}
    assert "PROMISING" not in {d.value for d in RunnerDecision}.__str__()
    report = json.loads((tmp_path / DRY_RUN_REPORT_FILE).read_text(encoding="utf-8"))
    for entry in report["entries"]:
        assert entry["would_start"] is False


# -- the tick itself -----------------------------------------------------------------------------

def test_a_clean_approved_candidate_is_accepted_for_research_design(tmp_path):
    _seed_queue(tmp_path, _approved())
    summary = _tick(tmp_path, required_data_present=True, cost_model_present=True)
    assert summary["decisions"] == {
        "EVOLITH-RESEARCH-CANDIDATE-001": RunnerDecision.DRY_RUN_OK.value}
    assert summary["heartbeat"]["accepted_count"] == 1
    assert summary["heartbeat"]["state"] == "idle"


def test_the_heartbeat_counts_always_sum_to_the_candidate_count(tmp_path):
    _seed_queue(tmp_path, volatility_normalized_session_breakout())
    heartbeat = _tick(tmp_path)["heartbeat"]
    assert (heartbeat["accepted_count"] + heartbeat["paused_count"]
            + heartbeat["rejected_count"] + heartbeat["awaiting_owner_or_inputs_count"]
            ) == heartbeat["candidate_count"] == 1


def test_the_tick_number_advances_and_the_audit_log_accumulates(tmp_path):
    _seed_queue(tmp_path, _approved())
    assert _tick(tmp_path)["tick"] == 1
    assert _tick(tmp_path)["tick"] == 2
    log = load_audit_log(tmp_path / AUDIT_FILE, HermesLeadRootPolicy.owning(tmp_path))
    assert [r.record_id for r in log.records] == [
        "TICK-0001-EVOLITH-RESEARCH-CANDIDATE-001", "TICK-0002-EVOLITH-RESEARCH-CANDIDATE-001"]
    assert all(r.selected_skill_bundle for r in log.records)


def test_failing_tests_return_failed_tests(tmp_path):
    _seed_queue(tmp_path, _approved())
    summary = _tick(tmp_path, tests_passing=False)
    assert summary["decisions"] == {
        "EVOLITH-RESEARCH-CANDIDATE-001": RunnerDecision.FAILED_TESTS.value}


def test_a_dirty_protected_path_pauses_the_tick(tmp_path):
    _seed_queue(tmp_path, _approved())
    summary = _tick(tmp_path, git_dirty_protected_paths=("integrations/x.py",))
    assert summary["decisions"] == {
        "EVOLITH-RESEARCH-CANDIDATE-001": RunnerDecision.PAUSED_GOVERNANCE_RISK.value}


def test_a_foreign_lock_refuses_the_tick_and_is_never_broken(tmp_path):
    policy = HermesLeadRootPolicy.owning(tmp_path)
    acquire_runner_lock(policy, tmp_path, pid=1, start_token="someone-else", acquired_at=NOW)
    with pytest.raises(RunnerRefused, match="CONFLICTING_LOCK"):
        _tick(tmp_path)
    holder = json.loads((tmp_path / LOCK_DIR / LOCK_FILE).read_text(encoding="utf-8"))
    assert holder["start_token"] == "someone-else"         # still theirs


def test_the_runner_ceiling_is_level_1_even_with_a_valid_marker(tmp_path):
    """Owner decision 2, structural: LEVEL_2 needs the marker AND an owner-ordered ceiling change."""
    from integrations.hermes_research_orchestrator.levels import (
        APPROVAL_MARKER_NAME, APPROVED_DIGEST_KEY, governance_matrix_digest)
    (tmp_path / APPROVAL_MARKER_NAME).write_text(
        f"{APPROVED_DIGEST_KEY}: {governance_matrix_digest()}", encoding="utf-8")
    _seed_queue(tmp_path, _approved())
    summary = _tick(tmp_path, required_data_present=True, cost_model_present=True)
    assert summary["level"] == AutomationLevel.LEVEL_1_SUPERVISED.value
