---
name: factory-plan
description: >
  Human-controlled plan-hardening loop for the agent factory. Use to turn a PRD or rough
  feature idea into a self-consistent, fully-specified plan that lives in its own Praxis
  snapshot. The skill pressure-tests, researches, and enforces self-consistency via the
  knowledge graph — it does NOT autonomously author or approve the plan. The human authors
  and clears the gate. Produces a `prd-<project>` snapshot; execution consumes it later.
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

In this skill: you AUTHOR the FIND set. Plan-hardening admits each settled requirement as a
`source="prd-<project>"` ticket and (via checks) the contract every ticket must later pass — so the loop
above has tickets to find and checks to resolve. You write tickets and checks to Praxis only; you never
write build/claim/pass state (that is the build loop's job) and you keep ZERO side files — the hardened
plan IS the Praxis snapshot, and the audit re-arm leaves only a panel-ran episode, never a state machine.

# Factory Plan (plan-hardening)

Planning is **human-controlled**. Your job is to make the human's plan *self-consistent* and
*thoroughly specified* — by pushing back, researching, and using the knowledge graph as the
consistency checker. You never decide what the plan should be, and you never declare it done;
you report what's inconsistent or under-specified, and the human clears the gate.

**Why the gate sits here (review leverage).** A bad line of *code* costs one bad line; a bad line
of *plan* can spawn hundreds of bad lines of code; a bad line of *research / requirements* can spawn
thousands. Review leverage is inverse to distance-from-execution — so the human's scrutiny and this
skill's rigor concentrate at the plan, where a caught error is cheapest to kill. Spending more
effort hardening a requirement than reviewing the code it later produces is the correct ratio, not
over-caution.

All Praxis access follows the **`factory-memory`** skill's policy (tenancy, `insight` vs
`ingest`, the tabular audit, mount/save rules). Record the session in the event log
(`src/agent_factory/event_log.py`).

## The model: facts are canonical, prose is rendered

**The plan IS the Praxis fact-set plus its contradiction-state — not a hand-typed document.**
The human authors by *answering and triaging*; each settled requirement is ingested as an atomic
fact; the prose PRD is *rendered* from the facts (via the H6 linearizer in
`src/agent_factory/tabular.py`) on demand, never edited by hand. This is what makes the done-gate
a mechanical property of the graph instead of a judgment call.

Escape hatch: a requirement the human deliberately owns but can't yet make testable is recorded
as an **owned decision** fact (tagged as such), not forced binary — but it cannot pass the
done-gate until it has an acceptance condition or is explicitly deferred.

## Step 1 — Mode and setup

Ask the human (blocking, single question) for the **rigor mode**:
- **Quick** — admission gate + contradiction surface only; relaxed pushback depth.
- **Rigorous** — every gap-lens and the full can't-miss checklist.

Either mode **records which lenses it ran/skipped** as a Praxis episode
(`praxis_record_episode`), so a quick pass never poses as a hardened one — that record lives in
Praxis, never in a side file.

Then run the tenancy lifecycle through `factory-memory`:
1. **Save-before-clear** (guardrail — never `clear_graph` without a confirmed snapshot of live state).
2. `clear_graph` → clean live scratch.
3. **Mount read-only** the reference snapshots: `general-pool` (general conventions),
   `constitution` (invariants, if it exists), and any relevant prior `prd-<project>` or research
   snapshot. Mounted facts inform retrieval but never enter the PRD snapshot.
4. **Admit each settled requirement** stamping **`source="prd-<project>"` as the project identity**,
   `category="requirement"`, and `meta={"requirement_id": "<R-id>"}` (tabular content via the
   linearizer first) so it's citable and the R-id↔fact mapping survives (read back via
   `praxis_get_fact`). **Pick the write path by batch size:**

   - **Incremental — minor edits, a single requirement add/change (the default for small work):**
     `praxis_add_insight(..., on_conflict="surface")`. This keeps **live contradiction surfacing**
     (the per-item conflict/claim check) — the safety net the hardening loop (Step 2d) relies on.
     Surface mode is mandatory here.
   - **Bulk raw fast-lane — a fresh whole-plan admission or a large refactor (≳20 requirements, or
     any batch that times out on the per-item path):** `praxis_add_insights(insights=[...],
     raw=True)` in ONE round-trip. `raw=True` still embeds each fact (retrievable) and still redacts
     secrets, but **skips dedup AND the per-item LLM conflict/claim check** — so `on_conflict` is
     ignored and *nothing is surfaced for review*. This is what avoids the timeout the normal path
     hits on large batches (e.g. 71 items) and the dedup that wrongly collapses near-duplicate
     requirements. **You own clean, non-conflicting data on this path** — which is why it is only
     safe HERE: after intake has reconciled/deduped the candidates (factory-intake Step 1), with the
     **audit's cold-eyes conflict pass as the contradiction net** (Step 2d note). Still stamp
     `source`/`category`/`meta` per insight; each result returns `ok`/`id`/`action`/`retrievable` and
     a bad item errors without aborting the rest — check them.

   **`source="prd-<project>"` is the project identity — it is NOT `meta.scope`.** `source` binds the
   requirement to its PRD (`prd-team-app`, `prd-foo`, …) and is what the downstream completeness
   query (`incomplete_requirements(project)` — pass the **BARE** name, e.g. `"team-app"`; the endpoint
   prepends `prd-` itself, so a prefixed `"prd-team-app"` searches `prd-prd-team-app`, returns EMPTY, and
   the build gate would wrongly believe every requirement is done) and the done-gate's `R-HAS-SOURCE` rule
   filter on; `meta.scope` is the orthogonal mvp/post-mvp **tier** tag the build loop reads to pick a tier.
   A requirement tagged only with `scope="team-app"` and **no** `source="prd-<project>"` is the exact
   generation drift that went uncaught: it never matched the completeness filter, so the build
   wrongly believed every requirement was done. Every admitted requirement MUST carry
   `source="prd-<project>"` — there is no source-less requirement.

**Verified Praxis behavior (2026-06-25):** with `on_conflict="surface"`, a detected contradiction
is **surfaced, not auto-resolved** — both facts are kept (incumbent stays `active`, newcomer lands
`proposed`, **neither rejected**) and a **pending pair appears in `praxis_get_contradictions`** with
a resolvable `pair_id`. The human settles it with `praxis_resolve_contradiction(pair_id, keep_id |
custom_text)`. (Without the flag, `add_insight` defaults to `auto_resolve` — newest wins, loser
silently → `rejected`, nothing flagged — which is wrong for planning. Always pass
`on_conflict="surface"`.) The earlier rejected-pile workaround for gap H9 is **retired**.

## Step 2 — The hardening loop

Work one requirement (or one tight cluster) at a time. For each, run these moves; surface
**one question per turn** using the blocking question tool, single-select with a free-text escape,
and prefer drafting-for-the-human-to-judge over asking-from-blank.

**Fan out via Workflow where it helps (the default for a substantial hardening pass; CONSTITUTION
§0).** This loop is not a solo grind — author and run a Workflow to parallelize the expensive parts:
**parallel research sub-agents** to resolve underspecification (the move-2a/underspecification-trigger
"research-resolvable" branch, run as a fan-out instead of one serial read), a **judge panel** to weigh
a contested fork before it reaches the human (move 2c / a genuine product fork), and an **adversarial
reviewer** over the candidate requirement set whose job is to falsify — surfacing missing actors,
unbounded conditions, and dangling concepts as contradicting facts (move 2c). Run gap-finding
**loop-until-dry**: keep fanning out challenge passes until one surfaces nothing new.
**The human-controlled gate is untouched:** workflows *inform* — they research, challenge, and rank —
but they never settle a contradiction, author a fact, or clear the done-gate. The human still answers,
still resolves each pending pair, and still clears Step 3. One decision-maker per slice holds: the
workflow orchestrates finders/reviewers, but you remain the sole agent that writes to the graph.

*Researching to resolve a question* (the PRD's other sections, the codebase, prior snapshots) may
use the **read-only retrieval sub-agent** (factory-execute §1a) so bulk reading doesn't crowd the
planning context — but **read any file the human or the PRD names explicitly fully in your own
context first**; only delegate exploratory reading.

**a. Resolve before you ask (mandatory gate before any question).** Never surface a
decision/fork to the human until you have first tried to answer it from existing sources, in this
order:
1. **The PRD / source text** — re-read the relevant section. If it specifies the answer, use it
   and cite the line; do **not** ask.
2. **Mounted knowledge** — query `get_context` against `general-pool`, `constitution`, and
   any mounted prior `prd-<project>`. If an existing fact/invariant answers it, use it; do not ask.
3. **Conventional default** — if the PRD is *silent* and there is a clear, low-regret conventional
   default (e.g. streak resets to 0 on a miss; DST uses local wall-clock), **take the default**,
   record it with **`praxis_record_episode`** (`text` = the decision + "PRD silent → conventional
   default", `alternatives` = the options not taken), and surface it for *override* rather than
   asking an open question. Do not invent forgiving/clever behavior the PRD didn't ask for — that's
   scope creep.
4. **Only then ask** — reserve a blocking question for a **genuine product fork**: the PRD left it
   open AND no conventional default is clearly right AND reasonable choices materially differ
   (e.g. "is the checklist required for completion?"). When you do ask, say what you already
   checked ("PRD is silent; no convention applies") so the human knows it's a real decision.

The failure mode to avoid: asking the human something the PRD already answers, or manufacturing a
decision out of an edge that has an obvious default. Pre-fill what you resolved as
"resolved from <source>" / "default (PRD silent) — confirm?" so the human edits rather than dictates.

**The underspecification trigger (research or ask — never silently default).** The concrete signal
that fires this ladder: *a candidate cannot be given a binary acceptance condition from the sources
in hand.* When that fires, classify the gap and route deterministically — do not guess a value:
1. **Research-resolvable** — the answer plausibly already exists (another PRD/spec section, the
   wireframe, a mounted `prd-*`/`constitution`, a convention, external prior art). **Dispatch the
   read-only research sub-agent** (factory-execute §1a) to go find it, then re-attempt the
   acceptance condition. *Reading more is the first move, not asking.*
2. **Convention-resolvable** — PRD silent, one clear low-regret default. Take it,
   `praxis_record_episode`, surface for override.
3. **Genuine product fork** — reasonable choices materially differ and no default is clearly right.
   **Ask the human** (blocking), stating what you already checked.
4. **Unknowable now** — record as an owned-decision / deferred fact; it cannot pass the done-gate
   until resolved.

**Anti-masking guard:** a "conventional default" may never be used to paper over a genuine fork. If
you can't tell whether something is a safe default or a real product decision, treat it as a fork
and ask. Silently defaulting an underspecified requirement is exactly the failure this trigger
exists to prevent — an underspecified area should *visibly* become research, a question, or a
flagged deferral, never a quiet guess.

**b. Admission gate + ambiguity forge.** A requirement is not admitted to the graph until it
carries ≥1 **binary acceptance condition** ("when X, the system does Y, observable via Z"). Draft
the candidate condition; the human accepts/edits/rejects. When an answer uses a vague term
("fast", "secure", "most users"), don't accept it — offer multiple-choice disambiguations
(`p95 < 200ms` / `p99 < 1s` / "feels instant in demo") that mint the testable fact. Keep a small
library of ambiguity examples in `general-pool` and grow it (Step 4).

**Tag each acceptance condition `automated` or `manual`** (in `meta`): *automated* = a command the
loop runs itself (test / build / type-check / lint — the default; always prefer it); *manual* =
needs a human to confirm (UX feel, a visual, a real external side-effect) and the executor **may
not self-check it**. The split drives phase-gate pauses in attended execution; an unattended run
(Constitution) auto-checks the automated ones and records each manual one as a deferred owned
decision for morning review.

**c. Adversarial pass (a skeptic must challenge).** For each requirement, file ≥1 falsifiable
challenge — missing actor, unbounded condition, hidden dependency, unhandled empty/error case —
as a *contradicting* fact, so an unanswered challenge blocks the gate like any contradiction. In
rigorous mode, each gap-lens must explicitly **fire-or-pass** (logged): failure-modes, security,
data-lifecycle, rollback, who-pays-the-tradeoff. Use leading yes/no questions ("so you have NOT
specified what happens on empty input — correct?") to corner vagueness into concrete gaps.

**d. KG self-consistency.** Because writes use `on_conflict="surface"`, the surface is
**`praxis_get_contradictions`** — the proper queue. After admitting a batch, read it and present
each pending pair as a **paired diff** ("Req A: sessions expire in 24h / Req C: sessions are
persistent"). The human settles each with `praxis_resolve_contradiction(pair_id, keep=…)` —
`keep="<id>"` to keep one side, **`keep="all"` when it's a false positive** (both genuinely hold,
e.g. different actors — keeps both active, nothing lost), or `custom_text` to reconcile. You never
settle it yourself. Reuse the
same machinery as an **oracle**: a requirement that conflicts with a mounted `constitution`
invariant, dependency/spec-registry fact, or research-evidence fact surfaces as the same kind of
pending pair — inspect provenance/`source` on each side to tell which is the invariant vs. the new
requirement. (Belt-and-suspenders: also glance at `praxis_list_graph(state="rejected")` in case a
write slipped through on `auto_resolve` — but with surface mode the pending queue is the surface.)

**Raw bulk caveat.** If the plan was admitted via the `raw=True` fast lane (Step 1 item 4), Praxis
ran **no** conflict detection, so `praxis_get_contradictions` is empty *by construction* — that
emptiness is NOT evidence of consistency. For a raw-admitted set the contradiction net is (1)
intake's reconcile/dedup (kills duplicates *before* the write) and (2) **factory-audit's cold-eyes
cross-requirement conflict challenges** (genuine clashes, plus clashes with mounted
`constitution`/`prd-*` invariants). Treat the audit — not the empty queue — as the contradiction gate
for bulk inserts. (Incremental edits still surface live via move d above.)

**e. A human correction is a fact, not an override.** When the human corrects a *factual* claim
(not merely states a preference), admit the correction the same way as any requirement —
`add_insight(..., on_conflict="surface")` — so that if it contradicts an admitted requirement or a
mounted `constitution`/`prd-*` invariant it lands in the **same contradiction queue** (move d)
instead of being silently absorbed. The human is in control of the plan, but a correction that is
itself wrong, or that clashes with something already settled, should *surface* and be reconciled,
not patched in blind. And when a correction invalidates earlier research, re-derive what rested on
it — run `praxis_get_stale_derivations` on the affected fact ids and revisit those — rather than
fixing only the one line the human pointed at. (This is the disciplined version of "verify the
correction": route it through the graph you already trust, don't kick off speculative re-research.)

## Step 3 — The done-gate (the human clears it; you only report)

A plan is **done** only when all hold — report status against each, never declare it yourself:
- Every requirement maps to ≥1 binary acceptance condition (or is an explicitly-deferred owned decision).
- **Every requirement carries `source="prd-<project>"`** (the project identity). A requirement with
  a missing or mis-scoped source is mechanically rejected by the gate's `R-HAS-SOURCE` rule below.
- **Zero unresolved contradictions** in the live graph.
- **No dangling concept reference (H14)** — every domain concept a requirement *references* is
  *defined* by some admitted requirement or explicitly declared out of scope. This is the hole that
  let an undefined "team streak" into prd-team-app: R2 referenced it, nothing defined it, and the
  prose gate admitted R2 anyway. Tag each requirement with the concepts it `defines`/`references`.
- Every **can't-miss failure class** is addressed-or-excluded with logged rationale: data loss,
  auth bypass, irreversible action, silent partial failure.

The mechanical half of this gate (binary-acceptance present, no unquantified vague term, no dangling
reference, **and project source present** — `R-HAS-SOURCE`) is executable, not eyeballed: run
**`agent_factory.plan_gate.evaluate_plan(requirements, project="<project>")`** — passing the project
explicitly, with **each requirement carrying its `source="prd-<project>"`** — and report its
`reasons`. The `project=` argument is mandatory: with it the gate requires every requirement's
`source` to equal `prd-<project>` exactly, so a source-less or mis-scoped plan is mechanically
**rejected** (this is the drift that went uncaught when the gate was run without project+source). It
is covered by the eval suite under `evals/cases/plan_gate/` (run
`pytest tests/test_eval_cases.py`) — add a new `case.yaml` there whenever a fresh gate edge case is
found, so the gate's coverage compounds the same way the graph does.

**The judgment pushback runs as a separate, enforced step.** Move 2c's adversarial pass is the
inline, interactive version for human-led planning. When you arrive here via the intake pipeline,
the cold-eyes adversarial + underspecification audit is **`factory-audit`** — a distinct step over
the admitted-but-not-yet-blessed set. **It carries no findings state machine of its own:** every
finding becomes a first-class Praxis node the same done-gate already reads — an underspecified
requirement is marked incomplete, a missing consideration is admitted as a new requirement/check —
so there is nothing to track on the side. The ONLY residue the audit leaves is one **panel-ran
assertion**: `praxis_record_episode` recording that the audit ran over this `source="prd-<project>"`
set (and its verdict), so the act of auditing cannot be silently skipped. The factory has a SINGLE Stop hook
(`build_completeness_gate`, for the BUILD phase); planning is **human-gated**, not hook-gated. Before
blessing, two things must hold, checked **live from Praxis** (never a manifest file): (a)
`plan_gate.evaluate_plan` passes over the live requirements, and (b) that panel-ran episode exists. The
human clears the gate only once both hold; any gap the audit admits becomes a Praxis ticket/check that
the one build gate later forces to done. Run `factory-audit` before `save_snapshot`.

**Stop by information-gain, not by exhaustion.** When the next question's expected information
gain is low and the gate is reachable, say so and STOP asking — do not loop. Beware the
under-specification trap: zero contradictions on a thin plan is not "done," it's "nothing was
claimed yet."

When the human clears the gate: `save_snapshot("prd-<project>")` (PRD-only — mounts aren't
carried). Render the prose PRD from the facts for human review. This snapshot is the durable plan;
editing later = `load_snapshot(... replace)` → edit → re-save.

## Step 4 — Compound (improve the tool)

Before finishing, with the human:
- Append any new ambiguity patterns the session caught to the `general-pool` ambiguity-example library.
- Offer to **promote** genuinely-new cross-project invariants into the `constitution` snapshot.
- Write **decision + derivation records** to the event log (why each threshold/decision, derived
  from which fact/source) — the local fill for Praxis gaps H4/H5.
- Reserve an **outcome slot** per requirement ID so post-execution verification can later fold back
  a trust score (H1). *(This loop only closes once execution feeds back — deferred until M1b.)*

## Interaction rules
- One question per turn (blocking tool, single-select + free-text escape). Never stack questions.
- Open-ended only when the answer is inherently narrative or a menu would bias it.
- Draft-for-judgment over ask-from-blank wherever possible.
- Cite the fact(s) that grounded each suggestion (provenance).

## Never
- Never autonomously author or approve the plan, or declare the gate cleared.
- Never write a planning fact without `on_conflict="surface"` — `auto_resolve` silently rejects the
  loser and hides the conflict.
- Never treat a write timeout as a failure — the write usually landed; **read back** (`list_graph` /
  `get_context`) before retrying, or you'll create duplicates (see `factory-memory`).
- Never `clear_graph` without a confirmed save-before-clear snapshot.
- Never admit a requirement with no acceptance condition and no owned-decision/deferred tag.
- Never let mounted reference knowledge leak into the `prd-<project>` snapshot.
