---
name: factory-churn-tickets
description: >
  Start churning through unfinished tickets: run the factory build loop over this project's
  prd-<project> plan and drive incomplete requirements (never-built, regressed, or stale — including
  any a validation check just regressed) to done. With NO argument it drives the WHOLE build set to
  completeness; with a scope argument (e.g. "auth", or "only the unfinished auth tickets") it targets
  ONLY the matching incomplete tickets and leaves the rest alone. The "go work unfinished" entry point
  (not for planning new work).
---

## How work flows (this factory's methodology — read first)

State lives in ONE place: Praxis. There are no JSON status files, no locks on disk, no self-set "done"
flags. A ticket (requirement) and a check are Praxis facts; everything about what is built/claimed/passed
is state ON THE TICKET'S Praxis node. To do ANY unit of work you follow exactly this loop:

1. FIND   — query Praxis for the next incomplete ticket in scope (incomplete = never-built | regressed |
            stale, derived from recorded outcomes). Pass the BARE project name (e.g. "team-app"); the
            endpoint adds the "prd-" prefix itself — passing "prd-team-app" returns EMPTY and silently
            hides all work.
2. CLAIM  — atomically set the ticket's meta.build_state="in_progress" with claim_owner=you + a heartbeat.
            The claim is a LEASE: refresh the heartbeat while working; a stale lease auto-reclaims so a
            dead agent never strands a ticket. Parallel agents never double-work because a live claim is
            visible to all.
3. RESOLVE— determine which checks this ticket must pass by QUERY (its tag ∪ its surfaces ∪ semantic
            match against active checks). The ticket NEVER stores its own check list. Truncate any prior
            per-check state, then PIN the freshly-resolved set onto the ticket as this pass's contract.
4. BUILD  — do the work to satisfy the ticket's acceptance condition.
5. VERIFY — run each pinned check; record each pass ON THE TICKET NODE (never on the check — checks are
            read-only during builds). External signals only; never self-judge.
6. FINISH — only when EVERY pinned check passed: record a succeeded outcome and release the lease
            (build_state="finished"). If any check fails, record a failed outcome — that regresses the
            ticket so it re-enters the FIND set and is re-done.

Praxis is a HARD dependency: if it is unreachable the factory STOPS (the gate blocks) — it never proceeds
on a guess. The single Stop gate (build_completeness) enforces this loop: it blocks the turn from ending
while you hold an unfinished claim or scoped incomplete tickets remain.

In this skill: this IS the entry loop. Claim an incomplete ticket (lease/heartbeat), resolve its checks
via QUERY, build, verify each pinned check by recording the pass on the TICKET NODE, release it finished —
and drive that loop until no claimable incomplete ticket remains in scope. "Build-active" means owning a
live `in_progress` claim; there is no `.factory/*.json` to read or write.

---

# Factory Churn Tickets — drive the (optionally scoped) build set to done

The explicit entry point for *"address unfinished work."* It is the **FIND → CLAIM → RESOLVE → BUILD →
VERIFY → FINISH** loop above, run until no claimable incomplete ticket remains in scope. **Praxis is the
single source of dynamic truth.** Every meta key referenced here is defined in
`docs/factory-state-contract.md` and surfaced through `hooks/_praxis.py` + `hooks/_ticket_state.py` —
read that contract and conform to it exactly.

**Fail-closed.** Praxis is a HARD dependency. If `_praxis` raises `PraxisUnreachable`, STOP — never assume
a ticket is done, never proceed past a gate. A loop that cannot reach the truth does not invent it.

## Scope (optional — this is the whole point of the argument)
- **No argument** (`/factory-churn-tickets`) → drive the **WHOLE incomplete set** to done. Default.
- **A scope argument** (`/factory-churn-tickets auth` · "only the unfinished auth tickets") → claim
  and build **ONLY** the incomplete tickets matching that scope; leave every other ticket alone **even
  if it is also incomplete**. Resolve the scope to a requirement set, in this order: a **class tag**
  (match `meta.tags`), explicit **requirement ids**, or a named **area** (semantic/text match via
  `factory-memory` — e.g. "auth" → login, signup, logout, JWT/session, password reset, authz). **List
  exactly which tickets you selected** before building, so the scope is explicit. Report the non-scoped
  incomplete tickets as parked — surfaced, never silently skipped, but not claimed this run.

## Do
1. **Identify the project.** Use the BARE project name for this repo (e.g. `team-app`, NOT
   `prd-team-app`). The incomplete endpoint prepends `prd-` itself; a prefixed name returns EMPTY and a
   gate would wrongly believe every build is complete.
2. **FIND — get the live incomplete set.** Call `_praxis.incomplete_requirements(project)` — the server
   derives this view from outcomes + staleness + lease state, so a validation check that just regressed
   a ticket already shows up here (no local sync, no manifest). To skip tickets another live session
   already holds, pass `exclude_leased=True`. If a scope was given, filter this set to the scoped subset.
3. **CLAIM + RESOLVE — lease and pin checks in one step.** For the next claimable ticket call
   `_ticket_state.start_ticket(cid, owner, project)`. This atomically: (a) `claim` — flips `build_state`
   `incomplete → in_progress` and stamps `claim_owner` / `claim_at` / `claim_heartbeat_at` /
   `claim_lease_ttl` via the race-tolerant PATCH merge; (b) `resolve_checks` — the QUERY (tag ∪ surface
   against active checks) that decides which checks apply *fresh, now*; (c) `pin_checks` — TRUNCATES any
   prior `pinned_checks` and writes the freshly resolved set as **this pass's completion contract** on
   the TICKET NODE. `start_ticket` returns the pinned check list (or `None` if a live lease already holds
   it — skip it). The check set is **never pre-authored on the ticket**; it is always re-derived here.
4. **BUILD + VERIFY — do the work and record each check pass on the TICKET NODE.** Build the ticket (via
   `factory-execute` for the single-decision build). For every pinned check, run it and call
   `_ticket_state.record_check_pass(cid, check_id, passed, ran_at)` — passes are recorded **on the
   ticket**, never on the check fact (checks are read-only during builds). Call
   `_ticket_state.heartbeat(cid, owner)` periodically during long work so the lease stays live and the
   ticket is not auto-reclaimed as stale.
5. **FINISH — release only when every pinned check passed.** When `_ticket_state.all_checks_passed(cid)`
   is true (≥1 pinned check, all passed), call `_praxis.record_outcome(cid, True)` and
   `_ticket_state.release(cid, owner, state="finished")`. If a check failed, record the failed outcome so
   the ticket regresses back into the FIND set. If you must yield without finishing,
   `release(cid, owner, state="incomplete")` so the lease drops and the ticket returns to the claimable
   pool — nothing dangles.
6. **LOOP.** Re-query `incomplete_requirements(project)` (filtered to scope) and repeat from step 3 until
   no claimable incomplete ticket remains in scope. Independent tickets may be fanned out across parallel
   sessions/workflows — the lease makes that safe (a rare double-claim is harmless wasted work, not
   corruption).
7. **Report** the tickets finished this run AND, when scoped, the parked non-scoped incomplete tickets
   left untouched — nothing hidden.

## Completeness
*"Are we done?"* is **not** a counter you maintain. The single `build_completeness` Stop gate answers it
live against Praxis: *are there incomplete tickets/checks for this scope?* When the scoped set has no
claimable incomplete ticket and every pinned check on the built tickets passed, the gate is satisfied. A
review/audit finding is not a separate state machine — it is just another Praxis ticket or check that
shows up incomplete and gets claimed and built like any other.

## Never
- **Never** write or read any `.factory/*.json` manifest, build-status file, or "awaiting subagents"
  flag. Dynamic state lives ONLY in Praxis. If you reach for a JSON state file, you are reintroducing the
  deleted bug.
- **Never** mark a ticket finished without `all_checks_passed(cid)` true — every pinned check passed,
  recorded on the ticket node.
- **Never** author or pre-bind a ticket's check list. Which checks apply is always the fresh query in
  `start_ticket`; pinning truncates and re-derives.
- **Never** record a check pass on the check fact — passes go on the TICKET NODE.
- **Never** proceed when `_praxis` raises `PraxisUnreachable`. Fail closed: stop, surface the error.
- **Never** start a new plan or add requirements here — this only finishes existing tickets.
- **Never** build a ticket outside the requested scope; if the scope is ambiguous, list your selection
  and ask before churning. The parked non-scoped incomplete tickets MUST appear in the report — scoping
  is explicit, never a silent under-build.
