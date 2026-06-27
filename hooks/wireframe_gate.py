#!/usr/bin/env python3
"""
factory-wireframe coverage gate — a Claude Code *Stop* hook.

Purpose: a wireframe build is only "done" when every requirement on its own
checklist is present in the produced HTML and no navigation link is dead. A
SKILL.md can only *ask* the model to self-audit; this hook *enforces* it — it
blocks the agent from ending its turn until the checklist passes, then gets out
of the way.

How it stays inert for everything else
--------------------------------------
This hook fires on EVERY Stop in EVERY session once the plugin is installed.
It does nothing unless the current project contains an *open* manifest at
  <cwd>/.factory/wireframe-checklist.json
which `factory-wireframe` writes during a build. No manifest (or status != open)
=> exit 0, allow stop. It also FAILS OPEN: any error => allow stop. A Stop hook
must never trap a user, so every exit path that isn't a deliberate block is 0.

Manifest schema (written by the skill)
---------------------------------------
{
  "status": "open",                  // open -> the gate is armed
  "attempts": 0,                     // gate-managed loop guard
  "max_attempts": 8,                 // give up (fail open) after this many blocks
  "outputs": ["wireframe-player.html", "wireframe-admin.html"],  // files, rel to cwd
  "requirements": [
    {
      "id": "A2",                    // PRD id/section to cite
      "desc": "invite generate / revoke / usage",
      "markers": ["invite", "revoke"],   // ALL must appear (case-insensitive) ...
      "in": "wireframe-admin.html",      // ... in this output (omit = any output)
      "waived": false,                   // set true + "reason" to legitimately drop
      "reason": ""
    }
  ]
}

The gate also checks that every go('X') / go("X", ...) navigation target in each
output file has a matching element id="s-X" (no dead links).
"""

import json
import os
import re
import sys


def _allow(advice: str = "") -> None:
    """Permit the stop. Optionally surface non-blocking advice to the model."""
    if advice:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "Stop",
                "additionalContext": advice,
            }
        }))
    sys.exit(0)


def _block(reason: str) -> None:
    """Refuse the stop and feed `reason` back to the model so it keeps working."""
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def main() -> None:
    # --- read hook input; fail open on anything unexpected -------------------
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

    manifest_path = os.path.join(cwd, ".factory", "wireframe-checklist.json")
    if not os.path.isfile(manifest_path):
        _allow()  # not a wireframe build — none of our business

    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            man = json.load(fh)
    except Exception:
        _allow()

    if man.get("status") != "open":
        _allow()  # already passed / abandoned

    outputs = man.get("outputs") or []
    reqs = man.get("requirements") or []

    # --- load output files ---------------------------------------------------
    blobs = {}
    missing_files = []
    for rel in outputs:
        p = os.path.join(cwd, rel)
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                blobs[rel] = fh.read()
        except Exception:
            missing_files.append(rel)

    misses = []  # (id, desc, why)

    if missing_files:
        for rel in missing_files:
            misses.append(("(file)", rel, "declared output file does not exist yet"))

    # --- requirement coverage ------------------------------------------------
    for r in reqs:
        if r.get("waived"):
            continue
        rid = r.get("id", "?")
        desc = r.get("desc", "")
        markers = r.get("markers") or []
        target = r.get("in")
        if target and target in blobs:
            haystacks = [blobs[target].lower()]
        else:
            haystacks = [b.lower() for b in blobs.values()]
        if not haystacks:
            misses.append((rid, desc, "no output file to search"))
            continue
        for m in markers:
            ml = str(m).lower()
            if not any(ml in h for h in haystacks):
                misses.append((rid, desc, f'marker "{m}" not found'))
                break

    # --- dead-link check: every go('X') target needs an id="s-X" -------------
    nav = re.compile(r"""go\(\s*['"]([A-Za-z0-9_\-]+)['"]""")
    for rel, blob in blobs.items():
        targets = set(nav.findall(blob))
        for t in targets:
            if (f'id="s-{t}"' not in blob) and (f"id='s-{t}'" not in blob):
                misses.append(("(nav)", f"{rel}: go('{t}')",
                               f'dead link — no element id="s-{t}"'))

    # --- verdict -------------------------------------------------------------
    if not misses:
        man["status"] = "passed"
        try:
            with open(manifest_path, "w", encoding="utf-8") as fh:
                json.dump(man, fh, indent=2)
        except Exception:
            pass
        _allow("factory-wireframe coverage gate: PASSED — every checklist "
               "requirement is present and all navigation links resolve.")

    # loop guard: never trap the user forever
    attempts = int(man.get("attempts", 0)) + 1
    max_attempts = int(man.get("max_attempts", 8))
    man["attempts"] = attempts

    lines = [f"  - [{rid}] {desc} — {why}" for rid, desc, why in misses[:40]]
    body = "\n".join(lines)
    more = "" if len(misses) <= 40 else f"\n  ...and {len(misses) - 40} more."

    if attempts >= max_attempts:
        man["status"] = "abandoned"
        try:
            with open(manifest_path, "w", encoding="utf-8") as fh:
                json.dump(man, fh, indent=2)
        except Exception:
            pass
        _allow(
            f"factory-wireframe coverage gate gave up after {attempts} attempts. "
            f"{len(misses)} item(s) still unmet — SURFACE THIS TO THE USER rather "
            f"than implying completeness:\n{body}{more}"
        )

    try:
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(man, fh, indent=2)
    except Exception:
        pass

    _block(
        "factory-wireframe coverage gate: NOT DONE. Do not end the turn or claim "
        f"the wireframe is complete. {len(misses)} checklist item(s) are unmet "
        f"(attempt {attempts}/{max_attempts}):\n"
        f"{body}{more}\n\n"
        "For each: add the missing requirement/state/screen to the wireframe HTML "
        "(or fix the dead link). If an item is genuinely out of scope, edit its "
        'entry in .factory/wireframe-checklist.json to set "waived": true with a '
        '"reason" -- do not silently delete it. Then finish.'
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # absolute backstop: a Stop hook must never trap the user.
        sys.exit(0)
