---
name: factory-plan
description: >
  Human-controlled plan-hardening loop for the agent factory. Use to turn a PRD or rough
  feature idea into a self-consistent, fully-specified plan that lives in its own Praxis
  snapshot. The skill pressure-tests, researches, and enforces self-consistency via the
  knowledge graph — it does NOT autonomously author or approve the plan. The human authors
  and clears the gate. Produces a `prd-<project>` snapshot; execution consumes it later.
---

# Factory Plan (plan-hardening)

Planning is **human-controlled**. Your job is to make the human's plan *self-consistent* and
*thoroughly specified* — by pushing back, researching, and using the knowledge graph as the
consistency checker. You never decide what the plan should be, and you never declare it done;
you report what's inconsistent or under-specified, and the human clears the gate.

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

Either mode **stamps which checks it ran/skipped** into the plan snapshot, so a quick pass never
poses as a hardened one.

Then run the tenancy lifecycle through `factory-memory`:
1. **Save-before-clear** (guardrail — never `clear_graph` without a confirmed snapshot of live state).
2. `clear_graph` → clean live scratch.
3. **Mount read-only** the reference snapshots: `general-pool` (general conventions),
   `constitution` (invariants, if it exists), and any relevant prior `prd-<project>` or research
   snapshot. Mounted facts inform retrieval but never enter the PRD snapshot.
4. Write each settled requirement with **`add_insight(..., on_conflict="surface")`** (tabular
   content via the linearizer first), stamping `source="prd-<project>"`, `category="requirement"`,
   and `meta={"requirement_id": "<R-id>"}` so it's citable and the R-id↔fact mapping survives in
   Praxis (read back via `praxis_get_fact`). Surface mode is mandatory during planning.

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

**b. Admission gate + ambiguity forge.** A requirement is not admitted to the graph until it
carries ≥1 **binary acceptance condition** ("when X, the system does Y, observable via Z"). Draft
the candidate condition; the human accepts/edits/rejects. When an answer uses a vague term
("fast", "secure", "most users"), don't accept it — offer multiple-choice disambiguations
(`p95 < 200ms` / `p99 < 1s` / "feels instant in demo") that mint the testable fact. Keep a small
library of ambiguity examples in `general-pool` and grow it (Step 4).

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

## Step 3 — The done-gate (the human clears it; you only report)

A plan is **done** only when all hold — report status against each, never declare it yourself:
- Every requirement maps to ≥1 binary acceptance condition (or is an explicitly-deferred owned decision).
- **Zero unresolved contradictions** in the live graph.
- **No dangling concept reference (H14)** — every domain concept a requirement *references* is
  *defined* by some admitted requirement or explicitly declared out of scope. This is the hole that
  let an undefined "team streak" into prd-team-app: R2 referenced it, nothing defined it, and the
  prose gate admitted R2 anyway. Tag each requirement with the concepts it `defines`/`references`.
- Every **can't-miss failure class** is addressed-or-excluded with logged rationale: data loss,
  auth bypass, irreversible action, silent partial failure.

The mechanical half of this gate (binary-acceptance present, no unquantified vague term, no dangling
reference) is executable, not eyeballed: run `agent_factory.plan_gate.evaluate_plan(requirements)`
and report its `reasons`. It is covered by the eval suite under `evals/cases/plan_gate/` (run
`pytest tests/test_eval_cases.py`) — add a new `case.yaml` there whenever a fresh gate edge case is
found, so the gate's coverage compounds the same way the graph does.

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
