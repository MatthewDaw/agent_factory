"""The plan done-gate: a deterministic verifier the factory-plan skill runs before
admitting a PRD (Milestone 1a).

The skill (an LLM) drafts each requirement and tags it with the concepts it
*defines* and the concepts it *references*; this module then mechanically checks
the closure properties that prose review keeps missing. Pushing the gate into
tested code (rather than leaving it as skill prose) is the thin-harness
discipline: the rules below are the same ones the skill claims to enforce, but
here they are executable and covered by evals.

Rules enforced (each failure is a rejection reason, never a silent pass):

- **Binary acceptance** — every requirement needs a non-empty acceptance
  condition. ("every requirement maps to >=1 binary acceptance condition.")
- **No vague terms** — a requirement may not use an unquantified vague term
  (fast, secure, scalable, most-users, ...) without a measurable threshold.
- **No dangling concept reference (H14)** — every concept a requirement
  *references* must be *defined* by some admitted requirement or explicitly
  declared out of scope. This is the gap that let an undefined "team streak"
  slip into prd-team-app: R2 referenced it, no requirement defined it, and the
  prose gate admitted R2 anyway.

Contradiction detection (zero unresolved contradictions) is delegated to Praxis
(`praxis_get_contradictions`) and is not re-implemented here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from agent_factory.gate import Reason, Verdict, register

# Stable rule-IDs (KTD5). Each emitted reason carries the constant for the rule that
# produced it, so coverage/harvesting attribute a verdict to a rule by field, not by
# parsing the message prose. These strings are part of the gate's public contract.
R_ACCEPT_BINARY = "R-ACCEPT-BINARY"  # every requirement maps to >=1 binary acceptance
R_NO_VAGUE = "R-NO-VAGUE"            # no unquantified vague term without a threshold
R_NO_DANGLING = "R-NO-DANGLING"      # every referenced concept is defined or out of scope

# Vague qualifiers that must be replaced with a measurable threshold before a
# requirement is admitted. Matched as whole words/phrases, case-insensitively.
VAGUE_TERMS = (
    "fast",
    "quickly",
    "slow",
    "secure",
    "scalable",
    "performant",
    "robust",
    "reliable",
    "most users",
    "most-users",
    "user-friendly",
    "intuitive",
    "soon",
    "lots of",
)


@dataclass
class Requirement:
    """One requirement as the plan skill hands it to the gate.

    ``defines`` are the domain concepts this requirement introduces (lower-cased
    for matching); ``references`` are the concepts it depends on. The skill is
    responsible for populating these; the gate verifies their closure.
    """

    id: str
    text: str
    acceptance: str = ""
    defines: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)


# The gate's decision type is the shared contract :class:`Verdict` (reasons carry a
# structured ``rule_id``). ``GateVerdict`` is kept as a backward-compatible alias.
GateVerdict = Verdict


def _norm(concept: str) -> str:
    return concept.strip().lower()


def _vague_terms_in(text: str) -> list[str]:
    low = text.lower()
    return [t for t in VAGUE_TERMS if re.search(rf"\b{re.escape(t)}\b", low)]


def evaluate_plan(
    requirements: list[Requirement], out_of_scope: list[str] | None = None
) -> Verdict:
    """Run the done-gate over a PRD's requirements; return admit/reject + reasons.

    Admits only when every rule passes for every requirement. Each violation
    contributes a structured :class:`Reason` (rule-ID + human-readable message) so the
    skill can report exactly what the human must fix and coverage can attribute the
    verdict to a rule. The admit/reject decision and message text are unchanged from the
    earlier string-reason form — only the reason carrier gained its ``rule_id`` field.
    """
    reasons: list[Reason] = []
    defined = {_norm(c) for r in requirements for c in r.defines}
    oos = {_norm(c) for c in (out_of_scope or [])}
    known = defined | oos

    for r in requirements:
        if not r.acceptance.strip():
            reasons.append(
                Reason(R_ACCEPT_BINARY, f"{r.id}: no binary acceptance condition")
            )

        for term in sorted(set(_vague_terms_in(f"{r.text} {r.acceptance}"))):
            reasons.append(
                Reason(
                    R_NO_VAGUE,
                    f"{r.id}: vague term '{term}' without a measurable threshold",
                )
            )

        for ref in r.references:
            if _norm(ref) not in known:
                reasons.append(
                    Reason(
                        R_NO_DANGLING,
                        f"{r.id}: dangling reference to undefined concept '{ref}' "
                        f"(define it in a requirement or declare it out of scope)",
                    )
                )

    return Verdict(admitted=not reasons, reasons=reasons)


class PlanGate:
    """The plan done-gate as a :class:`~agent_factory.gate.Gate` implementation.

    ``evaluate`` accepts a component ``input`` block (the case ``input``: a list of
    ``requirements`` and optional ``out_of_scope``), builds :class:`Requirement` objects,
    and delegates to :func:`evaluate_plan`. Registered under ``"plan_gate"`` so the eval
    harness reaches it only via the registry.
    """

    def evaluate(self, input: dict) -> Verdict:  # noqa: A002 - contract name
        requirements = [
            Requirement(
                id=r["id"],
                text=r.get("text", ""),
                acceptance=r.get("acceptance", ""),
                defines=r.get("defines", []),
                references=r.get("references", []),
            )
            for r in input.get("requirements", [])
        ]
        return evaluate_plan(requirements, out_of_scope=input.get("out_of_scope", []))


register("plan_gate", PlanGate())
