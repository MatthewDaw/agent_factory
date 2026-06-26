#!/usr/bin/env python3
"""
build-completeness gate — a Claude Code *Stop* hook.

Forces the build worker (factory-execute) to keep iterating until EVERY requirement in the
project is verified-complete. While a build is active, the worker cannot end its turn / declare
done as long as any requirement is still incomplete (never-built / regressed / stale).

Completeness is NOT self-judged: it comes from Praxis `incomplete_requirements(project)`, which is
derived from verified outcomes + staleness (PR #106). This hook is a pure *local-file* check (it
does not call Praxis itself — replicating the MCP's org/tenant auth from a hook is fragile), so the
worker is responsible for re-querying each pass and writing the honest result into the manifest.
The values can't be faked at the requirement level: a requirement only leaves the incomplete set by
actually passing factory-verify (an external signal), so "incompleteCount: 0" requires real,
verified completion of everything.

Stays inert otherwise: no manifest / status != "building" => allow stop. FAILS OPEN on any error.

Manifest schema (written/updated by factory-execute each pass) at <cwd>/.factory/build-status.json:
{
  "status": "building",        // "building" -> armed; "done"/"paused" -> allow stop
  "project": "prd-team-app",
  "checkedAt": "<pass marker>",        // bump every time you re-query (freshness)
  "incompleteCount": 5,                // from praxis_incomplete_requirements(project)
  "incomplete": [{"id": "R7", "reason": "never-built"}, ...],
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
        man["status"] = "done"
        try:
            with open(manifest_path, "w", encoding="utf-8") as fh:
                json.dump(man, fh, indent=2)
        except Exception:
            pass
        _allow(f"build-completeness gate: PASSED — incomplete_requirements({project}) is empty. "
               f"Every requirement is verified-complete; the build is done.")

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
