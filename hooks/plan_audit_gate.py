#!/usr/bin/env python3
"""
factory-audit gate — a Claude Code *Stop* hook.

The judgment skeptic + underspecification audit (factory-audit) runs as a SEPARATE step
over admitted-but-not-yet-blessed requirements, before `save_snapshot` blesses the plan.
A SKILL.md can only *ask* the model to do that audit; this hook *enforces* it — it blocks
the turn from ending while the audit is open and unmet, then gets out of the way.

Stays inert for everything else: does nothing unless the project has an *open* manifest at
  <cwd>/.factory/plan-audit.json
which factory-audit writes. No manifest / status != open => allow stop. FAILS OPEN on any
error — a Stop hook must never trap a user.

What it checks (a mix of independent + recorded, like the wireframe gate):
  - INDEPENDENT (can't be self-graded): re-runs agent_factory.plan_gate.evaluate_plan over the
    requirements recorded in the manifest — binary acceptance present, no vague term, no dangling
    concept reference. If the package can't be imported, this check is skipped (fail-open) and we
    fall back to the manifest's self-reported plan_gate flag.
  - RECORDED (the skill is responsible for honesty here, but the gate enforces presence):
    * contradictionsEmpty == true (skill ran praxis_get_contradictions and it was empty)
    * every requirement carries >=1 challenge, and EVERY challenge is closed
      (status in resolved/dismissed/deferred with a non-empty resolution) — no `open` challenges
    * rigorous mode: every gap-lens fired-or-passed (non-empty) for every requirement
    * technical decisions (DYNAMIC, no fixed list): `techDecisions` non-empty and every entry
      closed (resolved / deferred / na) with a decision/rationale, AND `techDecisionsCritic`
      ran with `missingFound: []` and `passes: true` (an independent pass found nothing missing)
    * test strategy (DERIVED per platform, mandatory): `testStrategy.layers` non-empty + a `ci`
      block, each closed with a binary acceptance, AND `techDecisionsCritic.testStrategyComplete`
      true (no untested/under-tested plan is blessed — Step 3a)

Manifest schema (written by factory-audit):
{
  "status": "open",                 // open -> armed; passed/abandoned -> allow
  "attempts": 0, "max_attempts": 8,
  "project": "prd-team-app",
  "mode": "rigorous",               // "quick" | "rigorous"
  "contradictionsEmpty": false,     // set true after praxis_get_contradictions returns []
  "out_of_scope": ["..."],
  "requirements": [
    {
      "id": "R1", "text": "...", "acceptance": "...",
      "defines": ["completion"], "references": ["daily rep","ratings"],
      "challenges": [
        {"type": "unhandled-empty-case", "statement": "...", "resolution": "...", "status": "resolved"}
      ],
      "gap_lenses": {"failure-modes":"fired","security":"pass","data-lifecycle":"pass","rollback":"pass","who-pays":"pass"}
    }
  ]
}
"""

import json
import os
import sys

GAP_LENSES = ("failure-modes", "security", "data-lifecycle", "rollback", "who-pays")
CLOSED = {"resolved", "dismissed", "deferred"}

# Technical decisions are DYNAMIC — derived per project by factory-audit, not a fixed checklist
# (a CLI, an ML pipeline, a web app, a game, and a library each need a different set). The gate
# therefore enforces *process*, not a hardcoded list: a non-empty enumeration, every entry closed,
# and an independent completeness critic that ran and came back with nothing missing.
TECH_CLOSED = {"resolved", "deferred", "na"}


def _allow(advice: str = "") -> None:
    if advice:
        print(json.dumps({
            "hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": advice}
        }))
    sys.exit(0)


def _block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def _plan_gate_misses(man):
    """Independent re-run of the deterministic plan gate. Returns (misses, ran)."""
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        sys.path.insert(0, os.path.join(plugin_root, "src"))
    try:
        from agent_factory.plan_gate import Requirement, evaluate_plan
    except Exception:
        return [], False  # not importable -> skip (fall back to recorded flag)
    reqs = [
        Requirement(
            id=r.get("id", "?"),
            text=r.get("text", ""),
            acceptance=r.get("acceptance", ""),
            defines=r.get("defines", []),
            references=r.get("references", []),
            source=r.get("source", ""),
        )
        for r in man.get("requirements", [])
    ]
    # Pass the bare project (strip a leading "prd-") so the R-HAS-SOURCE rule checks
    # source == "prd-<project>" exactly; if the manifest records no project, project=None
    # falls back to requiring a well-formed "prd-..." source. The manifest MUST record each
    # requirement's `source` (factory-audit §4) or this correctly flags the source-less drift.
    raw_project = man.get("project")
    project = raw_project[4:] if isinstance(raw_project, str) and raw_project.startswith("prd-") else raw_project
    verdict = evaluate_plan(reqs, out_of_scope=man.get("out_of_scope", []), project=project)
    return [f"plan_gate: {rsn.message}" for rsn in verdict.reasons], True


def _arm_review(cwd, phase, project):
    """Arm the factory-review gate for `phase` (so finalization can't skip the holistic
    review). Idempotent: leaves an existing manifest for the same phase untouched."""
    path = os.path.join(cwd, ".factory", "review-status.json")
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                if json.load(fh).get("phase") == phase:
                    return
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"phase": phase, "project": project, "status": "pending",
                       "panelRan": False, "findings": [], "size": {},
                       "attempts": 0, "maxAttempts": 30}, fh, indent=2)
    except Exception:
        pass


def main() -> None:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        _allow()
    cwd = data.get("cwd") or os.getcwd()

    # Defer (allow the stop) while real Claude subagents / a background Workflow are running — the
    # supervisor is legitimately yielding to wait for its fanned-out work (CONSTITUTION §0).
    try:
        from _gate_common import subagents_active
        if subagents_active(data, cwd):
            _allow()
    except Exception:
        pass

    manifest_path = os.path.join(cwd, ".factory", "plan-audit.json")
    if not os.path.isfile(manifest_path):
        _allow()
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            man = json.load(fh)
    except Exception:
        _allow()
    if man.get("status") != "open":
        _allow()

    misses = []
    reqs = man.get("requirements") or []
    rigorous = str(man.get("mode", "")).lower() == "rigorous"

    if not reqs:
        misses.append("no requirements recorded in the audit manifest")

    # 1) independent plan-gate re-run (or recorded fallback)
    pg_misses, ran = _plan_gate_misses(man)
    if ran:
        misses.extend(pg_misses)
    elif not man.get("planGatePass"):
        misses.append("plan_gate not independently verifiable here and planGatePass != true "
                      "(record the result of agent_factory.plan_gate.evaluate_plan)")

    # 2) contradiction queue must be empty
    if not man.get("contradictionsEmpty"):
        misses.append("contradictionsEmpty != true — run praxis_get_contradictions and resolve "
                      "every pending pair before blessing the plan")

    # 2b) technical architecture (DYNAMIC): a non-empty, fully-closed enumeration whose
    # completeness an INDEPENDENT critic has signed off on. No hardcoded dimension list — the
    # critic is what dynamically finds what's missing to build *this* system.
    tech = man.get("techDecisions") or []
    if not tech:
        misses.append("techDecisions is empty — derive the technical decisions THIS system needs "
                      "to be buildable (whatever applies: runtime, data store, auth, deploy, "
                      "packaging, model hosting, ...) and address each")
    for t in tech:
        dim = t.get("dimension", "?")
        st = str(t.get("status", "open")).lower()
        if st not in TECH_CLOSED:
            misses.append(f"tech decision '{dim}': open (status={st!r}) — resolve / defer / na")
        elif not (str(t.get("decision", "")).strip() or str(t.get("rationale", "")).strip()):
            misses.append(f"tech decision '{dim}': {st} but no decision/rationale recorded")
    critic = man.get("techDecisionsCritic") or {}
    if not critic.get("ran"):
        misses.append("techDecisionsCritic did not run — an INDEPENDENT cold-eyes pass must hunt "
                      "for technical decisions still unmade for this system")
    elif critic.get("missingFound"):
        misses.append(f"techDecisionsCritic surfaced {len(critic.get('missingFound') or [])} "
                      f"missing technical decision(s) — incorporate them, then re-run the critic")
    elif not critic.get("passes"):
        misses.append("techDecisionsCritic.passes != true — the completeness critic has not signed "
                      "off that the technical decisions are complete for this system")

    # 2c) test strategy (DERIVED per platform, MANDATORY): a non-empty set of test layers + CI,
    # each with a binary CI-enforced acceptance, and the critic confirming it's complete for THIS
    # platform. No project is blessed on an untested / under-tested plan (factory-audit Step 3a).
    ts = man.get("testStrategy") or {}
    layers = ts.get("layers") or []
    if not layers:
        misses.append("testStrategy.layers is empty — derive the platform-appropriate test layers "
                      "for THIS system (unit / integration / e2e / device-or-simulator / contract / "
                      "eval ... as fits) and give each a CI-enforced binary acceptance")
    for L in layers:
        name = L.get("layer", "?")
        st = str(L.get("status", "open")).lower()
        if st not in TECH_CLOSED:
            misses.append(f"test layer '{name}': open (status={st!r}) — resolve / defer / na")
        elif not str(L.get("acceptance", "")).strip():
            misses.append(f"test layer '{name}': {st} but no binary (CI-enforced) acceptance recorded")
    ci = ts.get("ci") or {}
    if not ci:
        misses.append("testStrategy.ci is missing — record the CI/CD setup (what runs, what it "
                      "gates) with a binary acceptance condition")
    else:
        cst = str(ci.get("status", "open")).lower()
        if cst not in TECH_CLOSED:
            misses.append(f"testStrategy.ci: open (status={cst!r}) — resolve / defer / na")
        elif not (str(ci.get("acceptance", "")).strip() or str(ci.get("decision", "")).strip()):
            misses.append("testStrategy.ci: closed but no decision/acceptance recorded")
    if not critic.get("testStrategyComplete"):
        misses.append("techDecisionsCritic.testStrategyComplete != true — the critic has not signed "
                      "off that the test strategy is complete & appropriate for this platform "
                      "(e.g. a mobile build with no device/simulator e2e layer, or any project with "
                      "no CI gate)")

    # 3) per-requirement challenge coverage + (rigorous) gap-lenses
    for r in reqs:
        rid = r.get("id", "?")
        challenges = r.get("challenges") or []
        if not challenges:
            misses.append(f"{rid}: no adversarial challenge filed (the skeptic must challenge it)")
        for c in challenges:
            st = str(c.get("status", "open")).lower()
            if st not in CLOSED:
                misses.append(f"{rid}: open challenge — \"{c.get('statement','?')}\" "
                              f"(resolve / dismiss-with-reason / defer)")
            elif not str(c.get("resolution", "")).strip():
                misses.append(f"{rid}: challenge \"{c.get('statement','?')}\" marked {st} "
                              f"but has no recorded resolution/reason")
        if rigorous:
            gl = r.get("gap_lenses") or {}
            for lens in GAP_LENSES:
                if not str(gl.get(lens, "")).strip():
                    misses.append(f"{rid}: gap-lens '{lens}' not logged (rigorous mode requires "
                                  f"fire-or-pass for every lens)")

    if not misses:
        man["status"] = "passed"
        try:
            with open(manifest_path, "w", encoding="utf-8") as fh:
                json.dump(man, fh, indent=2)
        except Exception:
            pass
        # Finalization is next (save_snapshot) — arm the holistic plan-review gate so it
        # can't be skipped. The review gate then blocks until the panel ran + findings cleared.
        _arm_review(cwd, "plan", man.get("project", "<project>"))
        _allow("factory-audit gate: PASSED — plan_gate clean, no open contradictions, every "
               "requirement adversarially challenged and resolved. Now run the plan-review "
               "(factory-review) the review_gate just armed, then save_snapshot.")

    attempts = int(man.get("attempts", 0)) + 1
    max_attempts = int(man.get("max_attempts", 8))
    man["attempts"] = attempts
    lines = "\n".join(f"  - {m}" for m in misses[:40])
    more = "" if len(misses) <= 40 else f"\n  ...and {len(misses) - 40} more."

    if attempts >= max_attempts:
        man["status"] = "abandoned"
        try:
            with open(manifest_path, "w", encoding="utf-8") as fh:
                json.dump(man, fh, indent=2)
        except Exception:
            pass
        _allow(f"factory-audit gate gave up after {attempts} attempts. {len(misses)} item(s) still "
               f"unmet — SURFACE THIS TO THE USER, do not bless the plan:\n{lines}{more}")

    try:
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(man, fh, indent=2)
    except Exception:
        pass

    _block(
        "factory-audit gate: NOT DONE. Do not save_snapshot or claim the plan is hardened. "
        f"{len(misses)} audit item(s) unmet (attempt {attempts}/{max_attempts}):\n{lines}{more}\n\n"
        "For each: file/resolve the adversarial challenge, route underspecification "
        "(research / default+episode / ask the human / defer as an owned-decision), resolve "
        "contradictions, and fix any plan_gate rejection. Update .factory/plan-audit.json as you go. "
        "Only bless the plan once this gate passes."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
