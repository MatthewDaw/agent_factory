#!/usr/bin/env python3
"""
preflight gate — a Claude Code *Stop* hook.

Coding must not start until the build's environment is actually provisioned. The worker
(factory-execute Step 0) DERIVES the external dependencies this build needs from the plan's
techDecisions — credentials, API keys/secrets, reachable services (DB, queues), CLI tools,
runtimes, deploy access, whatever the plan implies (NOT a hardcoded list) — checks each, and
writes the result to <cwd>/.factory/preflight.json. This hook ENFORCES that: while any required
dependency is missing it BLOCKS the turn from ending, so the worker cannot quietly build against a
half-provisioned environment. It recomputes from the recorded checks — a self-set status:"ready"
with a missing dep does NOT pass.

Many missing deps need the USER (set an API key, log in a cloud CLI). So the block surfaces exactly
what's missing + how to provide it; the worker re-checks after the user provides them. In an
unattended run the worker may set status:"parked" (record the blockers as an episode for the owner)
so the run doesn't trap forever — that allows the stop, loudly.

Stays inert otherwise: no manifest / status not in {pending, ready, parked} => allow. FAILS OPEN.

Manifest schema (written by factory-execute Step 0) at <cwd>/.factory/preflight.json:
{
  "status": "pending" | "ready" | "parked",   // pending -> gate armed
  "project": "prd-team-app",
  "deps": [
    {"name": "DB connection", "kind": "service|credential|api-key|tool|runtime|...",
     "check": "how it was checked", "status": "present" | "missing" | "unknown" | "na",
     "remediation": "what the user must do to provide it"}
  ],
  "parkedReason": "",                  // required non-empty when status=="parked"
  "attempts": 0, "maxAttempts": 50
}
"""

import json
import os
import sys

OK = {"present", "na"}


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

    path = os.path.join(cwd, ".factory", "preflight.json")
    if not os.path.isfile(path):
        _allow()  # no preflight in progress
    try:
        with open(path, "r", encoding="utf-8") as fh:
            man = json.load(fh)
    except Exception:
        _allow()

    status = str(man.get("status", "")).lower()
    if status not in ("pending", "ready", "parked"):
        _allow()

    project = man.get("project", "<project>")
    deps = man.get("deps") or []

    # Unattended escape: parked with a reason -> allow loudly (owner must provision).
    if status == "parked":
        reason = str(man.get("parkedReason", "")).strip()
        if reason:
            _allow(f"preflight gate: PARKED ({project}) — build deferred pending owner-provisioned "
                   f"dependencies: {reason}")
        # parked without a reason falls through to the armed path.

    # Recompute from the recorded checks (a self-set status:"ready" earns nothing).
    missing = [d for d in deps if str(d.get("status", "unknown")).lower() not in OK]

    if deps and not missing:
        if status != "ready":
            man["status"] = "ready"
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(man, fh, indent=2)
            except Exception:
                pass
            _allow(f"preflight gate: READY ({project}) — all {len(deps)} required dependencies "
                   f"are provisioned; coding may proceed.")
        _allow()  # already ready -> silent

    attempts = int(man.get("attempts", 0)) + 1
    max_attempts = int(man.get("maxAttempts", 50))
    man["attempts"] = attempts

    if not deps:
        lines = ("  - no dependencies recorded yet — derive the external deps this build needs from "
                 "the plan's techDecisions (credentials, API keys/secrets, services, CLI tools, "
                 "runtimes, deploy access — whatever applies) and check each into "
                 ".factory/preflight.json")
    else:
        lines = "\n".join(
            f"  - {d.get('name','?')} [{d.get('kind','?')}]: {str(d.get('status','unknown')).upper()}"
            f" — {d.get('remediation','provide it')}" for d in missing[:40]
        )
    more = "" if len(missing) <= 40 else f"\n  ...and {len(missing) - 40} more."

    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(man, fh, indent=2)
    except Exception:
        pass

    if attempts >= max_attempts:
        man["status"] = "parked"
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(man, fh, indent=2)
        except Exception:
            pass
        _allow(f"preflight gate gave up after {attempts} attempts — {len(missing)} dependency(ies) "
               f"for {project} still unprovisioned. SURFACE TO THE USER, do not build against a "
               f"half-provisioned environment:\n{lines}{more}")

    _block(
        f"preflight gate: NOT READY. Do not start coding for {project} — the build environment is "
        f"missing {len(missing) if deps else 'its'} required dependency(ies) "
        f"(attempt {attempts}/{max_attempts}):\n{lines}{more}\n\n"
        "Provision each (or tell the user exactly what to set — API keys, cloud credentials, a "
        "running service), then re-check and update .factory/preflight.json. Only build once every "
        'dependency is "present" (or "na"). Never stub/fake a credential to get past this. In an '
        'unattended run with deps only the owner can provide, set status:"parked" with a '
        "parkedReason and record an episode."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
