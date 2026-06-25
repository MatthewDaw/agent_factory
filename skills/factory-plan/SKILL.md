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
3. **Mount read-only** the reference snapshots: `planning-knowledge` (general conventions),
   `constitution` (invariants, if it exists), and any relevant prior `prd-<project>` or research
   snapshot. Mounted facts inform retrieval but never enter the PRD snapshot.
4. Ingest the source PRD/idea into the live graph (tabular content via the linearizer).

**Verified Praxis behavior (important):** `add_insight` **auto-resolves** conflicts silently —
the newest fact wins, the loser is moved to `rejected`, and **nothing is flagged in
`get_contradictions`**. There is no MCP toggle to turn auto-resolution off (Praxis gap **H9**).
So the **rejected pile IS the contradiction surface**: after every write batch, audit
`praxis_list_graph(state="rejected")`, and treat any fact you *just submitted* that landed
rejected as a **surfaced conflict** to bring to the human — do not assume a clean
`get_contradictions` means a consistent plan.

## Step 2 — The hardening loop

Work one requirement (or one tight cluster) at a time. For each, run these moves; surface
**one question per turn** using the blocking question tool, single-select with a free-text escape,
and prefer drafting-for-the-human-to-judge over asking-from-blank.

**a. Research before asking.** Pull grounding from the mounted snapshots + repo + (when needed)
web, so you only ask what the artifacts can't answer. Pre-fill inferred details as "inferred —
confirm?" for the human to edit.

**b. Admission gate + ambiguity forge.** A requirement is not admitted to the graph until it
carries ≥1 **binary acceptance condition** ("when X, the system does Y, observable via Z"). Draft
the candidate condition; the human accepts/edits/rejects. When an answer uses a vague term
("fast", "secure", "most users"), don't accept it — offer multiple-choice disambiguations
(`p95 < 200ms` / `p99 < 1s` / "feels instant in demo") that mint the testable fact. Keep a small
library of ambiguity examples in `planning-knowledge` and grow it (Step 4).

**c. Adversarial pass (a skeptic must challenge).** For each requirement, file ≥1 falsifiable
challenge — missing actor, unbounded condition, hidden dependency, unhandled empty/error case —
as a *contradicting* fact, so an unanswered challenge blocks the gate like any contradiction. In
rigorous mode, each gap-lens must explicitly **fire-or-pass** (logged): failure-modes, security,
data-lifecycle, rollback, who-pays-the-tradeoff. Use leading yes/no questions ("so you have NOT
specified what happens on empty input — correct?") to corner vagueness into concrete gaps.

**d. KG self-consistency.** The surface is the **rejected pile**, not `get_contradictions` (see
Verified Praxis behavior above). After admitting a batch, audit `praxis_list_graph(state="rejected")`;
for each fact you just submitted that landed rejected, present a **paired diff** — the active
"winner" vs. the rejected "loser" ("Req A: sessions expire in 24h / Req C: sessions are
persistent") — with resolve / keep-the-rejected (`promote`/`edit`) / keep-both-by-rewording
actions. The human decides; you never let the silent auto-resolution stand unreviewed. Also check
`get_contradictions` for any pairs that *do* surface. Reuse the same machinery as an **oracle**:
to check a requirement against a mounted `constitution` invariant, dependency/spec-registry fact,
or research-evidence fact, the conflict shows up the same way (the violating fact lands rejected
against the mounted truth, or vice versa) — inspect provenance on the pair to tell which side is
the invariant.

## Step 3 — The done-gate (the human clears it; you only report)

A plan is **done** only when all hold — report status against each, never declare it yourself:
- Every requirement maps to ≥1 binary acceptance condition (or is an explicitly-deferred owned decision).
- **Zero unresolved contradictions** in the live graph.
- Every **can't-miss failure class** is addressed-or-excluded with logged rationale: data loss,
  auth bypass, irreversible action, silent partial failure.

**Stop by information-gain, not by exhaustion.** When the next question's expected information
gain is low and the gate is reachable, say so and STOP asking — do not loop. Beware the
under-specification trap: zero contradictions on a thin plan is not "done," it's "nothing was
claimed yet."

When the human clears the gate: `save_snapshot("prd-<project>")` (PRD-only — mounts aren't
carried). Render the prose PRD from the facts for human review. This snapshot is the durable plan;
editing later = `load_snapshot(... replace)` → edit → re-save.

## Step 4 — Compound (improve the tool)

Before finishing, with the human:
- Append any new ambiguity patterns the session caught to the `planning-knowledge` ambiguity-example library.
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
- Never let Praxis's silent auto-resolution stand unreviewed — audit the rejected pile every batch
  and surface each just-rejected submission to the human (a clean `get_contradictions` is NOT proof
  of consistency; gap H9).
- Never `clear_graph` without a confirmed save-before-clear snapshot.
- Never admit a requirement with no acceptance condition and no owned-decision/deferred tag.
- Never let mounted reference knowledge leak into the `prd-<project>` snapshot.
