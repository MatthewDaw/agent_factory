"""The generic checklist gate: enforce that every check in a Praxis-sourced checklist is
closed-with-evidence (Milestone: data-driven planning gate, docs/coverage-spine/02-planner.md).

This is the deterministic core of the coverage spine on the *gate* side. The factory's gates
already enforce "every item in a set is closed with non-empty evidence" (challenges, findings,
tech decisions); this generalizes that pattern so the **set of items comes from Praxis** instead
of being hard-coded (the ``GAP_LENSES`` tuple in ``plan_audit_gate``). A skill pulls the
applicable checklist from the Praxis ``planning`` checklist and writes each check into the
manifest; this module enforces closure over them, recomputed from evidence — never a self-flag.

Pushing the enforcement into tested code (rather than a hard-coded loop in the Stop hook) is the
thin-harness discipline: adding a check is *data in Praxis*, and the rule that every check must
be addressed is *executable and eval-covered* here.

Rules (each unmet check is a rejection reason, never a silent pass):
- **Open check (R-CHECK-OPEN)** — a check whose ``status`` is not closed
  (closed = ``resolved`` / ``dismissed`` / ``deferred``) is unmet.
- **No resolution (R-CHECK-NO-RESOLUTION)** — a closed check with no recorded ``resolution``
  text is unmet (closing a check requires saying *how* it was addressed).
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_factory.gate import Reason, Verdict, register

# Stable rule-IDs (KTD5) — part of the gate's public contract; matched by field, not parsed.
R_CHECK_OPEN = "R-CHECK-OPEN"                  # a check is not closed
R_CHECK_NO_RESOLUTION = "R-CHECK-NO-RESOLUTION"  # a closed check has no recorded resolution

#: A check is closed only via one of these states (mirrors the audit/review CLOSED sets).
CLOSED = {"resolved", "dismissed", "deferred"}


@dataclass
class Check:
    """One checklist item as the skill hands it to the gate (pulled from Praxis).

    ``id`` and ``criterion`` identify the check; ``status``/``resolution`` are the closure
    evidence the skill records. ``angle``/``severity``/``applies_to`` are optional metadata
    carried from the Praxis fact (``meta.angle`` / ``meta.severity`` / ``meta.applies_to``);
    they don't affect the verdict but ride along for messaging and downstream selection.
    """

    id: str
    criterion: str = ""
    status: str = "open"
    resolution: str = ""
    angle: str = ""
    severity: str = "med"
    applies_to: str = ""


def evaluate_checklist(checks: list[Check]) -> Verdict:
    """Admit only when every check is closed with a non-empty resolution.

    Each violation contributes a structured :class:`~agent_factory.gate.Reason` (rule-ID +
    human-readable message). An empty checklist admits (no items to close) — emptiness policy
    (e.g. "the skill must have pulled at least the applicable checks") belongs to the caller,
    not this primitive.
    """
    reasons: list[Reason] = []
    for c in checks:
        status = c.status.strip().lower()
        label = c.id or c.criterion or "?"
        if status not in CLOSED:
            detail = f" — {c.criterion}" if c.criterion else ""
            reasons.append(
                Reason(R_CHECK_OPEN, f"check '{label}': open (status={status!r}) "
                                     f"— resolve / dismiss-with-reason / defer{detail}")
            )
        elif not c.resolution.strip():
            reasons.append(
                Reason(R_CHECK_NO_RESOLUTION,
                       f"check '{label}': marked {status} but has no recorded resolution")
            )
    return Verdict(admitted=not reasons, reasons=reasons)


class ChecklistGate:
    """The checklist gate as a :class:`~agent_factory.gate.Gate` implementation.

    ``evaluate`` accepts a component ``input`` block carrying a ``checks`` list of dicts
    (the shape a manifest records), builds :class:`Check` objects, and delegates to
    :func:`evaluate_checklist`. Registered under ``"checklist_gate"`` so the eval harness and
    the Stop hooks reach it via the registry.
    """

    def evaluate(self, input: dict) -> Verdict:  # noqa: A002 - contract name
        checks = [
            Check(
                id=str(c.get("id", "")),
                criterion=str(c.get("criterion", "")),
                status=str(c.get("status", "open")),
                resolution=str(c.get("resolution", "")),
                angle=str(c.get("angle", "")),
                severity=str(c.get("severity", "med")),
                applies_to=str(c.get("applies_to", "")),
            )
            for c in input.get("checks", [])
        ]
        return evaluate_checklist(checks)


register("checklist_gate", ChecklistGate())
