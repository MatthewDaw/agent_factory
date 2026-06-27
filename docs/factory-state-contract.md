# Factory State Contract

The canonical contract for the agent-factory refactor. Every other agent in this refactor reads
THIS document before touching ticket/check state. It defines the meta keys, the per-ticket
lifecycle, the check-resolution-is-a-query rule, the fail-closed rule, the auth/env surface, and the
public function signatures of `hooks/_praxis.py` and `hooks/_ticket_state.py`.

## Single source of dynamic truth

Praxis is the ONLY store of dynamic build/validation state. It holds tickets (requirements), checks,
and the outcomes/state that say what is built and what passed. Plugin code is deterministic plumbing
that reads Praxis live.

- **JSON is STATIC CONFIG ONLY.** No `json.dump` of build/validation/review/audit/preflight state.
  The `.factory/*.json` manifest pattern is being purged. These modules write NO local state files.
- **Checks are declarative + read-only during builds.** A check owns its own applicability
  predicate (`meta.applies_to` tag / bound surface). A ticket carries identity (tags, surfaces,
  semantics) but NEVER an authored list of its checks.
- **Which checks apply is a QUERY**, resolved fresh at ticket start (tag union surface against
  active checks). Never pre-bound onto the ticket.

## Fail-closed rule

Praxis is a HARD dependency. If it is unreachable / unauthenticated / errors, `_praxis` raises
`PraxisUnreachable`. A Stop-gate that catches `PraxisUnreachable` MUST BLOCK — it may never fail
open. A gate that cannot prove the truth does not let work pass.

## Auth / environment

The client (`hooks/_praxis.py`) is stdlib-only (`urllib`, `json`) so a bare hook subprocess can use
it — no `httpx`, `pycognito`, or `praxis` import.

| Env var               | Meaning                                                                 |
|-----------------------|-------------------------------------------------------------------------|
| `PRAXIS_API_BASE_URL` | Base URL. Default `http://localhost:8000`.                              |
| `PRAXIS_API_KEY`      | Preferred auth. Sent as `x-praxis-key`.                                 |
| `PRAXIS_ORG`          | Tenant org, sent as `x-praxis-org`. Default `agent-factory`.            |
| `PRAXIS_SPACE`        | Optional space, sent as `x-praxis-space` only when set.                 |
| `PRAXIS_AUTH_DISABLED`| `1` = dev seam; skip auth entirely (server has a matching seam).        |
| `COGNITO_CLIENT_ID`   | Used to mint a bearer when no API key is set.                           |
| `COGNITO_REGION`      | Cognito region for the mint. Default `us-east-1`.                       |

**Auth resolution order:** `PRAXIS_AUTH_DISABLED=1` → no auth header · else `PRAXIS_API_KEY` →
`x-praxis-key` · else mint a Cognito ID token from `~/.praxis/mcp.json`'s `refresh_token` via a raw
`InitiateAuth` REFRESH_TOKEN_AUTH call (minimal replication of `knowledge/mcp/identity.py:token()`,
without importing praxis) → `Authorization: Bearer`. If no credential is available, **fail closed.**

## Canonical meta keys (on the requirement / ticket node)

| Key                  | Type                              | Meaning                                                        |
|----------------------|-----------------------------------|----------------------------------------------------------------|
| `build_state`        | `"incomplete"｜"in_progress"｜"finished"` | The ticket's lifecycle state. Absent ≡ `incomplete`.   |
| `claim_owner`        | `str`                             | Session/agent id holding the lease.                            |
| `claim_at`           | `float` (epoch seconds)           | When this owner first claimed.                                 |
| `claim_heartbeat_at` | `float` (epoch seconds)           | Last liveness bump.                                            |
| `claim_lease_ttl`    | `int` (seconds)                   | Lease is STALE when `now - claim_heartbeat_at > claim_lease_ttl`. |
| `pinned_checks`      | `list[{check_id, passed, ran_at}]`| THIS pass's completion contract (resolved set, see below).     |

`pinned_checks` entry: `{ "check_id": str, "passed": bool｜null, "ran_at": float｜null }`
(null = not yet run). These key names align with the Praxis server's own `claim` view
(`build_state`, `claim_owner`, `claim_heartbeat_at`, `lease_live`) and lease semantics, so the
server-derived `/requirements/incomplete` view and these client writes agree.

## Per-ticket lifecycle

1. **start** — `claim` (incomplete → in_progress, stamp lease); then `resolve_checks` (the QUERY);
   then `pin_checks` which TRUNCATES any prior `pinned_checks` and writes the FRESH resolved set as
   this pass's completion contract. (`start_ticket` does all three.)
2. **build + validate** — run each pinned check; record each pass ON THE TICKET NODE via
   `record_check_pass` (never on the check fact). `heartbeat` periodically to keep the lease live.
3. **finished IFF** `all_checks_passed` (≥1 pinned check, all passed) → `release(state="finished")`.
   Yielding cleanly → `release(state="incomplete")`.

**Claiming is a LEASE, not a lock.** A stale lease (heartbeat older than ttl) is auto-reclaimable so
nothing dangles. "A build run is active" ≡ this session owns a live, unfinished `in_progress` claim,
read from Praxis — NOT a local file flag.

**Race-tolerance (v1).** `claim` is a read-modify-write over `patch_meta` (PATCH `/candidates/{cid}`,
which MERGES meta). No server-side CAS is assumed. Two agents can both claim a free/stale ticket — a
rare, HARMLESS double-claim (idempotent wasted work), not corruption.

**Note on key deletion.** `patch_meta` MERGES (it cannot delete keys), so `release` NULLs the lease
keys rather than removing them; `_lease_live` treats null heartbeat/ttl as not-live.

## Check resolution is a query (tag union surface)

`resolve_checks(ticket, project)` returns the de-duplicated union of:
- **tag match** — active `category="check"` facts whose `meta.applies_to` (array, supports `"*"`)
  contains any of the ticket's tags (`meta.tags` / `meta.applies_to`); via `facts_by`.
- **surface match** — active checks bound (via the `renders` edge) to any surface the ticket renders
  (`meta.surfaces` / `meta.screen_ids`); via `/surfaces/{screen}/checks`.

A third **semantic** lane (embedding the check predicate against the ticket text) is a documented
TODO hook, intentionally not implemented in v1.

## Public API — `hooks/_praxis.py`

```python
class PraxisUnreachable(RuntimeError): ...   # fail-closed signal; callers BLOCK

incomplete_requirements(project: str, *, exclude_leased: bool = False) -> list[dict]
# Pass the BARE project name. The endpoint prepends "prd-" itself; this fn strips a single leading
# "prd-" so an already-prefixed "prd-team-app" can never become "prd-prd-team-app" (→ empty → a
# gate that fails OPEN). Both "team-app" and "prd-team-app" resolve to bare "team-app".
get_fact(cid: str) -> dict                                  # full fact incl meta
facts_by(category: str|None = None, meta: dict|None = None, state: str = "active") -> list[dict]
patch_meta(cid: str, meta_dict: dict) -> dict               # MERGE meta (build_state/claim/pinned_checks)
record_outcome(cid: str, success: bool) -> dict
surface_checks(project: str, screen_id: str, scope: str|None = None) -> list[dict]
ping() -> bool                                              # smoke-test liveness
```

Every method raises `PraxisUnreachable` on any connection/HTTP/auth error.

## Public API — `hooks/_ticket_state.py`

```python
# canonical meta-key constants
M_BUILD_STATE, M_CLAIM_OWNER, M_CLAIM_AT, M_CLAIM_HEARTBEAT_AT, M_CLAIM_LEASE_TTL, M_PINNED_CHECKS
DEFAULT_LEASE_TTL_S = 900

resolve_checks(ticket, project: str = "") -> list[dict]      # the QUERY (tag ∪ surface)
pin_checks(cid: str, checks: list) -> dict                   # truncate + pin fresh contract
record_check_pass(cid: str, check_id: str, passed: bool, ran_at: float|None = None) -> dict
all_checks_passed(ticket) -> bool                            # ≥1 pinned AND all passed

claim(cid: str, owner: str, ttl: int = 900) -> bool          # incomplete -> in_progress (race-tolerant)
heartbeat(cid: str, owner: str) -> bool                      # bump iff still holding a live lease
release(cid: str, owner: str, state: str) -> bool            # state in {"finished","incomplete"}

start_ticket(cid: str, owner: str, project: str = "", ttl: int = 900) -> list[dict]|None  # claim+resolve+pin
```

`ticket` arguments accept either a fact id (`str`) or an already-fetched fact (`dict`). All Praxis
errors propagate as `PraxisUnreachable` (fail-closed).
