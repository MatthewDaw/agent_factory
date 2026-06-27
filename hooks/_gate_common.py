#!/usr/bin/env python3
"""
Shared helpers for the factory Stop-hook gates.

`subagents_active()` answers: should a gate DEFER (allow the stop) right now because the agent is
legitimately yielding to wait for real Claude subagent / background-Workflow work to finish? The
gates should only ENFORCE when there is no such work in flight — otherwise they kick the supervisor
back to work the moment it tries to wait for its fanned-out builders (CONSTITUTION §0).

Two signals (Claude Code exposes no direct "subagents running" field):
  1. The Stop input carries `agent_id` ONLY when the Stop fires *inside a subagent* — a subagent
     stopping is never the supervisor finishing, so defer.
  2. The supervisor records a background Workflow it is waiting on in
     `<cwd>/.factory/awaiting-subagents.json`, including the Workflow's task `outputPath`. A running
     Workflow's output file stays EMPTY until it completes — so an empty/absent output file means
     it's still running, and the gate defers. This is liveness-verified, not a bare self-set flag:
     once the Workflow finishes (output non-empty) the marker no longer defers, and a stale marker
     (older than MAX_MARKER_AGE_S, e.g. the Workflow died) is ignored so the gate can't be disabled
     forever.

This is a background *Claude* signal only — a background *bash* task does not write this marker and
does not count.
"""

import json
import os
import time

MAX_MARKER_AGE_S = 3 * 3600  # ignore an awaiting-subagents marker older than this (stale/dead)


def subagents_active(data, cwd):
    """True if a gate should DEFER (allow the stop) because real subagent/workflow work is live."""
    try:
        # 1) This Stop is firing inside a subagent, not the supervisor finishing.
        if data.get("agent_id"):
            return True

        marker = os.path.join(cwd, ".factory", "awaiting-subagents.json")
        if not os.path.isfile(marker):
            return False

        # Stale marker (supervisor forgot to clear, or the workflow died) -> don't defer forever.
        try:
            if time.time() - os.path.getmtime(marker) > MAX_MARKER_AGE_S:
                return False
        except Exception:
            pass

        with open(marker, "r", encoding="utf-8") as fh:
            m = json.load(fh)

        for w in (m.get("workflows") or []):
            out = w.get("outputPath")
            if out:
                # output file empty or not yet created => the Workflow is still running.
                try:
                    if (not os.path.isfile(out)) or os.path.getsize(out) == 0:
                        return True
                except Exception:
                    return True  # can't stat it -> treat as running (conservative for the wait)
            elif str(w.get("status", "running")).lower() == "running":
                return True
        return False
    except Exception:
        # Fail toward ENFORCING (a broken marker must not silently disable the gates).
        return False
