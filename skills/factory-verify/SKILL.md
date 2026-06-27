---
name: factory-verify
description: >
  The verification gate for the agent factory's execute step. Use after an execution attempt to
  decide pass/fail against a task's binary acceptance condition, using EXTERNAL signals only
  (tests, build, type-check, lint) — never the agent's own say-so. Drives the bounded
  correction loop and decides when to escalate. Coding tasks verify autonomously; non-coding
  tasks fall back to human confirmation.
---

# Factory Verify

A task is **not done because the agent believes it is.** It is done when an **external signal**
says so. This skill is the gate between "the agent changed something" and "the task passes," and
it is the single most important guardrail in the loop — intrinsic self-correction (the model
reviewing its own work) *degrades* coding quality; only signals the agent cannot fake count.

All memory access is through the **`factory-memory`** policy; every gate result is an event-log
entry (`gate_result`), and the final verdict an `outcome` event.

## 0. Get the acceptance condition (what "pass" means)

Pull the task's **binary acceptance condition** from the project pool (`prd-<project>`) via
`factory-memory` retrieval. The plan skill admitted every requirement with one ("when X, the
system does Y, observable via Z"). Verification checks *that* condition — not a vibe. If a task
has no binary acceptance condition, it was admitted wrongly; stop and send it back to planning,
don't invent a pass criterion here.

Each condition is tagged **`automated`** or **`manual`** (factory-plan §2b). You verify *automated*
conditions here with external signals (§1). A **`manual`** condition you **do not self-check**: in
an attended run, pause and hand it to the human as a checklist item ("ready for manual
verification"), marking it passed only on their confirmation; in an unattended run you cannot
confirm it — **park** it as a deferred owned-decision checkpoint (§5) for batch review, never
auto-pass it. A task passes only when its automated conditions are green **and** its manual
conditions are human-confirmed (or, unattended, explicitly parked).

## 1. The external-signal gates (coding tasks)

Run the gates that make the acceptance condition observable. These are **blocking** — a failing
gate fails the task. Use the project's real commands (discover them; don't assume):

| Gate | Signal | When |
|---|---|---|
| **Pre-flight** | schema / type-check / lint / AST parse | before trusting an edit |
| **Tests** | the task's acceptance test(s) + the existing suite | the primary oracle |
| **Build** | compile / bundle succeeds | for anything that must build |
| **Bound validation checks** | each check's `meta.run` exit code (0 = pass) | any ticket with checks bound in Praxis (`category="check"`, `scope="validation"`) |

Rules:
- **The acceptance test must exist and must have failed before the change** (red→green). A test
  written to match the implementation proves nothing. If the acceptance condition has no test
  yet, the gate is: write the failing test first, watch it fail, then verify the change makes it
  pass.
- **A gate's verdict is its exit code / output, not the agent's interpretation of it.** Capture
  the raw output into the `gate_result` event.
- **Bound validation checks are blocking, live signals — pulled from Praxis.** The checks live in
  the validation graph (`category="check"`, `scope="validation"`), each carrying `meta.applies_to`
  (a requirement id or a class tag like `auth`) and `meta.run` (the command). For the ticket being
  verified, **pull its applicable checks from Praxis** (via `factory-memory`; bind with
  `validation_target.resolve_bindings`), **run each check's `meta.run` command, and take its exit
  code as the verdict** (0 = pass; capture raw output to `gate_result`). The ticket does **not** pass
  while any bound check fails or has not been run green this build. Never self-judge them. Nothing
  about *what* is tested is in this skill or any file — the skill only says *how* to pull the checks
  from Praxis and *how* to run them.

## 2. Correction loop — fires ONLY on an external signal

On a failing gate, re-enter execution with the **captured failure** as context. Never let "the
model decided to revise" be a transition — corrections are signal-driven.

Four tiers with explicit trip conditions:
1. **Execute** — one attempt.
2. **Correction** — retry with the failing signal attached. Bounded (a max-attempts cap).
3. **Strategy** — after **N identical failures** (degeneration), stop retrying and replan the task.
4. **Human escalation** — after **M replans** without progress, or any low-confidence/irreversible
   step, escalate. Don't loop forever.

A **circuit breaker** trips on repeated identical output or identical errors — that's degeneration,
not progress; escalate rather than burn iterations.

## 3. Structural-erosion check (don't let "passing" hide rot)

Tests passing is necessary, not sufficient: long iterative runs erode structure (complexity,
duplication, file-spread) even while green. Track a **per-iteration complexity-delta** (cyclomatic
/ churn / new-symbol fan-out — wire an existing tool like `radon`/`ruff`/`git diff --stat`, don't
build one) and **halt/escalate** if the delta per unit of verified progress exceeds the task's
budget. This is a structural gate, not a prompt instruction — prompting alone does not bend the
erosion curve. *(Full version is an M2 deliverable; at minimum log the deltas now.)*

## 4. The evaluator must be a separate model

For anything that needs judgement rather than a deterministic signal (rare in coding; common for
soft outputs), the evaluator is a **different model from the generator** — a model judging its own
output inflates its own pass rate. Use the judge only for the residue with no deterministic oracle,
and keep it as escalation triage (proceed vs. park), never as the success verdict for coding.

## 5. Non-coding tasks — human-in-the-loop oracle

A task type with no deterministic oracle (form-filling, video) verifies by **human confirmation**,
not by the agent or a judge declaring success. In an unattended run, a low-confidence non-coding
step **parks** a checkpoint for batch review (the confidence-gated escalation — M4); high-confidence
steps proceed. The human remains the oracle; the judge only routes.

## 6. Record the outcome (close the H1 loop)

Emit an `outcome` event (verdict, deciding signal, task/requirement id) to the local log, **and**
feed it back to Praxis: call **`praxis_record_outcome(fact_id, "succeeded"|"failed")`** on the
requirement fact (and on any learning the task acted on). Repeated failures sink a fact in
retrieval; proven facts hold — this is the compounding mechanism, and it's live now (not deferred).
Only an externally-confirmed pass is eligible to write a learning back (per `factory-memory`).

A ticket is eligible for `record_outcome(fact_id, "succeeded")` **only when its automated gates AND
every bound validation check are green**; a failing or `unrun` bound check records `"failed"`, which
regresses the ticket so the build loop re-picks it (the fail→regress→re-pick loop).

## Never
- Never mark a task done without a passing external signal (or, for non-coding, human confirmation).
- Never trigger a correction from self-doubt alone — corrections require a failing signal.
- Never use the generator's own model as the success judge.
- Never accept an acceptance test that was written green (never observed failing).
- Never loop past the iteration cap / circuit breaker — escalate.
