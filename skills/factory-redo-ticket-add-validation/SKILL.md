---
name: factory-redo-ticket-add-validation
description: >
  Add a live validation check to Praxis AND regress every ticket that check matches BY QUERY, so the
  build loop must re-do them until the check passes. Use to enforce a new "this must be proven before
  the ticket counts done" rule — e.g. "auth tickets need a live Playwright login test", "the checkout
  flow needs an e2e payment test". It declares the rule + flips the matching tickets back to
  incomplete; it does NOT build or fix anything (the build run does that).
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

THIS SKILL'S ROLE IN THE NEW MODEL: Add a check + regress the tickets it MATCHES BY QUERY (set their meta.build_state=incomplete / record_outcome failed) — never by writing a check list onto the ticket. No JSON.

---

# Factory Redo-Ticket / Add Validation — add a check AND regress the tickets it matches

> For the lighter "just declare the check, touch no ticket" move, use **`factory-add-validation`**.
> This skill additionally regresses the tickets the check matches **by query**, so the build loop must
> re-claim them and force them re-done until the new check passes.

One explicit call that turns *"I want `<X>` proven before `<class-of-tickets>` can count done"* into:
one declarative `category="check"` fact in **Praxis** **plus** the matching tickets flipped back to
`meta.build_state="incomplete"`. The build loop (FIND→CLAIM→RESOLVE→BUILD→VERIFY→FINISH) then re-claims
them, re-RESOLVES the fresh check set, re-PINS it onto each ticket, and gates FINISH on every pinned
check passing — so the ticket cannot re-finish until this check passes. This skill **only** declares +
regresses; it never builds, claims, pins, or verifies.

Praxis is the single source of dynamic truth and a HARD dependency. If any Praxis call fails, **stop and
surface the error** — do not silently continue, and never fall back to a file.

## What a check is (read this first)

A check is **declarative and read-only during builds**. It **owns its own applicability predicate** —
`meta.applies_to` is an **array** of class tags (supporting `"*"` for all) and/or it binds to surfaces.
The ticket carries identity (`meta.tags`, `meta.surfaces`/`meta.screen_ids`) but **never an authored
list of its checks**. Which checks apply to a ticket is the RESOLVE-step **query** (tag ∪ surface
against active checks), resolved fresh at ticket start by the build — so you NEVER write a check list
onto a ticket, here or anywhere.

## Infer the spec from the user's one-liner

Pull three things (ask once only if genuinely ambiguous; otherwise infer):
- **criterion** — what must be true (e.g. "login works against the live service"); this is the fact text.
- **run** — the command that proves it, non-zero exit = fail (discover the repo's real e2e command; don't assume).
- **applies_to** — a list of requirement-class tags (e.g. `["auth"]`) and/or specific requirement id(s).

E.g. *"auth tickets need a live playwright login test"* → `applies_to: ["auth"]`,
`run: "npx playwright test …login…"`, `criterion: "login works end-to-end against the live service"`.

## Steps (all via `factory-memory`; no files, ever)

1. **Declare the check in Praxis.**
   `praxis_add_insight(insight="<criterion>", source="prd-<project>", category="check",
   scope="validation", meta={"check_id":"<stable-slug>", "applies_to":["<class-tag …>"],
   "run":"<command>"}, on_conflict="surface")`. Idempotent: if a check with the same `meta.check_id`
   already exists, `praxis_edit_fact` it instead of duplicating. `applies_to` is the check's OWN
   predicate — keep it an array.

2. **Resolve the regression set by the SAME query the build's RESOLVE step uses** (tag ∪ surface) —
   never by writing anything onto the check or hand-listing checks on tickets:
   - **tag match** — requirements whose `meta.tags` (or `meta.applies_to`) intersect the check's
     `meta.applies_to`; find via `praxis_facts_by(category="requirement", meta=...)`.
   - **surface match** — requirements that render any surface the check binds to
     (`praxis_requirements_for_surface` / `praxis_checks_for_surface`).
   - **explicit ids** — if the user named requirement id(s), use them directly.
   If a target requirement does not yet carry the class tag, add it to its `meta.tags` via
   `praxis_edit_fact` (this is the ticket's **identity**, not a check list) so the query keeps matching
   it on the next build. Preserve all existing meta when editing.

3. **Regress each matching ticket back to incomplete** — this is the FIND-set re-entry, done by ticket
   STATE only. For every requirement in the resolved set:
   - set `meta.build_state="incomplete"` (`praxis_edit_fact`, merging meta — preserve everything else), AND
   - `praxis_record_outcome(fact_id, success=False)` so it re-enters `incomplete_requirements`
     (which is derived from outcomes + staleness).
   A never-built ticket is already incomplete — leave it. **Do NOT touch `meta.pinned_checks`,
   `meta.claim_owner`/`meta.claim_at`/`meta.claim_heartbeat_at`/`meta.claim_lease_ttl`, or anything on
   the check fact** — the build's RESOLVE/PIN steps re-pin the fresh check set (including this new one)
   at the next ticket start; the pass contract is formed there, not here.

4. **Confirm + report.** Run `praxis_incomplete_requirements(<project>)` — passing the **BARE** project
   name (never `prd-<project>`, which returns EMPTY and would falsely report "all built"). Report: the
   check you declared (id, applies_to, run), the tickets you regressed (id + text), and that they now
   show incomplete. If any Praxis call failed, report the failure instead of claiming success.

After this, the next build run CLAIMs each regressed ticket, RESOLVEs checks (tag ∪ surface) fresh,
PINs the resulting set onto the ticket node, and gates FINISH on every pinned check passing — so the
ticket cannot re-finish until this check's `run` exits zero.

## Never

- **Never write or read a file** — no `.factory/*.json` manifest, no `validations.yaml`, no local
  state of any kind. The check, the tickets' tags, and `build_state` live ONLY in Praxis.
- **Never write a check list onto a ticket.** Applicability is the check's predicate, resolved by the
  build's RESOLVE query. You only set ticket **identity** (tags) and ticket **state** (`build_state` /
  outcome).
- **Never touch `pinned_checks` or the claim lease here**, and never edit check facts other than the
  one you declare. The build owns RESOLVE, CLAIM, PIN, and per-check pass records.
- **Never build or fix code**, and never regress requirements outside the resolved target set.
