"""U4: gate_result emission helper + verify-adapter contract fit.

Emission rides the existing ``gate_result`` event type (no vocabulary change) and the
verify adapter proves an external-signal gate conforms to the same Gate types as
plan_gate without adopting its structured input.
"""

from agent_factory.event_log import EVENT_TYPES, EventLog
from agent_factory.gate import (
    REGISTRY,
    Reason,
    Verdict,
    emit_gate_result,
    verify_adapter,
)


def test_emit_gate_result_appends_one_gate_result_event(tmp_path):
    log = EventLog("emit-probe", root=tmp_path)
    verdict = REGISTRY["plan_gate"].evaluate(
        {"requirements": [{"id": "R1", "text": "x", "acceptance": ""}]}
    )
    rec = emit_gate_result(log, "plan_gate", verdict, task_id="task-1")

    assert rec["type"] == "gate_result"
    assert "gate_result" in EVENT_TYPES
    assert rec["component"] == "plan_gate"
    assert rec["admitted"] is False
    assert rec["rule_ids"] == ["R-ACCEPT-BINARY"]
    assert rec["task_id"] == "task-1"

    events = log.read()
    assert len([e for e in events if e["type"] == "gate_result"]) == 1


def test_emit_is_opt_in_no_log_no_event(tmp_path):
    # Evaluating without passing a log emits nothing (pure unit eval stays log-free).
    log = EventLog("emit-optin", root=tmp_path)
    REGISTRY["plan_gate"].evaluate({"requirements": []})
    assert log.read() == []


def test_verify_adapter_failing_test_signal_rejects():
    verdict = verify_adapter({"tests": False, "lint": True})
    assert isinstance(verdict, Verdict)
    assert verdict.admitted is False
    assert verdict.rule_ids == ["R-TESTS"]
    assert all(isinstance(r, Reason) for r in verdict.reasons)
    assert verdict.reasons[0].rule_id == "R-TESTS"


def test_verify_adapter_all_pass_admits():
    verdict = verify_adapter({"tests": True, "build": True, "lint": True})
    assert verdict.admitted is True
    assert verdict.rule_ids == []
