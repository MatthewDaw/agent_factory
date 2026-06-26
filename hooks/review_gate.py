#!/usr/bin/env python3
"""
factory-review gate — a Claude Code *Stop* hook.

Forces a real, independent cold-eyes review to happen at a plan or work review
surface before the worker ends its turn. A SKILL.md can only *ask* the model to
convene the review panel and clear its findings; this hook *enforces* it.

Division of labor (the shared contract):
  - the factory-review SKILL fills in <cwd>/.factory/review-status.json
  - this hook ENFORCES the bar over it (pure local-file check; it never runs the
    panel itself — convening reviewers from a hook is fragile)

The manifest is ARMED upstream, not by factory-review itself: when the plan-audit
gate passes it writes a {phase:"plan", status:"pending"} manifest, and when the
build-completeness gate flips to done it writes {phase:"work", status:"pending"}.
So finalization cannot proceed without the review gate becoming armed — the
trigger is not merely prose the worker might skip.

THE BAR (recomputed from evidence every time — a self-reported status is NEVER
trusted as a free pass):
  - panelRan must be true (the independent panel actually ran), AND
  - every finding must be CLOSED: status in {resolved, accepted} AND a non-empty
    `resolution`. An open finding, or a resolved/accepted one with no resolution
    text, does NOT clear the gate — even if status=="done".
  A SKIP clears the gate only when skipReason is non-empty AND (size.small is true
  OR forceSkip is true) — so non-small / high-risk work cannot be skipped with a
  one-token reason; it needs an explicit human override (forceSkip).

Stays inert otherwise: no manifest, or status not in {pending, done, skipped} =>
allow. FAILS OPEN on any error. Loop-guarded by maxAttempts.

Manifest schema (at <cwd>/.factory/review-status.json):
{
  "phase": "plan" | "work",
  "project": "prd-team-app",
  "status": "pending" | "done" | "skipped",
  "skipReason": "",                     // REQUIRED non-empty when status=="skipped"
  "forceSkip": false,                   // explicit human override to skip non-small work
  "size": {"metric": "...", "value": 12, "threshold": 20, "small": true},
  "panelRan": true,                     // the independent cold-eyes panel actually ran
  "findings": [
    {"id": "F1", "lens": "coherence", "severity": "high"|"med"|"low",
     "summary": "...", "status": "open"|"resolved"|"accepted", "resolution": ""}
  ],
  "attempts": 0, "maxAttempts": 30
}
"""

import json
import os
import sys

CLOSED = {"resolved", "accepted"}


def _allow(advice: str = "") -> None:
    if advice:
        print(json.dumps({
            "hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": advice}
        }))
    sys.exit(0)


def _block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def _finding_open_reason(f):
    """Return None if the finding is genuinely CLOSED, else why it isn't."""
    st = str(f.get("status", "open")).lower()
    tag = f"finding {f.get('id', '?')} [{f.get('lens', '?')}/{f.get('severity', '?')}]"
    if st not in CLOSED:
        return f'{tag} is OPEN — "{f.get("summary", "?")}" (resolve it, or accept-with-reason)'
    if not str(f.get("resolution", "")).strip():
        return f'{tag} is marked {st} but has NO resolution recorded — add a non-empty resolution'
    return None


def main() -> None:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        _allow()
    cwd = data.get("cwd") or os.getcwd()

    manifest_path = os.path.join(cwd, ".factory", "review-status.json")
    if not os.path.isfile(manifest_path):
        _allow()  # not a review surface
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            man = json.load(fh)
    except Exception:
        _allow()

    status = str(man.get("status", "")).lower()
    if status not in ("pending", "done", "skipped"):
        _allow()  # unknown/terminal (e.g. "abandoned") -> fail open

    phase = man.get("phase", "<phase>")
    project = man.get("project", "<project>")
    findings = man.get("findings") or []
    panel_ran = man.get("panelRan") is True
    size = man.get("size") or {}
    small = size.get("small") is True
    force_skip = man.get("forceSkip") is True

    # --- evaluate the bar from evidence (status is NOT trusted as a free pass) ---
    misses = []
    if status == "skipped":
        reason = str(man.get("skipReason", "")).strip()
        if not reason:
            misses.append('status is "skipped" but skipReason is empty — record a non-empty '
                          "skipReason, or set status to \"pending\" and run the panel")
        elif not (small or force_skip):
            misses.append('status is "skipped" but this work is not marked small (size.small != '
                          "true) and forceSkip != true — review is MANDATORY for non-small / "
                          "high-risk work. Run the panel, or set forceSkip:true with an explicit "
                          "human-override reason in skipReason")
        if not misses:
            _allow(f"factory-review gate: SKIPPED ({phase} review for {project}) — "
                   f"{'override' if force_skip and not small else 'small work'}: {reason}")
    else:
        # pending OR done -> recompute; "done" earns nothing without the evidence.
        if not panel_ran:
            misses.append("panelRan != true — the independent cold-eyes review panel has not run "
                          "yet (need >=1 reviewer per lens)")
        for f in findings:
            why = _finding_open_reason(f)
            if why:
                misses.append(why)

        if not misses:
            if status != "done":
                man["status"] = "done"
                try:
                    with open(manifest_path, "w", encoding="utf-8") as fh:
                        json.dump(man, fh, indent=2)
                except Exception:
                    pass
            r = sum(1 for f in findings if str(f.get("status", "")).lower() == "resolved")
            a = sum(1 for f in findings if str(f.get("status", "")).lower() == "accepted")
            _allow(f"factory-review gate: PASSED — {phase} review for {project} complete; panel "
                   f"ran, {len(findings)} finding(s): {r} resolved, {a} accepted, 0 open.")

    # --- loop guard ---------------------------------------------------------
    attempts = int(man.get("attempts", 0)) + 1
    max_attempts = int(man.get("maxAttempts", 30))
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
        _allow(f"factory-review gate gave up after {attempts} attempts. {len(misses)} item(s) "
               f"still unmet for the {phase} review of {project} — SURFACE THIS TO THE USER, do "
               f"not imply the review passed:\n{lines}{more}")

    try:
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(man, fh, indent=2)
    except Exception:
        pass

    _block(
        f"factory-review gate: NOT DONE. Do not end the turn or claim the {phase} work for "
        f"{project} is reviewed. {len(misses)} item(s) unmet (attempt {attempts}/{max_attempts}):"
        f"\n{lines}{more}\n\n"
        "To clear this gate, do ONE of:\n"
        f"  1. Run the factory-review panel for the {phase} phase (>=1 independent reviewer per "
        "lens), set panelRan:true, then resolve or accept-with-reason EVERY finding (each needs a "
        'non-empty resolution). Status flips to "done" automatically once the evidence is there.\n'
        "  2. Only for genuinely small work: set status \"skipped\" with a non-empty skipReason "
        "(size.small must be true; non-small work also needs forceSkip:true as an explicit "
        "override).\n"
        "Update .factory/review-status.json as you go; only stop once this gate passes."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
