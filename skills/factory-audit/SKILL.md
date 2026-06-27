---
name: factory-audit
description: >
  The separate cold-eyes judgment audit that runs AFTER factory-plan admits requirements and
  BEFORE the plan is blessed (save_snapshot). It adversarially challenges every admitted
  requirement, detects and routes underspecification, checks cross-requirement gaps, AND forces
  every end-to-end technical-architecture decision (auth, data store, stack, deploy, secrets, ...)
  to be made explicitly — the pushback that mechanical gates can't do. Every gap it finds is written
  back into Praxis as a requirement edit or a check; it leaves only a "panel-ran" episode behind, no
  findings file. Use as the last step of plan-hardening (intake → plan → audit → snapshot).
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

In this skill: factory-audit is the planning-side analog of factory-review. It does no FIND/CLAIM/BUILD
of its own — it runs cold-eyes judgment over the admitted-but-not-yet-blessed `prd-<project>` graph and
emits every gap it finds as a Praxis write: a tightened/added requirement (a TICKET) or a declared
planning/validation check (a CHECK), plus ONE "panel-ran" episode so the act of auditing can't be
silently skipped. Each unresolved gap therefore lives as an INCOMPLETE ticket/check, and the single live
`build_completeness` gate — reading Praxis fresh, fail-closed — refuses to let the plan be blessed while
any remain. There is NO plan-audit.json, no findings state machine, no audit-specific gate.

# Factory Audit (judgment skeptic + underspecification)

This is the **planning-side analog of `factory-review`**: a cold-eyes pass whose entire output is
**writes into Praxis** — requirement edits, new requirements, reconciled near-duplicates, and
planning/validation checks — plus a single **panel-ran episode** that proves the audit happened. It
authors **no state file**. There is no `plan-audit.json`, no findings state machine, no per-audit
manifest; **Praxis is the only store of dynamic truth.** An audit gap that isn't resolved doesn't
live in a JSON status field — it lives in Praxis as an **incomplete requirement or check**, and the
single live completeness gate (`build_completeness`, reading Praxis fresh) is what refuses to let the
plan be called hardened while any such gap is still incomplete.

The mechanical checks (binary-acceptance, no-vague-term, no-dangling-reference, contradiction
surfacing) happen inline during ingestion in `factory-plan`. They catch what's *nameable*. This
skill is the **separate step** for what needs judgment: *is this requirement underspecified? what
case does it not handle? what gap sits between two requirements? what architecture did nobody
choose?* It runs over the admitted-but-not-yet-snapshotted `prd-<project>` graph — the live graph is
the staging area, and the act of resolving every gap **into Praxis** is what makes the plan
blessable.

## Why separate (not inline)

- **Independence.** A skeptic firing in the same breath that drafted a requirement is self-review —
  the weak kind (`factory-verify`: a model judging its own output inflates its pass rate). So run
  the challenge with **cold eyes**: dispatch the **read-only retrieval sub-agent** (`factory-execute`
  §1a) as the skeptic — it reads the admitted facts (`praxis_list_graph` / `get_context` on the live
  graph) plus the PRD prose and wireframe, and tries to **break** each requirement. It didn't write
  them, so it challenges harder.
- **Whole-set view.** Cross-requirement gaps (a missing interaction, an unhandled handoff) are
  invisible per-requirement; the audit sees the full set.
- **Everything becomes a ticket or a check.** There is no separate audit machinery to feed: a
  challenge that holds is resolved by **editing/adding a requirement** or **declaring a check** in
  Praxis. The gap and its resolution are the graph itself, not a row in a sidecar file.

## Step 1 — Adversarial challenge (cold eyes, every requirement)

For each admitted requirement, the skeptic files **≥1 falsifiable challenge** drawn from: missing
actor, unbounded condition, unhandled empty / error / boundary case, hidden dependency, idempotency,
race/ordering, and **cross-requirement gap** (the case that falls between two requirements). In
**rigorous** mode, each gap-lens must explicitly **fire-or-pass** per requirement: `failure-modes`,
`security`, `data-lifecycle`, `rollback`, `who-pays`.

**Evaluate the lenses by BATCH, not per-requirement (stop-sooner).** Take ONE lens and sweep it
across ALL requirements in a single pass — five sweeps total — recording fire/pass per requirement,
rather than re-deriving all five lenses for each requirement (5×N separate judgments, the dominant
cost on a large plan). For a large plan, **fan the five lens-sweeps out as a Workflow** (one builder
per lens). The same batch-by-dimension discipline applies to the technical sweep (Step 3) and the
test-strategy derivation (Step 3a).

A challenge isn't done until it's **closed by a Praxis write** — one of:
- **resolved** — the plan changed: `praxis_edit_fact` to tighten the requirement, or
  `praxis_add_insight(category="requirement", ...)` to add the missing one. The edit/add IS the
  closure; nothing is "closed" by annotation.
- **dismissed** — the challenge doesn't hold: record *why* with a non-empty reason as a
  `praxis_record_episode` (so the reasoning is durable, not lost in chat).
- **deferred** — a genuine owned-decision that can't be settled now: record it as a deferred
  owned-decision via `praxis_record_episode` (explicit, not silent). A deferral that still blocks the
  build is left as an **incomplete requirement/check** in Praxis so the live gate keeps it visible.

### Step 1a — Near-duplicate / overlap challenges WRITE BACK to the graph

A specific, load-bearing class of challenge is the **near-duplicate / overlap** pair: two admitted
facts that say the same thing, or where one restates a clause of the other. The cold-eyes pass is the
**only** dedup/reconcile step for any plan admitted via the `raw=True` bulk fast-lane — `raw`
deliberately **skips Praxis dedup**, so no earlier stage collapses these. That makes reconciliation
**the audit's job**, and a near-dup is **not closed until the graph itself reflects it**:

- **redundant / subsumed** (one fact fully covers the other) → keep the canonical fact and
  **`praxis_reject_fact`** the loser. Rejection drops it from active queries and fires the **stale
  cascade** (`praxis_get_stale_derivations` / `praxis_dependents` flag anything built on it). Record
  *why* + a **cross-link** to the canonical fact, then **re-save the `prd-<project>` snapshot**.
- **distinct-but-overlapping** (different primary intents, but one restates a clause of the other) →
  **`praxis_edit_fact`** the overlapping fact to **NARROW** it — strip the duplicated clause so it
  **defers to / references** the canonical fact (`edit_fact` requires BOTH `title` and `content`).
  Persist the relationship as a **cross-link in the GRAPH** — a `praxis_record_derivation` edge (or a
  `references` entry in `meta`) — then **re-save the snapshot**.
- **genuinely distinct / complementary** → **no graph change**; record the cross-link rationale (an
  episode) so a future reader knows the overlap was considered and the two were deliberately kept.

## Step 1b — Pull the planning checklist from Praxis (data-driven lenses)

The fixed gap-lenses above are the built-in **floor**; the **extensible** lenses live in Praxis. Pull
the **planning checklist** — the active `category="check"`, `scope="planning"` facts (via
`factory-memory` / `praxis_facts_by(category="check", meta={"...":"..."})`, written by
`factory-add-planning-check`) — and treat each as a consideration the audit must close for THIS plan.
For each check, respect `meta.applies_when` / `meta.applies_to` (skip a lens whose condition this
product doesn't meet — and record *why* as an episode; surface an ambiguous one rather than silently
skipping it), and address it across the requirements it bears on.

**Closing a planning check is a Praxis write, not a status row.** When a check's lens exposes a real
gap, close it the same way as any challenge: edit/add the requirement that satisfies it. A planning
lens added to Praxis via `factory-add-planning-check` is therefore enforced on the next plan **with
no code change** — *which* lenses exist lives ONLY in Praxis; this skill only says how to pull them
and how to apply them.

## Step 2 — Route underspecification (research / default / ask / defer)

When a challenge exposes that a requirement can't carry a *correct, complete* binary acceptance
condition, use `factory-plan`'s underspecification trigger (§2a) — do not paper over it:
1. **Research-resolvable** → dispatch the read-only research sub-agent to find the answer (PRD,
   wireframe, mounted `prd-*`/`constitution`, prior art), then `praxis_edit_fact` to tighten the
   acceptance condition.
2. **Convention-resolvable** → low-regret default written into the requirement + `praxis_record_episode`,
   surfaced for override.
3. **Genuine fork** → **ask the human** (batch all such questions — see mode below).
4. **Unknowable now** → deferred owned-decision (`praxis_record_episode`); if it still blocks the
   build, leave the affected requirement **incomplete** in Praxis.

The **anti-masking guard** is the whole point of this step: a plausible-but-shallow acceptance
condition that hides a gap is exactly what a mechanical check waves through. The audit is where that
gets caught — an underspecified area must visibly become a research-tightened requirement, a question,
or an explicit deferred fact, never a quiet guess.

## Step 3 — Technical architecture sweep (end-to-end) → written into Praxis

Behavioral requirements describe *what* the product does; they routinely leave the *how* — the
cross-cutting technical architecture — unspecified. This sweep forces every project-wide technical
decision to be made explicitly (or consciously deferred), so the build never quietly invents an
architecture nobody chose. (This is the dimension a requirement-by-requirement audit misses entirely.)

**Derive the decisions dynamically — there is NO fixed list.** Enumerate the technical decisions
*this* system needs to be buildable, reasoning from the PRD, the admitted requirements, and the
*kind* of software it is. What a web app needs differs from a CLI, an ML/data pipeline, a game, an
embedded device, or a library — never work from a canned checklist.

*Illustrative only* (a typical web app): auth + authz, data store + migrations, backend stack + API
style, frontend framework + styling + build tooling, hosting/deploy + CI + environments,
secrets/config, external services, testing + the verify oracle, observability, data-privacy. **These
are prompts, not the list** — an ML service also needs model hosting/versioning/eval data; a CLI
needs packaging/distribution/config; a library needs its public API surface + semver + release
process. Derive the real set for *this* build.

**Each decision becomes durable Praxis state, not a JSON row.** Resolve each like an underspecified
requirement (PRD → mounted conventions → low-regret default + `praxis_record_episode` → ask → defer)
and persist it: write the chosen decision **into the requirement(s) it governs** (`praxis_edit_fact`)
or as a first-class architecture requirement (`praxis_add_insight(category="requirement", ...)`), and
log the rationale + alternatives as a `praxis_record_episode`. A genuinely-deferred or not-applicable
decision is an episode with the reason. None may be silently skipped, and a default may never paper
over a genuine owner fork (anti-masking).

### Step 3a — Test strategy is mandatory (derive the layers for THIS system)

A PRD almost never says *how* the product is tested — yet a plan with no test strategy (or one that
skips a layer this platform lives or dies on) is exactly the silent gap mechanical checks wave
through. So an explicit, **platform-appropriate, automated test strategy + CI is a MANDATORY outcome
of every audit**: no project can be blessed on an untested or under-tested plan. **Derive the right
set of test LAYERS for THIS system from the PRD, the requirements, and the *kind* of software it is;
there is NO fixed checklist.**

*Illustrative only* (derive, don't copy): a **library** → unit + public-API/contract tests +
semver-aware release CI; a **web app** → unit + integration + e2e on the critical flows + merge-gating
CI/CD; a **MOBILE app** → unit + integration + UI/e2e on a real device or simulator + build/sign CI
(the device/simulator layer is the one a generic plan silently omits); a **CLI** → unit + integration
+ a packaging/install smoke test; a **data/ML pipeline** → unit + data-contract/schema tests +
pipeline integration + eval gates on model quality.

**Persist each chosen layer + the CI/CD setup as Praxis state with a BINARY acceptance condition** —
the same bar as any requirement. The natural home is a **live validation check** per layer (the kind
`factory-add-validation` writes: `category="check"`, an applicability predicate, a binary criterion)
and/or a first-class testing requirement. Examples of the shape (not content): "CI runs the
unit+integration suite on every push and **blocks merge on red**"; "the e2e suite covers the critical
flows on a simulator **in CI** and blocks release on failure"; "the packaging smoke test installs the
built artifact in a clean environment in CI." This is **what `factory-verify` gates the build on** —
a layer with no binary, CI-enforced condition is not a strategy; it's a hope, and the build gate
treats the requirement it should have produced as missing (incomplete).

**Then run the completeness critic — the dynamic pushback.** Dispatch an *independent* cold-eyes
sub-agent (`factory-execute` §1a) whose only job is: *"to actually build this system, what technical
decisions are still unmade?"* It reads the PRD + requirements + the architecture decisions already
written and names what's missing for **this** product. Write what it surfaces into Praxis, resolve
those too, and **loop until it returns nothing new** (loop-until-dry). The critic must **explicitly
interrogate the test strategy**, not just build decisions: *"is the test strategy COMPLETE and
APPROPRIATE for THIS platform?"* — flagging e.g. a mobile app with no device/simulator e2e, a library
with no contract tests, a data pipeline with no data-contract/eval gates, or any project with no CI
or a layer with no binary merge-/release-blocking condition. Each gap becomes a requirement/check in
Praxis and is resolved like the others; the critic does not sign off while a platform-appropriate
layer or the CI gate is missing or unenforced.

## Step 4 — Record the panel-ran episode (the only residue)

When the sweep is done — every requirement challenged, every planning check applied, every
architecture decision and test layer written into Praxis — record **ONE** `praxis_record_episode`
asserting the audit panel ran for `prd-<project>`: what was challenged, which lenses fired, the
critic's loop-until-dry result, and a pointer to the requirements/checks it edited or added. This is
the **only** thing the audit leaves behind besides the graph edits themselves. It is a tiny
assertion-of-record so the act of auditing **cannot be silently skipped** — NOT a findings state
machine, NOT a status manifest. Everything substantive already lives as tickets/checks in Praxis.

```
praxis_record_episode(
  text = "factory-audit ran for prd-<project>: challenged <N> requirements; "
         "lenses fired=[...]; near-dups reconciled=[...]; arch decisions written=[...]; "
         "test layers=[...]; tech-decision critic loop-until-dry passes=<k>, missing=[]",
  derived_from = ["<edited/added requirement ids>", "<check ids>"],
  outcome = "succeeded",
)
```

## Step 5 — How completion is enforced (the single live gate)

There is **no audit-specific Stop gate** and **no audit manifest** to satisfy. The factory's gate
spine is a **single completeness gate** that reads Praxis live and asks one question: *are there
incomplete tickets/checks for this scope?* Because every unresolved audit gap was written back as an
**incomplete requirement or check**, that one gate is automatically the audit's forcing function —
the plan is not blessable while any audit-surfaced requirement/check is still incomplete in Praxis.
The gate is **fail-closed**: if Praxis is unreachable it **BLOCKS**, never fails open (a gate that
can't reach the single source of truth does not let work pass).

So you do not "set status to passed." You make the graph true: tighten/add the requirements, declare
the checks, reconcile the near-dups, record the panel-ran episode. The live gate then sees no
incomplete tickets/checks and lets the plan proceed.

## Step 6 — Mode-aware human moment, then bless

- **Attended:** present the audit's still-open challenges, routed-underspecs, and questions as **one
  batched review** (the concentrated human moment the review-leverage rule wants — not
  one-question-per-turn interruptions). On resolution, every gap is written into Praxis →
  `save_snapshot("prd-<project>")`. After the snapshot lands, **auto-run `factory-review` in PLAN
  mode** over the finalized fact-set (the holistic cold-eyes pass on the whole plan).
- **Unattended (Constitution / owner asleep):** don't ask — route forks to deferred owned-decisions,
  `praxis_record_episode` each, leave the blocking ones as **incomplete** requirements/checks in
  Praxis for morning review, and proceed only on what cleared.

## Never
- Never `save_snapshot` (bless the plan) while any audit-surfaced requirement/check is still
  **incomplete** in Praxis, or any open challenge is unresolved.
- Never write a `.factory/*.json` audit manifest, a findings state machine, or any sidecar status
  file — the audit's output is graph edits + one panel-ran episode. Praxis is the only store.
- Never let the agent that drafted a requirement be its *only* skeptic — use the cold-eyes sub-agent.
- Never "close" a challenge with a free-text note alone — close it with the Praxis write that fixes
  it (edit/add the requirement, declare the check) or a recorded dismissal/deferral episode.
- Never "close" a near-duplicate / overlap challenge without writing it back to the graph
  (`reject_fact` the subsumed loser, or `edit_fact`-narrow + cross-link, or keep-as-distinct with a
  recorded rationale) and **re-saving the `prd-<project>` snapshot**. On the `raw=True` fast-lane this
  write-back is the ONLY dedup step — leaving redundant facts active is a leak.
- Never bless a plan with no automated test strategy, a platform-required layer missing (e.g. a
  mobile build with no device/simulator e2e), or any test layer / CI gate lacking a binary condition
  — those are missing checks/requirements, and the live gate treats them as incomplete.
- Never skip the audit silently — the panel-ran episode is what proves it ran.
