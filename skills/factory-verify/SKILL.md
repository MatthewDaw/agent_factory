---
name: factory-verify
description: >
  The verification gate for the agent factory's execute step. Use after an execution attempt to
  decide pass/fail against a task's binary acceptance condition, using EXTERNAL signals only
  (the ticket's query-resolved pinned checks, tests, build, type-check, lint) — never the agent's
  own say-so. Records each pass on the TICKET'S Praxis node and records a succeeded outcome ONLY
  when every pinned check passed. Drives the bounded correction loop and decides when to escalate.
  Coding tasks verify autonomously; non-coding tasks fall back to human confirmation.
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

THIS SKILL'S ROLE IN THE NEW MODEL: Run the pinned checks (resolved by query, NOT read from an authored list on the ticket); record each pass on the TICKET NODE; record_outcome(success) ONLY when every pinned check passed. No JSON manifests.

---

# Factory Verify

A task is **not done because the agent believes it is.** It is done when an **external signal** says so.
This skill is the VERIFY → FINISH segment of the loop above: the gate between "the agent changed
something" and "the ticket passes." It is the single most important guardrail in the loop — intrinsic
self-correction (the model reviewing its own work) *degrades* coding quality; only signals the agent
cannot fake count.

Every read and write here goes to **Praxis live**, via the deterministic plugin client
(`hooks/_praxis.py` + `hooks/_ticket_state.py`), per `docs/factory-state-contract.md` — never to a local
file. This skill writes **no** state files. **Fail-closed:** Praxis is a HARD dependency; if it is
unreachable the client raises `PraxisUnreachable` and this gate **BLOCKS** — it never passes a ticket it
cannot prove.

## 0. The completion contract is the pinned check set

When the ticket started (the CLAIM + RESOLVE steps), `start_ticket(cid, owner, project)` did three things
atomically: claimed it (`claim`: `build_state` incomplete → in_progress, stamping the lease), ran the
**applicability query** (`resolve_checks` — the tag ∪ surface union against active checks in Praxis), and
**pinned** the resolved set onto the TICKET node (`pin_checks`, which TRUNCATES any prior `pinned_checks`
first). That pinned set is this pass's completion contract.

You **never read an authored list of checks off the ticket** — there is no such list. Which checks apply
was resolved fresh, by query, at ticket start, and pinned. Verification runs exactly the `pinned_checks`
for this ticket and nothing else. If the ticket has no live `in_progress` claim owned by this session,
there is nothing to verify — go (re)start the ticket first.

Each pinned entry is `{ "check_id", "passed": bool|null, "ran_at": float|null }` (null = not yet run this
pass). A check fact carries `meta.run` (the command) and its own applicability predicate
(`meta.applies_to`); the ticket carries only the resolved `check_id`s. Fetch each check fact with
`get_fact(check_id)` to read its `meta.run`. Call `heartbeat(cid, owner)` periodically while verifying so
the lease stays live.

## 1. Run each pinned check — exit code is the verdict

For every entry in `pinned_checks`, run the check fact's `meta.run` command and take its **exit code** as
the verdict (0 = pass). The verdict is the exit code / raw output, **not** the agent's interpretation of
it. Record the result ON THE TICKET NODE:

```
record_check_pass(cid, check_id, passed=(exit_code == 0), ran_at=now)
```

This writes into the ticket's `pinned_checks` entry (via `patch_meta`, which MERGES) — never onto the
check fact. The check is read-only during builds.

Alongside the pinned checks, run the project's real external gates so the acceptance condition is actually
observable (discover the commands; don't assume):

| Gate | Signal | When |
|---|---|---|
| **Pre-flight** | schema / type-check / lint / AST parse | before trusting an edit |
| **Tests** | the task's acceptance test(s) + the existing suite | the primary oracle |
| **Build** | compile / bundle succeeds | for anything that must build |

Rules:
- **The acceptance test must exist and must have failed before the change** (red→green). A test written
  to match the implementation proves nothing. If the acceptance condition has no test yet, the gate is:
  write the failing test first, watch it fail, then verify the change makes it pass.
- **A gate's verdict is its exit code / output, not the agent's reading of it.** Capture raw output.
- **Nothing about *what* is checked lives in this skill or any file.** The checks live in Praxis,
  resolved by query and pinned; this skill says only *how* to run the pinned set and *how* to record each
  pass on the ticket.

## 2. Correction loop — fires ONLY on an external signal

On a failing gate or a failing pinned check, re-enter execution (the BUILD step) with the **captured
failure** as context. Never let "the model decided to revise" be a transition — corrections are
signal-driven.

Four tiers with explicit trip conditions:
1. **Execute** — one attempt.
2. **Correction** — retry with the failing signal attached. Bounded (a max-attempts cap).
3. **Strategy** — after **N identical failures** (degeneration), stop retrying and replan the task.
4. **Human escalation** — after **M replans** without progress, or any low-confidence/irreversible step,
   escalate. Don't loop forever.

A **circuit breaker** trips on repeated identical output or identical errors — that's degeneration, not
progress; escalate rather than burn iterations.

## 3. Structural-erosion check (don't let "passing" hide rot)

Tests passing is necessary, not sufficient: long iterative runs erode structure (complexity, duplication,
file-spread) even while green. Track a **per-iteration complexity-delta** (cyclomatic / churn /
new-symbol fan-out — wire an existing tool like `radon`/`ruff`/`git diff --stat`, don't build one) and
**halt/escalate** if the delta per unit of verified progress exceeds the task's budget. This is a
structural gate, not a prompt instruction — prompting alone does not bend the erosion curve.

## 4. The evaluator must be a separate model

For anything that needs judgement rather than a deterministic signal (rare in coding; common for soft
outputs), the evaluator is a **different model from the generator** — a model judging its own output
inflates its own pass rate. Use the judge only for the residue with no deterministic oracle, and keep it
as escalation triage (proceed vs. park), never as the success verdict for coding.

## 5. Non-coding tasks — human-in-the-loop oracle

A task type with no deterministic oracle (form-filling, video) verifies by **human confirmation**, not by
the agent or a judge declaring success. In an unattended run, a low-confidence non-coding step **parks** a
checkpoint for batch review; high-confidence steps proceed. The human remains the oracle; the judge only
routes.

## 6. FINISH — record the outcome IFF every pinned check passed

The ticket is finished **iff `all_checks_passed(ticket)`** — at least one pinned check and **every** pinned
check `passed == True`. Then, and only then:

- `record_outcome(cid, success=True)` on the requirement fact (and on any learning the task acted on).
- `release(cid, owner, state="finished")` — flips `build_state` to `finished` and drops the lease.

If any pinned check failed or is still unrun, the ticket does **not** pass:

- `record_outcome(cid, success=False)` — repeated failures sink a fact in retrieval and **regress** the
  ticket so it re-enters the FIND set; this is the compounding mechanism, live now.
- `release(cid, owner, state="incomplete")` — yields the lease cleanly so the build loop re-picks the
  ticket (the fail → regress → re-pick loop).

Only an externally-confirmed pass (every pinned check green) is eligible to write a learning back. The one
completeness gate (`build_completeness`) reads this state live from Praxis to decide whether incomplete
tickets/checks remain for the scope — there is no separate findings state machine and no manifest to
update.

## Never
- Never mark a ticket done without every pinned check green (or, for non-coding, human confirmation).
- Never read or write build/validation state on a `.factory/*.json` manifest — Praxis is the only store.
- Never read an authored list of checks off the ticket; run the query-resolved `pinned_checks`.
- Never record a check pass on the check fact; record it on the ticket node via `record_check_pass`.
- Never let the gate pass when Praxis is unreachable — `PraxisUnreachable` BLOCKS (fail-closed).
- Never trigger a correction from self-doubt alone — corrections require a failing signal.
- Never use the generator's own model as the success judge.
- Never accept an acceptance test that was written green (never observed failing).
- Never loop past the iteration cap / circuit breaker — escalate.
