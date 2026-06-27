---
name: factory-add-validation
description: >
  Insert a live validation check into Praxis (the validation graph) — and nothing else. Use to
  declare a "this must pass before the ticket counts done" rule (e.g. "auth tickets need a live
  Playwright login test") WITHOUT touching any ticket. It writes ONE check fact to Praxis; it
  regresses nothing and writes no files. For the variant that also marks the matching tickets
  incomplete now, use factory-redo-ticket-add-validation.
---

# Factory Add Validation — just insert the check (into Praxis)

Writes one validation check into **Praxis** as a `category="check"`, `scope="validation"` fact bound
to a requirement (or a class of them). That's the whole job — no regress, no files. The check takes
effect on the **next build run**: `factory-execute` regresses any bound ticket that hasn't passed it,
and `factory-verify` runs the check as a blocking gate.

The check lives in **Praxis, never in a file**. Do NOT write `.factory/validations.yaml` or any other
manifest — the validation graph is the single source of truth.

## Infer the spec from the user's one-liner
- **criterion** — what must be true (e.g. "login works against the live service"); this is the fact text.
- **run** — the command that proves it, non-zero exit = fail (discover the repo's real e2e command).
- **applies_to** — a requirement-class tag (e.g. `auth`) or a specific requirement id.

E.g. *"auth tickets need a live playwright login test"* → `applies_to: auth`,
`run: "npx playwright test …login…"`, `criterion: "login works end-to-end against the live service"`.

## Do (one Praxis write)
Via `factory-memory`, insert the check:

```
praxis_add_insight(
  insight   = "<criterion>",                       # the fact text
  source    = "prd-<project>",
  category  = "check",
  scope     = "validation",
  meta      = { "check_id": "<stable-slug>", "applies_to": "<class-tag|requirement-id>",
                "run": "<command>" },
  on_conflict = "surface",
)
```

Idempotent intent: if a check with the same `meta.check_id` already exists, edit it
(`praxis_edit_fact`) rather than adding a duplicate. Then report the check you wrote (id, applies_to,
run). Note that binding by a **class tag** only matches requirements carrying that tag in `meta.tags`;
bind by requirement id when unsure.

## Never
- **Never write a file** (no `.factory/validations.yaml`, no manifest). The check goes in Praxis only.
- **Never regress / mark any ticket** and never run `record_outcome` — that is
  `factory-redo-ticket-add-validation`'s job, or it happens on the next `factory-execute`.
- Never build or fix code.
