---
name: factory-redo-ticket-add-validation
description: >
  Add a live validation check to the current target repo and regress the tickets it binds to, so
  the build loop must re-do them until the check passes. Use to enforce a new "this must be proven
  before the ticket counts done" rule — e.g. "auth tickets need a live Playwright login test", "the
  checkout flow needs an e2e payment test". Sets up the rule + marks the matching work incomplete;
  it does NOT build or fix anything (the build run does that).
---

# Factory Redo-Ticket / Add Validation — add a check AND regress its tickets

> For the lighter "just declare the check, don't touch any ticket" move, use
> **`factory-add-validation`** instead — this skill additionally regresses the matching tickets.

One explicit call that turns *"I want `<X>` proven before `<class-of-tickets>` can count done"* into:
a bound validation check in the target repo **plus** the matching tickets regressed. The build loop
(`factory-execute` / `factory-verify`) then forces them re-done until the check passes. This skill
**only** sets up + regresses — it never builds.

## Infer the spec from the user's one-liner
Pull three things (ask once only if genuinely ambiguous; otherwise infer):
- **criterion** — what must be true (e.g. "login works against the live service").
- **run** — the command that proves it, non-zero exit = fail (e.g. `npx playwright test e2e/auth/login.spec.ts`; discover the repo's real e2e command, don't assume).
- **target** — a requirement-class tag (e.g. `auth`) or specific requirement id(s).

E.g. *"auth tickets need a live playwright login test"* → `applies_to: auth`,
`run: "npx playwright test …login…"`, `criterion: "login works end-to-end against the live service"`.

## Steps
1. **Insert the check into Praxis** (the validation graph) via `factory-memory` —
   `praxis_add_insight(insight="<criterion>", source="prd-<project>", category="check",
   scope="validation", meta={"check_id":"<slug>", "applies_to":"<class | requirement-id>",
   "run":"<command>"}, on_conflict="surface")`. Idempotent — if a check with that `meta.check_id`
   already exists, `praxis_edit_fact` it instead of duplicating. **Write no file.**
2. **Resolve the target tickets** in `prd-<project>`. For a class tag: find the requirements in that
   class — by existing `meta.tags`, else by text/semantic match via `factory-memory` — and **tag each**
   with the class (`praxis_edit_fact`, preserving existing meta: keep source/scope/verify/acceptance/
   surfaces, add the tag to `meta.tags`) so the check binds. For specific ids: use them directly.
3. **Regress them.** For each target requirement that currently shows complete, call
   **`praxis_record_outcome(fact_id, "failed")`** — it re-enters `incomplete_requirements` (a
   never-built one is already incomplete; leave it).
4. **Confirm + report.** Run `praxis_incomplete_requirements(<project>)` and report: the check you
   wrote, the tickets you tagged + regressed (id + text), and that they now show incomplete.

After this, a cleared session that "addresses all unfinished work" runs `factory-execute`, which
re-picks the regressed tickets and (via `factory-verify`) runs the check's `run` command as a blocking
gate — the ticket can't re-complete until it passes.

## Never
- **Never build or fix code here.** This skill declares the rule and regresses, nothing more.
- **Never write a file** (no `.factory/validations.yaml`, no manifest). What gets tested lives
  entirely in **Praxis**. The only writes are: the check fact, the class tag on the bound
  requirements, and the `failed` outcome (the regress trigger).
- Never regress requirements outside the resolved target set.
