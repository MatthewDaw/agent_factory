#!/usr/bin/env python3
"""
Per-ticket lifecycle helpers, built on :mod:`_praxis`. Pure plumbing — deterministic, reads/writes
Praxis live, holds NO state of its own (no JSON manifests). This module defines the CANONICAL meta
keys for a ticket's build lifecycle; see ``docs/factory-state-contract.md``.

A TICKET is a requirement fact in the ``prd-<project>`` graph. It carries identity (tags, surfaces,
semantics) but NEVER an authored list of its checks. WHICH CHECKS APPLY is a QUERY, resolved fresh
at ticket start against the active ``check`` facts (tag union surface). The resolved set is PINNED
onto the ticket node (``meta.pinned_checks``) as that pass's completion contract; the ticket is
finished IFF every pinned check passed.

Lifecycle (see contract doc):
  start  -> truncate prior pinned_checks, resolve_checks(), pin_checks()
  claim  -> incomplete => in_progress + lease stamps (race-tolerant; see below)
  build/validate -> record_check_pass() per pinned check
  done   -> all_checks_passed() AND release(state="finished")

CANONICAL META KEYS (on the requirement/ticket node):
  build_state          : "incomplete" | "in_progress" | "finished"
  claim_owner          : str   (session/agent id holding the lease)
  claim_at             : float (epoch seconds, when first claimed)
  claim_heartbeat_at   : float (epoch seconds, last liveness bump)
  claim_lease_ttl      : int   (seconds; lease is stale when now - heartbeat > ttl)
  pinned_checks        : list[ {check_id: str, passed: bool|None, ran_at: float|None} ]

RACE-TOLERANCE (v1)
-------------------
Claiming is a read-modify-write over ``patch_meta`` (PATCH /candidates/{cid}, which MERGES meta).
There is NO server-side CAS here: we read the live lease, decide locally, then write. Two agents can
therefore both decide a stale/free ticket is theirs and both write — a rare double-claim. That is
HARMLESS wasted work (idempotent rebuild), not corruption, so v1 accepts it. The lease is a LEASE,
not a lock: a lease whose heartbeat is older than its ttl is auto-reclaimable, so nothing dangles.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import _praxis
from _praxis import PraxisUnreachable  # re-exported so gates import one place  # noqa: F401

CHECK_CATEGORY = "check"

# Canonical meta keys.
M_BUILD_STATE = "build_state"
M_CLAIM_OWNER = "claim_owner"
M_CLAIM_AT = "claim_at"
M_CLAIM_HEARTBEAT_AT = "claim_heartbeat_at"
M_CLAIM_LEASE_TTL = "claim_lease_ttl"
M_PINNED_CHECKS = "pinned_checks"

_LEASE_KEYS = (M_CLAIM_OWNER, M_CLAIM_AT, M_CLAIM_HEARTBEAT_AT, M_CLAIM_LEASE_TTL)

DEFAULT_LEASE_TTL_S = 900  # 15 min


# --------------------------------------------------------------------------- helpers

def _meta(ticket: Any) -> dict:
    """Extract the meta dict from a ticket id (str) or an already-fetched fact (dict)."""
    if isinstance(ticket, str):
        ticket = _praxis.get_fact(ticket)
    return dict((ticket or {}).get("meta") or {})


def _ticket_id(ticket: Any) -> str:
    if isinstance(ticket, str):
        return ticket
    cid = (ticket or {}).get("id") or (ticket or {}).get("factId")
    if not cid:
        raise ValueError("ticket fact has no id")
    return str(cid)


def _as_list(v: Any) -> list:
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple)) else [v]


def _check_id(check: Any) -> str:
    if isinstance(check, str):
        return check
    return str((check or {}).get("id") or (check or {}).get("check_id") or "")


# --------------------------------------------------------------------------- check resolution

def resolve_checks(ticket: Any, project: str = "") -> list[dict]:
    """Resolve WHICH active checks apply to ``ticket`` — a fresh QUERY, never a pre-bound list.

    Tag union surface:
      * TAG match — for each tag on the ticket (meta.tags / meta.applies_to identity), enumerate
        active ``check`` facts whose ``meta.applies_to`` contains that tag (array-membership; the
        check owns its own applicability predicate, incl. a ``"*"`` wildcard the server matches).
      * SURFACE match — for each surface the ticket renders (meta.surfaces / meta.screen_ids),
        enumerate active checks bound to that surface via the ``renders`` edge.

    Returns the de-duplicated union of matching check facts.

    TODO(semantic): a third lane — semantic/embedding match of the check's predicate against the
    ticket's text — is intentionally left as a documented hook. Tag+surface is the v1 contract.
    """
    meta = _meta(ticket)
    seen: dict[str, dict] = {}

    tags = _as_list(meta.get("tags")) + _as_list(meta.get("applies_to"))
    for tag in {str(t) for t in tags if t}:
        for chk in _praxis.facts_by(category=CHECK_CATEGORY, meta={"applies_to": tag}):
            cid = _check_id(chk)
            if cid:
                seen.setdefault(cid, chk)

    surfaces = _as_list(meta.get("surfaces")) + _as_list(meta.get("screen_ids")) \
        + _as_list(meta.get("screen_id"))
    if project:
        for screen in {str(s) for s in surfaces if s}:
            try:
                for chk in _praxis.surface_checks(project, screen):
                    cid = _check_id(chk)
                    if cid:
                        seen.setdefault(cid, chk)
            except PraxisUnreachable:
                raise
            except Exception:  # noqa: BLE001 - a malformed surface entry must not drop tag matches
                continue

    return list(seen.values())


# --------------------------------------------------------------------------- pinning

def pin_checks(cid: str, checks: list) -> dict:
    """TRUNCATE prior per-check state and PIN a FRESH resolved set onto the ticket node.

    Writes ``meta.pinned_checks`` as a list of fresh {check_id, passed=None, ran_at=None} entries.
    Because patch_meta replaces the ``pinned_checks`` value wholesale, this is the truncation: any
    prior pass results are discarded — the new set is THIS pass's completion contract.
    """
    pinned = [{"check_id": _check_id(c), "passed": None, "ran_at": None}
              for c in checks if _check_id(c)]
    return _praxis.patch_meta(cid, {M_PINNED_CHECKS: pinned})


def record_check_pass(cid: str, check_id: str, passed: bool,
                      ran_at: Optional[float] = None) -> dict:
    """Record one check's pass/fail ON THE TICKET NODE (never on the check fact).

    Read-modify-write of ``meta.pinned_checks``: update the matching entry's passed/ran_at. If the
    check is not already pinned (resolved set drifted), it is appended so the result is not lost.
    """
    if ran_at is None:
        ran_at = time.time()
    meta = _meta(cid)
    pinned = list(meta.get(M_PINNED_CHECKS) or [])
    found = False
    for entry in pinned:
        if str(entry.get("check_id")) == str(check_id):
            entry["passed"] = bool(passed)
            entry["ran_at"] = ran_at
            found = True
            break
    if not found:
        pinned.append({"check_id": str(check_id), "passed": bool(passed), "ran_at": ran_at})
    return _praxis.patch_meta(cid, {M_PINNED_CHECKS: pinned})


def all_checks_passed(ticket: Any) -> bool:
    """True IFF the ticket has at least one pinned check AND every pinned check passed.

    A ticket with no pinned checks returns False — completion requires a resolved contract, never
    "no checks therefore done". (An intentionally check-free ticket should pin an explicit set.)
    """
    pinned = list(_meta(ticket).get(M_PINNED_CHECKS) or [])
    if not pinned:
        return False
    return all(bool(e.get("passed")) for e in pinned)


# --------------------------------------------------------------------------- claiming / lease

def _lease_live(meta: dict, now: Optional[float] = None) -> bool:
    """True iff the ticket is in_progress with a non-stale heartbeat (now - hb <= ttl)."""
    if now is None:
        now = time.time()
    if meta.get(M_BUILD_STATE) != "in_progress":
        return False
    hb = meta.get(M_CLAIM_HEARTBEAT_AT)
    ttl = meta.get(M_CLAIM_LEASE_TTL)
    if hb is None or ttl is None:
        return False
    try:
        return (now - float(hb)) <= float(ttl)
    except (TypeError, ValueError):
        return False


def claim(cid: str, owner: str, ttl: int = DEFAULT_LEASE_TTL_S) -> bool:
    """Claim a ticket (incomplete -> in_progress) for ``owner``, race-tolerantly.

    Read the live lease, then claim IFF the ticket is free to claim: not in_progress, OR ``owner``
    already holds it (idempotent renew), OR the existing lease is STALE (auto-reclaim). On success
    stamps claim_owner/claim_at/claim_heartbeat_at/claim_lease_ttl and sets build_state=in_progress.
    Returns True if we now hold the lease, False if a DIFFERENT owner holds a LIVE lease.

    Race note: two agents can both read a free ticket and both write — a rare, harmless double-claim
    (see module docstring). No server CAS is assumed.
    """
    meta = _meta(cid)
    now = time.time()
    if _lease_live(meta, now) and meta.get(M_CLAIM_OWNER) != owner:
        return False  # a different owner holds a live lease
    held_at = meta.get(M_CLAIM_AT)
    if meta.get(M_CLAIM_OWNER) != owner or held_at is None:
        held_at = now  # first claim by this owner stamps claim_at
    _praxis.patch_meta(cid, {
        M_BUILD_STATE: "in_progress",
        M_CLAIM_OWNER: owner,
        M_CLAIM_AT: held_at,
        M_CLAIM_HEARTBEAT_AT: now,
        M_CLAIM_LEASE_TTL: int(ttl),
    })
    return True


def heartbeat(cid: str, owner: str) -> bool:
    """Bump ``claim_heartbeat_at`` IFF ``owner`` still holds a live lease. Returns success.

    If the lease has gone stale or been taken over, returns False without writing — the owner has
    lost the lease and should re-claim (or yield).
    """
    meta = _meta(cid)
    if meta.get(M_CLAIM_OWNER) != owner or not _lease_live(meta):
        return False
    _praxis.patch_meta(cid, {M_CLAIM_HEARTBEAT_AT: time.time()})
    return True


def release(cid: str, owner: str, state: str) -> bool:
    """Release ``owner``'s lease and set a terminal build_state ("finished" or "incomplete").

    Drops the lease keys (so nothing dangles) and stamps build_state, MERGING so identity keys
    (tags/surfaces/pinned_checks) survive. Only the holding owner may release; a mismatch returns
    False without writing. ``patch_meta`` cannot delete keys, so lease keys are NULLED out.
    """
    if state not in ("finished", "incomplete"):
        raise ValueError("state must be 'finished' or 'incomplete'")
    meta = _meta(cid)
    if meta.get(M_CLAIM_OWNER) not in (owner, None):
        return False
    patch: dict[str, Any] = {M_BUILD_STATE: state}
    for k in _LEASE_KEYS:
        patch[k] = None  # MERGE can't remove keys; null them so _lease_live reads not-live
    _praxis.patch_meta(cid, patch)
    return True


# --------------------------------------------------------------------------- start

def start_ticket(cid: str, owner: str, project: str = "",
                 ttl: int = DEFAULT_LEASE_TTL_S) -> Optional[list[dict]]:
    """Convenience: claim, then truncate+resolve+pin in one call.

    Returns the pinned check facts on success, or None if the claim was lost to another live owner.
    """
    if not claim(cid, owner, ttl=ttl):
        return None
    checks = resolve_checks(cid, project=project)
    pin_checks(cid, checks)
    return checks
