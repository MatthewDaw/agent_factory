---
name: factory-add-planning-check
description: >
  Insert a planning check (a "how to plan" lens) into Praxis — a consideration the audit must apply
  to every plan before it's hardened (e.g. "any app with user accounts needs a credential-recovery
  flow", "every screen needs loading/empty/error states"). The PLANNING-side analog of
  factory-add-validation. Writes ONE check fact to the planning checklist in Praxis; it touches no
  plan and regresses nothing.
---

# Factory Add Planning Check — declare a planning lens (into Praxis)

Writes one planning check into the **planning checklist** in Praxis — a `category="check"`,
`scope="planning"` fact carrying a general "what to consider when planning" rule that `factory-audit`
pulls and enforces against every plan. The analog of `factory-add-validation`, for the planning side.

**What gets checked lives ENTIRELY in Praxis.** This skill (and the audit) only say *how* to pull and
*how* to apply the lens — never the lens content in a file.

## Infer the spec from the user's one-liner
- **criterion** — the consideration (the fact text), e.g. *"any app with user accounts needs a
  credential-recovery (password reset) flow"*.
- **angle** — the lens category (e.g. `auth`, `states`, `security`, `data-lifecycle`, `rollback`,
  `who-pays`, `privacy`).
- **applies_when** (optional) — when it applies, e.g. *"the product has authentication"*. Omit for
  always-applicable lenses.

## Do (one Praxis write)
Via `factory-memory`, insert the check:

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

Idempotent intent: if a check with that `meta.check_id` already exists, `praxis_edit_fact` it instead
of duplicating. Then report the check you wrote (id, angle, criterion). It takes effect on the **next
plan**: `factory-audit` pulls the planning checklist and must close this lens before the plan hardens.

## Never
- **Never write a file** — the planning checklist lives in Praxis, nowhere else.
- **Never edit or re-open an existing plan** — that's `factory-redo-plan-add-check`'s job (or it
  applies on the next plan run).
- Never build, plan, or audit here. This only declares the lens.
