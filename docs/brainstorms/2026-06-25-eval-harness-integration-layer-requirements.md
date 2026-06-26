---
date: 2026-06-25
topic: eval-harness-integration-layer
status: ready-for-planning
origin: docs/ideation/2026-06-25-eval-harness-smarter-ideation.md
---

# Eval Harness as the Factory's Self-Test Integration Layer

## Problem Frame

The agent-factory eval harness today is a YAML-case + pytest runner over a single
deterministic component, `plan_gate` (`src/agent_factory/plan_gate.py`). It works, but it
has three structural weaknesses that this brainstorm addresses:

1. **It can't prove its own adequacy.** A passing suite tells us the cases agree with the
   gate, not that the suite would *catch a regression*. Nothing detects a weak case
   (`gate_rejects(reason_contains=None)` passes on any rejection) or a green-from-birth case
   that never actually failed.
2. **It doesn't know which rule a case exercises.** `plan_gate` has three named rules but the
   suite has no inventory mapping cases to rules — a rule can ship with zero exercising cases
   (exactly the silent gap that let H14, the undefined "team streak", through prose review).
3. **It's single-component and manually fed.** It only tests `plan_gate`; the factory has
   other gates (verify, memory-audit) with no harness. The highest-value cases — real escapes
   found live (H6/H10/H14) — are harvested by hand, so suite strength depends on human
   diligence rather than factory mileage.

The opportunity: make the harness the factory's **self-test integration layer** — a uniform
contract every factory gate implements, deterministic meta-eval that proves the suite catches
regressions, and a loop that harvests real escapes from the existing event log into locked
regression cases. The evidence this is the real problem is direct: we hit H14 live this week,
and the only reason it became a test was manual transcription.

**Primary beneficiary:** the factory operator (the human running plan→execute→verify), who
needs to trust that "suite green" means "the gates are actually guarded," and who today must
hand-write every regression case.

---

## Goal & Non-Goals

**Goal.** A multi-component eval harness with (a) a uniform `Gate` contract, (b) deterministic
meta-eval that makes suite adequacy provable (rule coverage, falsifiability, mutation
kill-rate), and (c) a human-ratified loop that harvests real escapes from the event log into
locked RED cases — built on `plan_gate` and shaped so `verify` and `memory-audit` plug in later.

**Non-goals (this iteration).**
- LLM-judge triage lane (ideation #6) — deferred; the green-locking suite stays deterministic.
- Metamorphic / property-based case generation (ideation #5) — deferred.
- Actually wiring `verify` and `memory-audit` as live gates — the contract must *fit* them, but
  building their adapters is follow-up work.
- Any non-deterministic concern (latency, concurrency, persistence) — routed to stress tests by
  design, never admitted to the deterministic suite.

---

## Key Decisions

**KD1 — The integration spine is the existing event log, not a new mechanism.**
`src/agent_factory/event_log.py` already defines a closed event vocabulary including
`gate_result` ("a verification gate outcome") and `outcome` ("final success/failure"). Gates
emit `gate_result` carrying their verdict + rule-IDs; the harvest loop reads `gate_result` +
`outcome` from `runs/<run_id>/events.jsonl`. No new transport is introduced. *(see origin:
ideation #1, #7)*

**KD2 — Harvesting covers false-admits only; mutation + hand-authored cases cover false-rejects.**
An escape is detectable from the log when a gate **passed** (admitted) but the task **outcome
failed** — a false-admit (H14's class). A **false-reject** (gate wrongly blocked a good plan)
never produces an outcome to contradict, so it is structurally invisible to log harvesting. This
is an accepted, explicit coverage split: the harvest loop owns false-admits; mutation testing
and hand-authored reject cases own false-rejects. The harness must state this boundary, not
paper over it.

**KD3 — RED-proof is dual-sourced.** A case is "falsifiable" (a real guard, not a tautology)
only if it has been observed failing. Harvested cases carry their escape as natural RED evidence
(the `gate_result` that recorded the wrong verdict). Hand-authored cases assert RED against a
stored **"broken-gate" fixture** (a pinned mutant of the gate) rather than a git commit-ref —
chosen for portability across worktrees and time. Commit-ref is the recorded alternative.

**KD4 — The `Gate` contract models deterministic input→verdict→rule-IDs gates; external-signal
gates plug in via an adapter.** `plan_gate` and `memory-audit` fit the contract directly. The
`verify` gate is external-signal (test/build/lint exit codes), so it conforms by wrapping those
signals in the same verdict+rule-ID shape, not by adopting the same structured input. The
contract must not be over-fit to `plan_gate`.

**KD5 — Adequacy is measured, not assumed.** The suite's health metric becomes mutation
kill-rate (via `mutmut`) plus rule-coverage completeness, replacing case-count. A surviving
mutant is a machine-readable description of an undetected regression and becomes a worklist item.

---

## Requirements

### Gate contract & integration

- **R1.** Define a uniform `Gate` contract: an input scenario → a verdict (`admitted` / rejected
  or pass/fail) + structured `reasons`, each reason tagged with a stable **rule-ID**. `plan_gate`
  is refactored to be one implementation of this contract without changing its current behavior.
- **R2.** A component registry maps component name → gate implementation; the eval runner
  produces a verdict by dispatching through the registry. A meta-check asserts every registered
  component has ≥1 case.
- **R3.** Gates emit a `gate_result` event (existing event-log type) carrying the component name,
  verdict, and the rule-IDs that fired. This is the harvest loop's data source.
- **R4.** The contract is demonstrated to fit a second component shape: provide a contract-level
  fit note (or a thin reference adapter) for the external-signal `verify` gate, proving the
  contract is not `plan_gate`-specific (KD4). Building the live verify/memory gates is out of
  scope.

### Rule-ID taxonomy & coverage

- **R5.** Each `plan_gate` rule carries a stable rule-ID (e.g. `R-ACCEPT-BINARY`, `R-NO-VAGUE`,
  `R-NO-DANGLING`); `evaluate_plan` surfaces which rule produced each reason.
- **R6.** Each `case.yaml` declares the rule-ID(s) it exercises. A meta-test fails if any shipped
  rule has zero exercising cases **or** zero RED cases. A rule×case coverage matrix is renderable
  with holes highlighted.

### Falsifiability (RED-proof)

- **R7.** Each `case.yaml` records RED-proof: the evidence it was observed failing (harvested:
  the originating `gate_result`; hand-authored: the broken-gate fixture it fails against, per
  KD3). A meta-test quarantines cases with no RED-proof as "decorative," excluded from coverage
  claims.

### Suite adequacy (mutation)

- **R8.** Mutation testing runs against the gate logic + check functions (`mutmut`); the harness
  reports a mutant kill-rate. Surviving mutants are emitted as a structured "wanted-case"
  worklist. A kill-rate threshold policy is defined (target ≥80%); whether it blocks CI is an
  open question (OQ3).

### Escape harvesting

- **R9.** A harvester reads `runs/<run_id>/events.jsonl`, pairs `gate_result: passed` with a
  later `outcome: failed` for the same task, and scaffolds a draft `case.yaml` seeded with the
  offending input + a RED-proof reference (false-admits only, per KD2).
- **R10.** Harvested cases land in a **quarantine / proposed** state and require explicit human
  ratification before joining the locking suite — the human curates, never authors from scratch.
- **R11.** Harvesting is idempotent: re-running over the same log does not produce duplicate
  draft cases (dedupe on the originating event identity / input signature).

### Boundary enforcement

- **R12.** The case loader refuses cases that encode non-deterministic concerns (time, ordering,
  IO-shaped fields) and points them to a separate stress lane — the deterministic suite never
  goes flaky (ideation rejection #7, promoted to a hard guard).

---

## Scope Boundaries

**In scope:** R1–R12 on `plan_gate`, with the contract shaped for verify/memory.

**Deferred to follow-up work (plan-local sequencing):**
- Live `verify` and `memory-audit` gate adapters (contract-ready here, built later).
- Mutation kill-rate as a hard CI merge gate (start as a report; OQ3).

**Deferred for later (separate brainstorm):**
- LLM-judge triage lane (ideation #6).
- Metamorphic + property-based generative coverage (ideation #5).
- Corpus minimization / SPC control charts (need suite volume first).

**Outside this iteration's identity:**
- False-reject harvesting from the event log — structurally impossible (KD2); not a backlog item.
- Writing harvested cases straight into the locking suite without human ratification (KD/R10).

---

## Success Criteria

- **SC1.** Removing or weakening any single `plan_gate` rule causes at least one case to go RED
  (provable via mutation: kill-rate ≥ target, no surviving mutant on a shipped rule).
- **SC2.** A shipped rule with no exercising case (or no RED case) fails CI — the H14-class
  silent gap is impossible by construction.
- **SC3.** A case that has never been observed failing cannot contribute to a coverage claim
  (RED-proof enforced).
- **SC4.** A false-admit recorded in an event log becomes a draft RED case with zero hand-typing;
  a human ratifies it into the suite in one step.
- **SC5.** The harness verdict path runs through the `Gate` contract for `plan_gate`, and a
  second component shape (external-signal verify) is shown to conform without changing the
  contract.
- **SC6.** The coverage split is legible: docs/output state that harvesting covers false-admits
  and mutation + hand-authored cases cover false-rejects.

---

## Acceptance Examples

- **AE1 (rule coverage).** Add a new rule to `plan_gate` without adding a case → the rule-coverage
  meta-test fails naming the uncovered rule-ID.
- **AE2 (falsifiability).** Author a `case.yaml` with no RED-proof → it is quarantined and does
  not count toward coverage; the meta-test reports it.
- **AE3 (mutation).** Mutate `R-NO-DANGLING` (e.g. make the dangling-reference check always pass)
  → at least one case kills the mutant; kill-rate report reflects it.
- **AE4 (harvest false-admit).** An event log where `plan_gate` emitted `gate_result: passed` and
  verify emitted `outcome: failed` for the same task → harvester produces one draft `case.yaml`
  seeded with that input + RED-proof, in quarantine.
- **AE5 (harvest idempotent).** Re-run the harvester over the same log → no new draft case.
- **AE6 (boundary guard).** A `case.yaml` carrying a latency/ordering field → loader refuses it at
  discovery with a pointer to the stress lane.
- **AE7 (contract fit).** The external-signal `verify` shape is expressed as a `Gate` verdict +
  rule-IDs via the adapter note/reference, with no change to `plan_gate`'s contract.

---

## Outstanding Questions

- **OQ1 (planning).** Exact storage shape for rule-IDs in `reasons` — structured field vs parseable
  prefix. Knowable at plan time from the `plan_gate` code.
- **OQ2 (planning).** Where quarantined/proposed harvested cases live on disk (subdir vs a
  `status:` field in `case.yaml`) and how ratification promotes them.
- **OQ3 (product/ops).** Does mutation kill-rate block CI, or report only, in this iteration?
  Default: report-only first, gate later once the threshold is calibrated.
- **OQ4 (planning).** Broken-gate fixture mechanics for hand-authored RED-proof (one canonical
  mutant per rule vs a single all-rules-off fixture).
- **OQ5 (integration).** Does the harvester read the event log directly, or should harvesting
  also (later) cross-reference Praxis outcomes? This iteration: event log only (local, no Praxis
  dependency) — Praxis cross-referencing is a deferred enrichment.

---

## Dependencies & Assumptions

- **Assumes** the event log (`event_log.py`) remains the local source of `gate_result` / `outcome`
  data (it is, per its own design note). Gates must actually emit `gate_result` — today
  `plan_gate` is invoked by the skill but does not yet emit the event; R3 closes that.
- **Assumes** `mutmut` (or equivalent) is acceptable as a dev dependency.
- **Independent of** the in-flight Praxis write-path fixes — this work is local to the factory
  repo and does not touch Praxis.
