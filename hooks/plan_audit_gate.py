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
        )
        for r in man.get("requirements", [])
    ]
    verdict = evaluate_plan(reqs, out_of_scope=man.get("out_of_scope", []))
    return [f"plan_gate: {rsn.message}" for rsn in verdict.reasons], True


def main() -> None:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        _allow()
    cwd = data.get("cwd") or os.getcwd()

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
        _allow("factory-audit gate: PASSED — plan_gate clean, no open contradictions, every "
               "requirement adversarially challenged and resolved. Safe to save_snapshot.")

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
