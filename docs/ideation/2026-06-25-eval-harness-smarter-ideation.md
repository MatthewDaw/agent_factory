---
date: 2026-06-25
topic: eval-harness-smarter
focus: do a little research and see if we can make the eval harness smarter
mode: repo-grounded
---

# Ideation: Making the Eval Harness Smarter

## Grounding Context

**Codebase context.** The agent-factory eval harness is a small Python suite:
`evals/cases/<name>/case.yaml` files declare an input scenario + reference deterministic
check functions by `"module:function"`; `evals/checks.py` holds component runners + checks
that return structured `reasons`; `evals/case_def.py` loads YAML; `tests/test_eval_cases.py`
discovers and parametrizes every case (with a guard test that fails on zero discovered cases).
The only component under test today is the deterministic `plan_gate`
(`src/agent_factory/plan_gate.py`): rules are (a) every requirement has a binary acceptance
condition, (b) no unquantified vague terms, (c) no dangling concept references (H14). Cases are
added by accretion — every real escape found in live planning becomes a `case.yaml`. It mirrors
a larger Praxis knowledge-graph eval harness (RED/xfail cases, LLM-judge rubrics, cached
embedders/cassettes).

**External context (research).** Property-based testing (Hypothesis) + metamorphic relations
generate/relate cases instead of hand-authoring; mutation testing (mutmut, ~80%+ kill-rate bar)
measures whether the suite actually catches gate regressions; LLM-judge frameworks (DeepEval,
Inspect, promptfoo, Braintrust) with rubric-decomposition + different-model judging; golden/
cassette replay (syrupy, vcrpy) for non-determinism; adversarial/red-team case generation;
"eval the evaluator" meta-evals (seeded poison fixtures, flake/variance detection, RED→GREEN
locking); coverage taxonomy tagging cases to rule IDs (GCC/LLVM conformance suites).

**Past learnings (this repo).** RED→GREEN must be *observed* failing before the fix (a
green-from-birth test proves nothing); real escapes found live (H6/H10/H14) are the highest-value
cases; LLM-judge must be a *different* model than the generator, scoped to soft outputs, used as
park/proceed triage, kept *out* of the green-locking suite; non-deterministic/infra concerns are
explicitly NOT eval-able as `case.yaml` and route to stress tests so the deterministic suite never
goes flaky.

## Topic Axes

- Case authoring & generation (how cases come to exist)
- Check / oracle power (what a check can assert; deterministic vs judge)
- Suite adequacy / meta-eval (proving the suite catches regressions)
- Coverage & taxonomy tracking (which rules / equivalence classes have cases)
- Component scope (beyond `plan_gate`)

## Ranked Ideas

### 1. Escape → RED autopromotion (the harness ingests its own exhaust)
**Description:** When the factory's verify step (or a recorded Praxis outcome) shows a plan the
gate wrongly admitted, a hook auto-scaffolds a `case.yaml` seeded with the offending input,
tagged RED and locked; a human ratifies rather than authors from scratch. Absorbs the proactive
adversarial-generator variant (a red-team loop that manufactures escapes in a sandbox and locks
the successful ones).
**Axis:** Case authoring & generation
**Basis:** `direct:` — the factory already records outcomes/episodes to Praxis; the
`run_plan_gate` input shape (`requirements`, `out_of_scope`) templates directly from a transcript.
Harvesting is 100% manual today.
**Rationale:** Real escapes are the highest-value cases and the bottleneck is human transcription,
not insight; this makes suite strength compound with factory mileage instead of human diligence.
**Downsides:** Needs a trusted distill+ratify step; risk of low-quality auto-cases without a human
gate.
**Confidence:** 85%
**Complexity:** High
**Status:** Unexplored

### 2. Mutation-test the gate to grade the suite
**Description:** Run `mutmut` against `plan_gate`/`checks.py`; the health metric becomes *mutant
kill-rate*, not case-count. Each surviving mutant is a machine-readable description of an
undetected regression → becomes a "wanted case" worklist, optionally enforced as a PR merge gate.
**Axis:** Suite adequacy / meta-eval
**Basis:** `external:` mutmut/cosmic-ray (80%+ kill-rate is a credible bar) + `direct:`
`gate_rejects(reason_contains=None)` passes on *any* rejection, so a weak case pins almost nothing
and nothing detects that today.
**Rationale:** Replaces "green = good" false confidence with proof the suite actually constrains
the gate; turns adequacy from a vibe into a falsifiable number.
**Downsides:** Mutation runs add CI time; needs a kill-rate threshold policy.
**Confidence:** 88%
**Complexity:** Medium
**Status:** Unexplored

### 3. RED-proof field — record the observed failure, enforce falsifiability
**Description:** Add a `red_proof` field to `case.yaml` (commit/run-id where the case was observed
failing). A meta-test quarantines cases that have never been red as "decorative," excluded from
coverage claims.
**Axis:** Suite adequacy / meta-eval
**Basis:** `direct:` — `case_def.py` has no failure-state field and `test_eval_cases.py` only
asserts `result.passed`; the project believes in RED→GREEN (factory-verify) but cannot enforce it.
**Rationale:** A green-from-birth test proves only that code and test agree, not that the test
*can* fail; provenance of failure is data the harness currently throws away.
**Downsides:** Requires a convention for pinning the "broken" state (commit ref vs stored verdict
fixture).
**Confidence:** 80%
**Complexity:** Low
**Status:** Unexplored

### 4. Rule-ID taxonomy + coverage matrix (≥1 RED case per rule)
**Description:** Give each gate rule a stable ID (`R-ACCEPT-BINARY`, `R-NO-VAGUE`,
`R-NO-DANGLING`); `evaluate_plan` emits which rule produced each reason; a meta-test fails if any
shipped rule has zero exercising (or zero RED) cases. Render a rule×case matrix with holes
highlighted.
**Axis:** Coverage & taxonomy tracking
**Basis:** `external:` GCC/LLVM conformance suites tag every test to a rule + `direct:` checks
already return structured `reasons` that map cleanly to rule IDs.
**Rationale:** Adding a rule with no failing case is the silent-gap version of green-from-birth;
a conformance matrix makes the gap impossible by construction instead of trusting accretion.
**Downsides:** Small API change to surface rule IDs in `reasons`; cases must declare the rules
they exercise.
**Confidence:** 85%
**Complexity:** Low–Medium
**Status:** Unexplored

### 5. Generative coverage: metamorphic relations + property-based invariants
**Description:** A registry of transformations that must preserve or predictably flip the verdict
(reorder requirements → same; strip the acceptance condition → PASS→FAIL; inject a synonym vague
term → still FAIL), plus Hypothesis invariant fuzzing that shrinks any violation to a minimal
`case.yaml` saved as a permanent regression case.
**Axis:** Case authoring & generation (generative)
**Basis:** `direct:`/`external:` metamorphic testing + Hypothesis `st.builds()`; solves the oracle
problem — you assert relations between transformed inputs, not absolute verdicts.
**Rationale:** Turns one hand-written case into dozens for free and reaches the weird input regions
where escapes actually live, rather than only scenarios a human imagined.
**Downsides:** Generated cases need minimization/curation to stay legible; some relations are
subtle to state correctly.
**Confidence:** 78%
**Complexity:** Medium
**Status:** Unexplored

### 6. LLM-judge triage lane, structurally fenced from the green lock
**Description:** Add an optional `judge_checks` slot + a separate `-m judge` test lane that runs
rubric judges as park/proceed triage only, asserts the judge model ≠ generator, and never
contributes to the deterministic green lock. Requires the small refactor to produce verdicts
*inside* the test body rather than at pytest collection time (today `_case_check_params()` runs
every verdict at import).
**Axis:** Check / oracle power
**Basis:** `direct:` factory-verify already mandates external-signal-only, different-model judges
used as escalation triage; `EvalCase` has no slot keeping soft checks out of the lock.
**Rationale:** Lets soft outputs (no deterministic oracle) get coverage without re-flaking the
deterministic suite — the exact failure mode the project's own rules warn against.
**Downsides:** Introduces a model dependency + cassette/replay needs for reproducibility.
**Confidence:** 80%
**Complexity:** Medium
**Status:** Unexplored

### 7. Generalize to a multi-component `Gate` contract
**Description:** Refactor so `plan_gate` is one implementation of a generic contract (input schema,
rule-ID set, structured reasons); new components (the verify-gate, a Praxis-writeback validator,
or the plan-skill→gate *pipeline* as a unit) plug in and inherit the whole meta-eval machinery
(taxonomy, mutation, autopromotion) for free. A meta-test asserts every registered component has
≥1 case.
**Axis:** Component scope
**Basis:** `direct:` `COMPONENT_RUNNERS = {"plan_gate": run_plan_gate}` is single-entry and
`produce_verdict` raises on anything else; nothing proves the harness generalizes.
**Rationale:** Highest second-order payoff — every mechanism in #1–#5 applies to every future
evaluated component at zero marginal cost; the first second component (esp. the plan-skill→gate
pipeline) surfaces every baked-in `plan_gate` assumption.
**Downsides:** Upfront refactor with no immediate new coverage; contract design must not overfit
to `plan_gate`.
**Confidence:** 82%
**Complexity:** Medium
**Status:** Unexplored

> **Suggested sequence:** #3 + #4 are the cheap foundation (small, enable everything) → #2 proves
> the suite works → #1 + #7 are the compounding payoff → #5 + #6 are the generative / soft-output
> expansion.

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | Decouple verdict from collection time | Absorbed into #6 as the enabling refactor |
| 2 | Check-strength linter (no-op detection) | Absorbed into #2 (mutation testing covers it) |
| 3 | Differential N-version oracle | Strong but heavier — defer to brainstorm |
| 4 | Promote plan-skill→gate *pipeline* as the unit | Strong (real mis-tag blind spot) — folded into #7's first second-component |
| 5 | Trust-weighted oracle from Praxis outcome history | `reasoned:`-only / speculative — better as a brainstorm variant |
| 6 | Corpus minimization; SPC control charts over time | Premature — need suite volume the 4-case suite doesn't have yet |
| 7 | Non-deterministic-case stress-lane guard | Good hygiene, low urgency — cheap to add later |
| 8 | Provenance ledger + recurrence count | Partly subsumed by #1's provenance |
| 9 | Epidemiological R0 escape surveillance | Vivid but exotic — subsumed by #5's metamorphic sibling generation |
