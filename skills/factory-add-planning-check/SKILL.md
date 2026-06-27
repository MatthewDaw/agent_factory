---
name: factory-add-planning-check
description: >
  Insert a planning check (a "how to plan" lens) into Praxis — a consideration the audit must apply
  to plans before they're hardened (e.g. "any app with user accounts needs a credential-recovery
  flow", "every screen needs loading/empty/error states"). The PLANNING-side analog of
  factory-add-validation. Writes ONE check fact to Praxis; it touches no plan and regresses nothing.
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

In this skill: you write ONE planning-checklist *check* fact into Praxis — a "how to plan" lens that
`factory-audit` resolves (step 3, RESOLVE) against future plans. You write NO JSON state, touch no
ticket, claim nothing, and regress nothing. The check is declarative config that takes effect on the
next plan run.

# Factory Add Planning Check — declare a planning lens (into Praxis)

Writes **one** planning check into Praxis as a `category="check"`, `scope="planning"` fact carrying a
general "what to consider when planning" rule that `factory-audit` pulls and enforces against plans.
The planning-side analog of `factory-add-validation`.

Praxis is the single source of dynamic truth and a **hard dependency**: if the write cannot reach
Praxis, this skill **fails closed** (it errors and stops) — it never falls back to a file. The lens
lives in Praxis and **nowhere else**.

## A check owns its own applicability

A check is declarative and read-only during builds — edited only on an explicit user request like this
one, never as plans run. It carries its OWN applicability predicate in `meta.applies_to` — never an
authored list of which plans/tickets reference it, and no plan or ticket carries an authored list of its
checks. WHICH checks apply is resolved as a fresh QUERY at the point of use (the RESOLVE step: tag ∪
surface ∪ semantic match), so this skill only writes the predicate; it binds nothing by hand.

`meta.applies_to` is an **array of tags**. Use `["*"]` for an always-applicable lens; otherwise list
the surface/semantic tags a plan must carry for the lens to fire (e.g. `["auth"]`).

## Infer the spec from the user's one-liner
- **criterion** — the consideration (the fact text), e.g. *"any app with user accounts needs a
  credential-recovery (password reset) flow"*.
- **angle** — a short lens label for reporting (e.g. `auth`, `states`, `security`, `data-lifecycle`,
  `rollback`, `privacy`).
- **applies_to** — the applicability tag array: `["*"]` for always, else the tags that gate it.

## Do (one Praxis write)
Via `factory-memory`, insert the check:

```
praxis_add_insight(
  insight  = "<criterion>",                 # the fact text
  source   = "planning-checklist",
  category = "check",
  scope    = "planning",
  meta     = { "check_id": "<stable-slug>", "applies_to": ["<tag>", ...] | ["*"],
               "angle": "<lens-label>" },
  on_conflict = "surface",
)
```

Idempotent intent: if a check with that `meta.check_id` already exists, `praxis_edit_fact` it instead
of duplicating. Then report the check you wrote (id, applies_to, angle, criterion). It takes effect on
the **next plan**: `factory-audit` queries active planning checks and must close every lens whose
`meta.applies_to` matches the plan before the plan hardens.

## Never
- **Never write a file** — no manifest, no checklist file, no `json.dump` of any state. The check goes
  in Praxis only; on a Praxis failure, fail closed, do not fall back to disk.
- **Never edit or re-open an existing plan**, and never mark anything incomplete or claim a ticket —
  that is `factory-redo-plan-add-check`'s job (or the lens simply applies on the next plan run).
- Never build, plan, or audit here. This only declares the lens.
