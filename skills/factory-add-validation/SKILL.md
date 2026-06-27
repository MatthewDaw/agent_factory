---
name: factory-add-validation
description: >
  Insert a live validation check into Praxis (the validation graph) — and nothing else. Use to declare a
  "this must pass before the ticket counts done" rule (e.g. "auth tickets need a live Playwright login
  test") WITHOUT touching any ticket. It writes ONE declarative, read-only check fact to Praxis; it
  regresses nothing and writes no files. For the variant that also marks the matching tickets incomplete
  now, use factory-redo-ticket-add-validation.
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

In this skill: you write ONE declarative, READ-ONLY check fact (`meta.applies_to` / `meta.applies_when` /
bound surfaces). You never bind it onto specific tickets — applicability is a QUERY resolved at each
ticket's RESOLVE step. You touch no ticket state, regress nothing, and write no JSON.

---

# Factory Add Validation — declare one check (into Praxis)

Writes **one** declarative validation check into **Praxis** as a `category="check"`, `scope="validation"`
fact. The check carries its OWN applicability predicate (`meta.applies_to` tags / `meta.applies_when` /
bound surfaces). That is the whole job — no regress, no ticket edit, no files.

Praxis is the **single source of dynamic truth** (see `docs/factory-state-contract.md`). The check is
**read-only during builds** — edited only on explicit user request, never as work completes.

**The check NEVER names specific tickets.** Which tickets a check applies to is the RESOLVE query run
fresh at each ticket's start (`_ticket_state.resolve_checks`: tag ∪ surface match against active checks,
per the state contract). You declare the predicate; the build loop resolves and pins it. Do NOT bind,
list, or stamp this check onto any requirement node — that defeats the query model.

## Infer the spec from the user's one-liner
- **criterion** — what must be true (the fact text), e.g. "login works end-to-end against the live service".
- **run** — the command that proves it; non-zero exit = fail (discover the repo's real e2e command).
- **applies_to** — an ARRAY of requirement-class tags (e.g. `["auth"]`); use `["*"]` to apply to every
  ticket. RESOLVE matches a ticket when `meta.applies_to` shares any tag with the ticket's `meta.tags`.
- **applies_when** (optional) — a free-text condition narrowing applicability (e.g. "the ticket renders
  a credentialed form"). Omit for unconditional checks. (Reserved for the documented semantic lane; in
  v1 RESOLVE is tag ∪ surface, so lean on `applies_to`/surfaces for the actual match.)
- **surfaces** (optional) — screen ids this check binds to; RESOLVE also matches any ticket that renders
  one of these surfaces (via the `renders` edge / `/surfaces/{screen}/checks`).

E.g. *"auth tickets need a live playwright login test"* → `applies_to: ["auth"]`,
`run: "npx playwright test …login…"`, `criterion: "login works end-to-end against the live service"`.

## Do (one Praxis write)
Via `factory-memory`, insert the check:

```
praxis_add_insight(
  insight  = "<criterion>",                          # the fact text
  source   = "prd-<project>",
  category = "check",
  scope    = "validation",
  meta     = { "check_id": "<stable-slug>",
               "applies_to": ["<class-tag>", ...],   # array; ["*"] = all tickets
               "applies_when": "<condition | empty>",
               "surfaces": ["<screen-id>", ...],     # optional; omit if none
               "run": "<command>" },
  on_conflict = "surface",
)
```

If the check binds to surfaces, also create the `renders` edge so the surface lane of RESOLVE finds it
(`praxis_bind_surface(check_id, screen_id)`), instead of relying on `meta.surfaces` alone.

Idempotent intent: if a check with the same `meta.check_id` already exists, `praxis_edit_fact` it rather
than adding a duplicate. Then report the check you wrote (id, applies_to, run).

The check takes effect on the **next build run**, with no action here: at each ticket's RESOLVE step
`resolve_checks` picks it up by tag/surface match, `pin_checks` truncates prior per-check state and
writes it into that ticket's `meta.pinned_checks` completion contract, and the ticket is FINISHED iff
every pinned check (this one included) passed (`all_checks_passed`).

## Never
- **Never write or read a file** — no manifest, no local state. The check lives in Praxis only.
- **Never bind / list / stamp this check onto a ticket node.** Applicability is the RESOLVE query;
  pinning is the build loop's job at ticket start.
- **Never touch ticket state** — no claim, no heartbeat, no `record_outcome`, no `build_state` change.
  Regressing the matching tickets now is `factory-redo-ticket-add-validation`'s job; otherwise the next
  build run picks the check up at RESOLVE.
- Never build, fix, or run the check here. This only declares the rule.
