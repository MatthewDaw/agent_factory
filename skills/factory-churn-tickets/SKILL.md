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

# Factory Churn Tickets — drive the (optionally scoped) build set to done

The explicit entry point for *"address unfinished work."* It runs the **factory-execute** build loop
over `prd-<project>` until the forced completeness gate is satisfied. All the discipline
(single-decision-maker per slice, the read-only retrieval sub-agent, outcome-grounded completeness,
every gate) is `factory-execute`'s, unchanged — this is that loop with a name **and an optional scope**.

## Scope (optional — this is the whole point of the argument)
- **No argument** (`/factory-churn-tickets`) → drive the **WHOLE build set** to done. Default.
- **A scope argument** (`/factory-churn-tickets auth` · "only the unfinished auth tickets") → target
  **ONLY** the incomplete tickets matching that scope; leave every other ticket alone **even if it is
  also incomplete**. Resolve the scope to a requirement set, in this order: a **class tag** (match
  `meta.tags`), explicit **requirement ids**, or a named **area** (semantic/text match via
  `factory-memory` — e.g. "auth" → login, signup, logout, JWT/session, password reset, authz). **List
  exactly which tickets you selected** before building, so the scope is explicit.

## Do
1. **Identify the project** (`prd-<project>` for this repo).
2. **Sync validation checks from Praxis** and `record_outcome("failed")` on any ticket bound to a
   not-yet-passing check (so a just-added check's ticket enters the set).
3. Query `praxis_incomplete_requirements(prd-<project>)`, partition with `select_build_target`, and
   **if a scope was given, filter the build set to the scoped subset.** Write
   `<project>/.factory/build-status.json` so `incompleteCount` / `incomplete[]` count **only the
   targeted set** — the whole build group when unscoped, the scoped subset when scoped — and record
   every non-targeted incomplete ticket in `outOfScopeThisRun:[{id, reason}]` (surfaced, **never**
   counted). This arms/satisfies the build-completeness gate, so a **scoped run is done when the
   scoped tickets are done**; the parked ones are reported, not silently skipped.
4. **Run the forced loop** (`factory-execute` §0b): build the frontier (fan out independent slices via
   a Workflow), gate each via `factory-verify` (which **runs the ticket's bound validation checks from
   Praxis** as blocking signals), `praxis_record_outcome`, re-query, loop until `incompleteCount == 0`.
5. **Honor the gates** (deploy hard-gate, work-review) exactly as `factory-execute`. **Report** both
   the scoped tickets finished AND the `outOfScopeThisRun` tickets left untouched — nothing hidden.

## Never
- Never start a new plan or add requirements here — this only finishes existing tickets.
- Never mark a ticket done without `factory-verify` passing, including its bound validation checks.
- Never fake `incompleteCount`. When scoped, the parked (non-scoped) incomplete tickets MUST appear in
  `outOfScopeThisRun` and in the report — scoping is explicit, never a silent under-build.
- Never build a ticket outside the requested scope; if the scope is ambiguous, list your selection and
  ask before churning.
