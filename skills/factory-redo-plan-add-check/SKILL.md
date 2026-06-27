---
name: factory-redo-plan-add-check
description: >
  Insert a planning check into Praxis AND re-arm the plan audit so the new lens is enforced against
  the already-admitted requirements of prd-<project>. The planning-side analog of
  factory-redo-ticket-add-validation. Use when a "we should have considered X" rule must be applied
  to a plan that's already hardened.
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

In this skill: Add a planning check + re-arm the plan audit via Praxis (the panel-ran episode model), not a JSON manifest.

# Factory Redo-Plan / Add Planning Check — declare a lens AND re-arm the audit

Same write as `factory-add-planning-check` (the lens is a check fact in Praxis, never a file), plus
it **re-arms the plan audit** so the panel must convene again and close the new lens for the existing
requirements — the planning analog of regressing a ticket.

Praxis is the single source of dynamic truth and a HARD dependency: every step here reads/writes
Praxis live via `factory-memory`. If Praxis is unreachable, STOP (fail-closed) — never proceed on a
stale or assumed plan state. **No file is written or edited.**

## Steps

1. **Insert the planning check into Praxis** — exactly as `factory-add-planning-check`. Via
   `factory-memory`:

   ```
   praxis_add_insight(
     insight  = "<criterion>",
     source   = "planning-checklist",
     category = "check",
     scope    = "planning",
     meta     = { "check_id": "<stable-slug>", "angle": "<lens>", "applies_when": "<condition | empty>" },
     on_conflict = "surface",
   )
   ```

   A check owns its own applicability predicate (`meta.applies_when` / `angle`) — it is declarative and
   read-only during builds. Idempotent on `meta.check_id`: if a check with that id already exists,
   `praxis_edit_fact` it instead of duplicating. The active `category="check"`, `scope="planning"` facts
   ARE the planning checklist — `factory-audit` resolves it fresh by QUERY at audit start, never from an
   authored list, and never pre-bound onto any requirement.

2. **Re-arm the audit (panel-ran episode model).** The ONLY audit residue in this model is a small
   **"panel-ran" Praxis EPISODE** asserting the audit convened for `prd-<project>` — there is no
   findings state machine, no manifest, no `.factory/*.json`. Adding a new planning check makes the
   latest panel-ran episode STALE: it covered a checklist that no longer includes this lens. Make that
   explicit so the audit cannot be silently treated as still-passed — record the re-arm episode via
   `factory-memory`:

   ```
   praxis_record_episode(
     text="Re-armed prd-<project> plan audit: planning checklist extended with check <check_id> (<angle>); prior panel-ran is stale and the audit must reconvene to close the new lens.",
     outcome="pending",
     derived_from=[<the new check fact id>],
   )
   ```

   The audit Stop-gate is satisfied only by a panel-ran episode that covers the CURRENT active
   planning checklist for `prd-<project>`. Because the new check post-dates the last panel-ran
   assertion, the gate now sees the audit as un-run for this checklist and **blocks "planning done"
   until `factory-audit` reconvenes** and closes the new lens (resolve / dismiss-with-reason /
   defer-as-owned-decision) for every requirement it bears on.

3. **Report**: the check you wrote (id, angle, criterion) and that `prd-<project>`'s plan audit is
   re-armed — a plan run (`factory-audit`) must now reconvene and close the new lens before the plan
   can be considered hardened again.

## Never

- **Never write or edit a file.** The lens lives as a check fact in Praxis; the re-arm is a Praxis
  episode. There is no manifest in this model — do not create one.
- **Never author a per-ticket check list, and never pre-bind the lens onto a requirement.** A check
  owns its own applicability (`meta.applies_when` / `angle`); which lenses apply is resolved by query
  at audit time.
- **Never silently bless.** The re-armed audit must actually close the new lens, not annotate it away.
- Never touch a different project's plan, and never build or execute.
