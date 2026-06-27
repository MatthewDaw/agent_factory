from agent_factory.checklist_gate import (
    R_CHECK_NO_RESOLUTION,
    R_CHECK_OPEN,
    Check,
    ChecklistGate,
    evaluate_checklist,
)
from agent_factory.gate import REGISTRY


def _c(cid, status="resolved", resolution="done", **kw):
    return Check(id=cid, status=status, resolution=resolution, **kw)


def test_empty_checklist_admits():
    v = evaluate_checklist([])
    assert v.admitted
    assert v.reasons == []


def test_all_closed_with_resolution_admits():
    v = evaluate_checklist([_c("C1"), _c("C2", status="deferred"), _c("C3", status="dismissed")])
    assert v.admitted


def test_open_check_is_rejected():
    v = evaluate_checklist([_c("C1", status="open", resolution="")])
    assert not v.admitted
    assert v.rule_ids == [R_CHECK_OPEN]
    assert "C1" in v.reasons[0].message


def test_closed_without_resolution_is_rejected():
    v = evaluate_checklist([_c("C1", status="resolved", resolution="   ")])
    assert not v.admitted
    assert v.rule_ids == [R_CHECK_NO_RESOLUTION]


def test_unknown_status_is_open():
    v = evaluate_checklist([_c("C1", status="in-progress", resolution="x")])
    assert not v.admitted
    assert v.rule_ids == [R_CHECK_OPEN]


def test_status_is_normalized():
    # Case/whitespace drift must not knock a genuinely-closed check out.
    v = evaluate_checklist([_c("C1", status=" Resolved ")])
    assert v.admitted


def test_criterion_appears_in_open_message():
    v = evaluate_checklist([_c("C1", status="open", resolution="", criterion="needs password reset")])
    assert "needs password reset" in v.reasons[0].message


def test_mixed_reports_each_violation():
    v = evaluate_checklist([
        _c("C1"),                                   # ok
        _c("C2", status="open", resolution=""),     # open
        _c("C3", status="resolved", resolution=""),  # no resolution
    ])
    assert not v.admitted
    assert set(v.rule_ids) == {R_CHECK_OPEN, R_CHECK_NO_RESOLUTION}
    assert len(v.reasons) == 2


def test_gate_registered_and_dispatches_via_dict_input():
    gate = REGISTRY["checklist_gate"]
    assert isinstance(gate, ChecklistGate)
    verdict = gate.evaluate({"checks": [
        {"id": "C1", "status": "resolved", "resolution": "added R-pwd-reset"},
        {"id": "C2", "status": "open"},
    ]})
    assert not verdict.admitted
    assert verdict.rule_ids == [R_CHECK_OPEN]


def test_gate_admits_empty_checks_block():
    assert REGISTRY["checklist_gate"].evaluate({}).admitted
