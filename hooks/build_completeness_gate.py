#!/usr/bin/env python3
"""
build-completeness gate — a Claude Code *Stop* hook.

Forces the build worker (factory-execute) to keep iterating until every requirement in the
**build target** is verified-complete. While a build is active, the worker cannot end its turn /
declare done as long as any build-target requirement is still incomplete (never-built / regressed /
stale).

Completeness is NOT self-judged: it comes from Praxis `incomplete_requirements(project)`, which is
derived from verified outcomes + staleness (PR #106). The worker partitions that set with
`select_build_target` (src/agent_factory/build_target.py) so the forced loop targets ONLY the build
set — `mvp` + `automated` requirements. This hook is a pure *local-file* check (it does not call
Praxis itself — replicating the MCP's org/tenant auth from a hook is fragile), so the worker is
responsible for re-querying + re-partitioning each pass and writing the honest result into the
manifest. The values can't be faked at the requirement level: a requirement only leaves the
incomplete set by actually passing factory-verify (an external signal), so "incompleteCount: 0"
requires real, verified completion of the whole build set.

`incompleteCount`/`incomplete` are scoped to the build target (mvp+automated) — NOT all active
requirements. `deferred_manual` (mvp, human-verified) and `excluded_post_mvp` requirements are
recorded separately for transparency and never block the gate; `needs_triage` (mis-tagged) is
surfaced so a human resolves the tag rather than the loop silently auto-building it.

Stays inert otherwise: no manifest / status != "building" => allow stop. FAILS OPEN on any error.

Manifest schema (written/updated by factory-execute each pass) at <cwd>/.factory/build-status.json:
{
  "status": "building",        // "building" -> armed; "done"/"paused" -> allow stop
  "project": "prd-team-app",
  "checkedAt": "<pass marker>",        // bump every time you re-query (freshness)
  "incompleteCount": 5,                // count over the BUILD TARGET ONLY (mvp+automated still incomplete)
  "incomplete": [{"id": "R7", "reason": "never-built"}, ...],   // the build-target incompletes
  // --- transparency only; recorded but NEVER counted toward incompleteCount / the block ---
  "deferredManual": [{"id": "R20"}, ...],      // mvp + manual-verify: parked, surfaced to the human
  "excludedPostMvp": [{"id": "R47"}, ...],     // post-mvp: out of scope for this build
  "needsTriage": [{"id": "R31"}, ...],         // mis-tagged (unknown tier/verify): must NOT be silently built
  "attempts": 0, "maxAttempts": 200    // generous backstop so a truly-stuck build can't trap forever
}
"""

import json
import os
import sys


def _allow(advice: str = "") -> None:
    if advice:
        print(json.dumps({
            "hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": advice}
        }))
    sys.exit(0)


def _block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


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

    manifest_path = os.path.join(cwd, ".factory", "build-status.json")
    if not os.path.isfile(manifest_path):
        _allow()
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            man = json.load(fh)
    except Exception:
        _allow()

    # "paused"/"done" -> the worker is deliberately yielding; only "building" is armed.
    if man.get("status") != "building":
        _allow()

    project = man.get("project", "<project>")
    count = man.get("incompleteCount")
    incomplete = man.get("incomplete") or []

    # Transparency-only groups: surfaced in advisories, never counted toward the block.
    deferred_manual = man.get("deferredManual") or []
    excluded_post_mvp = man.get("excludedPostMvp") or []
    needs_triage = man.get("needsTriage") or []

    def _transparency_note() -> str:
        bits = []
        if deferred_manual:
            bits.append(f"{len(deferred_manual)} deferred-manual (parked for the human)")
        if excluded_post_mvp:
            bits.append(f"{len(excluded_post_mvp)} excluded post-MVP")
        if needs_triage:
            bits.append(f"{len(needs_triage)} NEEDS-TRIAGE (mis-tagged — resolve before relying on this build)")
        return "" if not bits else "\nOut of build target: " + "; ".join(bits) + "."

    # Missing/odd count => force a re-query rather than letting it slide.
    if not isinstance(count, int):
        attempts = int(man.get("attempts", 0)) + 1
        man["attempts"] = attempts
        try:
            with open(manifest_path, "w", encoding="utf-8") as fh:
                json.dump(man, fh, indent=2)
        except Exception:
            pass
        _block(f"build-completeness gate: no current incompleteCount recorded for {project}. "
               f"Re-run praxis_incomplete_requirements(\"{project}\") and write the result into "
               f".factory/build-status.json before stopping.")

    if count <= 0:
        # The build set is verified-complete — but the plan is NOT done until it is DEPLOYED and
        # the deployment verified, UNLESS the user explicitly opted out. Deployment is a hard gate.
        dep = man.get("deployment") or {}
        required = dep.get("required") is not False  # default True; only an explicit False opts out
        dep_status = str(dep.get("status", "pending")).lower()
        opt_out_reason = str(dep.get("optOutReason", "")).strip()
        if required and dep_status != "verified":
            attempts = int(man.get("attempts", 0)) + 1
            man["attempts"] = attempts
            try:
                with open(manifest_path, "w", encoding="utf-8") as fh:
                    json.dump(man, fh, indent=2)
            except Exception:
                pass
            _block(
                f"build-completeness gate: build set for {project} is verified-complete, but the "
                f"plan is NOT done until it is DEPLOYED and verified (deployment.status is "
                f"'{dep_status}', not 'verified'). Deploy to the techDecisions target, verify the "
                f"deployment is reachable/healthy, and set deployment.status='verified' in "
                f".factory/build-status.json. To skip deployment you need the USER's explicit "
                f"opt-out: deployment.required=false WITH a deployment.optOutReason — never skip it "
                f"on your own." + _transparency_note())
        man["status"] = "done"
        try:
            with open(manifest_path, "w", encoding="utf-8") as fh:
                json.dump(man, fh, indent=2)
        except Exception:
            pass
        # Build finished — arm the holistic work-review gate before "shipped".
        _arm_review(cwd, "work", project)
        deploy_note = (f" Deployment: VERIFIED." if (required and dep_status == "verified")
                       else f" Deployment: opted out ({opt_out_reason or 'no reason given'})."
                       if not required else "")
        _allow(f"build-completeness gate: PASSED — the build target (mvp+automated) for {project} "
               f"is empty; every targeted requirement is verified-complete.{deploy_note} Now run "
               f"the work-review (factory-review) the review_gate just armed before shipping."
               + _transparency_note())

    attempts = int(man.get("attempts", 0)) + 1
    max_attempts = int(man.get("maxAttempts", 200))
    man["attempts"] = attempts

    lines = "\n".join(
        f"  - {r.get('id','?')} ({r.get('reason','?')})" for r in incomplete[:40]
    )
    more = "" if len(incomplete) <= 40 else f"\n  ...and {len(incomplete) - 40} more."

    if attempts >= max_attempts:
        man["status"] = "stuck"
        try:
            with open(manifest_path, "w", encoding="utf-8") as fh:
                json.dump(man, fh, indent=2)
        except Exception:
            pass
        _allow(f"build-completeness gate gave up after {attempts} attempts: {count} requirement(s) "
               f"in {project} are still incomplete. SURFACE THIS TO THE USER — do not imply the "
               f"build is done:\n{lines}{more}")

    try:
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(man, fh, indent=2)
    except Exception:
        pass

    _block(
        f"build-completeness gate: NOT DONE. {count} requirement(s) in {project} are still "
        f"incomplete (attempt {attempts}/{max_attempts}):\n{lines}{more}\n\n"
        "Keep building: pick the next incomplete requirement, build it, gate it through "
        "factory-verify, and record its outcome (praxis_record_outcome) — then re-query "
        f"praxis_incomplete_requirements(\"{project}\") and update .factory/build-status.json. "
        "Do not end the turn or claim the build is complete until that query returns empty. "
        "(To intentionally yield, set status to \"paused\" in the manifest.)"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
