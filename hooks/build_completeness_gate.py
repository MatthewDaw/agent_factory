#!/usr/bin/env python3
"""
build-completeness gate — THE SINGLE factory *Stop* hook.

This is the one and only gate of the factory's collapsed gate spine. The old preflight / wireframe /
plan-audit / review gates are GONE: everything they used to enforce is now either a ticket or a check
in Praxis, and this gate enforces the one question they all reduce to — *"are there incomplete
tickets/checks for the active build scope, and is this session in the middle of building them?"* —
LIVE against Praxis. There is no manifest. There is no ``.factory/*.json`` build/validation state.

SINGLE SOURCE OF DYNAMIC TRUTH = Praxis
---------------------------------------
The gate reads build/validation state live from Praxis via ``hooks/_praxis.py`` and
``hooks/_ticket_state.py`` (see ``docs/factory-state-contract.md`` for the canonical meta keys and
API). It writes NO local state. "A build run is active" is NOT a file flag — it is *"this session
owns a live, unfinished in_progress claim"*, read from Praxis.

ARMING (stay inert for ordinary repo conversation)
--------------------------------------------------
The gate queries the active project's incomplete requirements and asks whether THIS session owns a
live ``in_progress`` claim on any of them. A build run is active IFF this session owns such a claim.
If it owns none, no build is active for this session, so the gate ALLOWS the stop and stays inert —
ordinary conversation in a repo that merely *has* a ``prd-<project>`` is never blocked. The build
loop (factory-churn-tickets / factory-execute) is the igniter: it CLAIMS a ticket as it starts work,
which is what arms this gate for the rest of that run.

ENFORCE
-------
While this session owns one or more unfinished ``in_progress`` claims, OR (being armed) scoped
claimable incomplete tickets remain, the gate BLOCKS with an actionable message: which tickets, what
is unmet, and the lifecycle to follow — claim/heartbeat, resolve checks by query, build, record each
pass ON THE TICKET NODE, release as finished. The worker cannot end its turn mid-build.

FAIL-CLOSED
-----------
Praxis is a HARD dependency. If it is unreachable / unauthenticated / errors (``PraxisUnreachable``),
the gate BLOCKS loudly — it NEVER fails open. A gate that cannot prove build state must not let work
pass. The ONLY way out when Praxis is down is to bring Praxis up, or to set the documented, LOUD
emergency escape hatch ``FACTORY_GATE_DISABLED=1`` (never silent — it prints why it stood down).
"""

import json
import os
import sys

# The helper modules (_praxis, _ticket_state) live next to this file. A bare hook
# subprocess may be launched with an arbitrary cwd, so make sure our own directory is importable.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


# --------------------------------------------------------------------------- hook I/O

def _allow(advice: str = "") -> None:
    if advice:
        print(json.dumps({
            "hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": advice}
        }))
    sys.exit(0)


def _block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


# --------------------------------------------------------------------------- project / identity

def _active_project(cwd: str) -> str:
    """Resolve the active ``prd-<project>`` from the environment or the cwd — NEVER a manifest file.

    Order: ``FACTORY_PROJECT`` env (with or without a ``prd-`` prefix) → the basename of the cwd.
    Returns the full ``prd-<name>`` form the Praxis ``/requirements/incomplete`` endpoint expects.
    """
    raw = os.environ.get("FACTORY_PROJECT", "").strip()
    if not raw:
        raw = os.path.basename(os.path.normpath(cwd or os.getcwd()))
    raw = raw.strip()
    if not raw:
        return ""
    return raw if raw.startswith("prd-") else f"prd-{raw}"


def _session_owner(data: dict) -> str:
    """This session's claim-owner identity (matches the owner the build loop claims tickets with)."""
    return str(data.get("session_id") or data.get("sessionId") or "").strip()


# --------------------------------------------------------------------------- ticket views

def _rid(item: dict) -> str:
    for k in ("id", "factId", "fact_id", "requirement_id", "rid", "cid"):
        v = item.get(k)
        if v:
            return str(v)
    return "?"


def _label(item: dict) -> str:
    for k in ("title", "name", "summary"):
        v = item.get(k)
        if v:
            return str(v)[:80]
    text = item.get("text") or item.get("requirement") or ""
    return (str(text)[:80] or _rid(item))


def _claim_view(item: dict):
    """Return ``(owner, build_state, lease_live)`` for an incomplete-requirement item, tolerating
    either a server-derived ``claim`` view or the raw ``meta`` keys (or both)."""
    import _ticket_state as ts

    claim = item.get("claim") or {}
    meta = item.get("meta") or {}
    merged = dict(meta)
    for k, v in claim.items():
        if v is not None:
            merged[k] = v

    owner = merged.get(ts.M_CLAIM_OWNER) or claim.get("owner")
    build_state = merged.get(ts.M_BUILD_STATE) or "incomplete"
    if "lease_live" in claim:
        live = bool(claim.get("lease_live"))
    else:
        merged[ts.M_BUILD_STATE] = build_state
        live = ts._lease_live(merged)
    return (str(owner) if owner else None), str(build_state), bool(live)


def _ready_to_finish(item: dict) -> bool:
    """True iff the ticket has a pinned check contract that is fully satisfied (≥1, all passed)."""
    import _ticket_state as ts
    try:
        return ts.all_checks_passed(item if item.get("meta") else _rid(item))
    except Exception:  # noqa: BLE001 - never let an enrichment read crash the gate
        return False


# --------------------------------------------------------------------------- main

def main() -> None:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:  # noqa: BLE001
        data = {}
    cwd = data.get("cwd") or os.getcwd()

    # --- Emergency escape hatch (documented + LOUD, never silent). ----------------------------
    if os.environ.get("FACTORY_GATE_DISABLED") == "1":
        _allow("build-completeness gate STOOD DOWN: FACTORY_GATE_DISABLED=1 is set. The factory is "
               "NOT verifying build state right now — incomplete tickets/checks may remain unbuilt. "
               "Unset FACTORY_GATE_DISABLED to restore enforcement.")

    project = _active_project(cwd)
    owner = _session_owner(data)

    # --- Read the single source of dynamic truth (fail-closed). -------------------------------
    # NOTE on fan-out: a supervisor that delegated building to sub-agents owns NO live claim of its
    # own (the builders claim tickets under their own session ids), so the arming rule below leaves
    # it inert automatically — no special subagent-deferral plumbing is needed or kept.
    try:
        import _praxis
        incomplete = _praxis.incomplete_requirements(project)
    except Exception as exc:  # noqa: BLE001
        # FAIL-CLOSED: a gate that cannot reach Praxis can prove nothing, so it BLOCKS. It NEVER
        # fails open. (PraxisUnreachable is the contract signal; any import/transport failure is
        # treated identically — the truth is unavailable.)
        try:
            from _praxis import PraxisUnreachable  # noqa: F811
            is_unreachable = isinstance(exc, PraxisUnreachable)
        except Exception:  # noqa: BLE001
            is_unreachable = True
        detail = str(exc) if is_unreachable else f"{type(exc).__name__}: {exc}"
        _block(
            "build-completeness gate: PRAXIS UNREACHABLE — the factory cannot verify build state, so "
            "this gate is failing CLOSED and BLOCKING. Praxis is the single source of dynamic truth; "
            "without it there is no way to know whether tickets/checks are still incomplete.\n"
            f"  reason: {detail}\n"
            "Bring Praxis up (default http://localhost:8000; check PRAXIS_API_BASE_URL / "
            "PRAXIS_API_KEY / PRAXIS_ORG / auth) and try again. For a real emergency ONLY, set "
            "FACTORY_GATE_DISABLED=1 to stand the gate down (loud, never silent)."
        )

    if not isinstance(incomplete, list):
        incomplete = []

    # --- Partition the incomplete set by claim ownership. -------------------------------------
    owned_unfinished: list[dict] = []   # this session owns a LIVE in_progress lease on these
    claimable: list[dict] = []          # free / stale / ours — work this session may drive
    # (tickets a DIFFERENT owner holds a live lease on are neither — left to that owner)

    for item in incomplete:
        if not isinstance(item, dict):
            continue
        c_owner, build_state, live = _claim_view(item)
        if live and c_owner == owner and owner:
            owned_unfinished.append(item)
        elif live and c_owner and c_owner != owner:
            continue  # actively leased by someone else
        else:
            claimable.append(item)

    # --- ARMING: a build run is active IFF this session owns a live in_progress claim. ---------
    if not owned_unfinished:
        # No claim owned by this session => no build run is active for it => stay inert. Ordinary
        # repo conversation (even in a project with open tickets) is never blocked here.
        _allow()

    # --- ENFORCE: armed. Block until owned claims are finished AND scoped claimable work is done.
    def _fmt(items: list[dict], limit: int = 40) -> str:
        lines = []
        for it in items[:limit]:
            tail = " — checks PASSED, release as finished" if _ready_to_finish(it) else ""
            lines.append(f"  - {_rid(it)}: {_label(it)}{tail}")
        more = "" if len(items) <= limit else f"\n  ...and {len(items) - limit} more."
        return "\n".join(lines) + more

    owned_block = _fmt(owned_unfinished)
    claimable_note = ""
    if claimable:
        claimable_note = (
            f"\n\nAlso still incomplete in scope ({len(claimable)} claimable ticket(s)) — keep "
            f"churning until the whole build set is finished:\n{_fmt(claimable)}"
        )

    _block(
        f"build-completeness gate: NOT DONE for {project}. This session owns "
        f"{len(owned_unfinished)} unfinished in_progress ticket(s):\n{owned_block}"
        f"{claimable_note}\n\n"
        "Do not end the turn. Per the per-ticket lifecycle (docs/factory-state-contract.md):\n"
        "  1. heartbeat your live claim(s) so the lease stays valid;\n"
        "  2. for each owned ticket, resolve its checks by QUERY (tag union surface) and pin them;\n"
        "  3. build + validate, recording each pass ON THE TICKET NODE (record_check_pass);\n"
        "  4. when all pinned checks pass, release(state=\"finished\");\n"
        "  5. claim the next scoped incomplete ticket and repeat until none remain.\n"
        "To intentionally yield a ticket without finishing it, release(state=\"incomplete\") so its "
        "lease is dropped and this gate goes inert. (Emergency-only stand-down: FACTORY_GATE_DISABLED=1.)"
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        # A crash in the gate's own logic must not wedge the agent forever. This catches only
        # UNEXPECTED errors AFTER the fail-closed Praxis check above (which BLOCKS on its own); a
        # bug here should not masquerade as "Praxis down", so we exit cleanly (allow).
        sys.exit(0)
