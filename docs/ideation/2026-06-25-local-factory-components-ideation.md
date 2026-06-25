---
date: 2026-06-25
topic: local-factory-components
focus: how to build the local components of the agent coding factory
mode: repo-grounded
---

# Ideation: Building the Local Factory Components

Ideation over the components in [`../factory-local-components.md`](../factory-local-components.md),
grounded in [`../agent-coding-factory-reference.md`](../agent-coding-factory-reference.md) and the
Praxis holes in [`../praxis-gaps.md`](../praxis-gaps.md). Fixed constraints: **single agent**, **thin
harness**, Praxis owns the *knowing* system.

## Grounding Context (Codebase)
Greenfield Python repo. Praxis (KG over HTTP/MCP) owns durable facts, hybrid retrieval, dedup/merge,
contradiction detection + resolution (gated writes), bitemporal `as_of`, mountable read-only overlays,
provenance. We build the *doing* system + glue locally; all Praxis access flows through one knowledge
port. Known Praxis holes the local side must work around: H1 (no outcome/trust score on facts),
H4 (no first-class episodic/decision record), H5 (no derivation edges), H6 (tabular ingestion
under-emits — shim designed). Key research: intrinsic self-correction degrades coding (correction must
be external-signal-grounded); LLM-as-judge needs a separate model; structural erosion is structural
(needs complexity-delta gates, not prompt hints); context rot at 8–12 round-trips; error compounding
(1-p)^N; single-agent ≥ multi-agent at equal token budget; persistent memory ~15–28% repeat-task savings.

## Topic Axes
1. Knowledge port (the Praxis chokepoint)
2. Plan-building pipeline (PRD → spec → task DAG)
3. Single-agent execution + verification loop
4. Long-horizon control & context engineering (tiering over Praxis)
5. Observability + compounding write-back loop

## The through-line
The local side's reason to exist is to **manufacture, from an event log, the three things Praxis
doesn't store** (outcome scores H1, episodic records H4, derivation edges H5) — and to keep every run
**reproducible** so that log is trustworthy. Most survivors orbit that.

## Ranked Ideas

### 1. The event log is the compounding spine
**Description:** One append-only structured event log (every decision, tool call, gate result, outcome)
is the single artifact from which everything else is derived — where H1 outcome scores, H4 episodic
decision-records, and H5 derivation edges get *manufactured* before write-back. Long-horizon control and
write-back become pure functions over this log (replayable, offline-testable). Causal happens-before
edges let any bad output be traced to the fact/plan-node that caused it.
**Axis:** 5 — Observability + write-back
**Basis:** `direct:` H1/H4/H5 are exactly the holes the local side must produce; `external:` Lamport
happens-before causality, cross-session "dreaming" pattern extraction.
**Rationale:** Every other compounding mechanism is downstream of this; get the schema wrong and nothing compounds.
**Downsides:** The schema is a one-way door — expensive to change later.
**Confidence:** 88% · **Complexity:** Medium · **Status:** Unexplored

### 2. The knowledge port is an asymmetric write-gate, not a symmetric retrieval layer
**Description:** Reads delegate straight to Praxis hybrid retrieval (cheap, near-direct — don't
reimplement ranking). Writes go through one narrow gate: provenance stamp, git/KG/ephemeral router
(reject undeclared), never block on `/ingest` (a local journal drains async + audits the rejected pile —
the H6 shim lives here). Symmetric ports throttle reads to protect writes; split them.
**Axis:** 1 — Knowledge port
**Basis:** `direct:` `/ingest` async, one-port mandate, H6 shim; `reasoned:` reads and writes have
different blast radii.
**Rationale:** Keeps one chokepoint *for writes*, where policy matters, without starving context on reads.
**Downsides:** "Reads bypass, writes gate" is a more nuanced contract to hold.
**Confidence:** 82% · **Complexity:** Medium · **Status:** Unexplored

### 3. Snapshot-isolated, reproducible runs; the agent is disposable
**Description:** Pin a single `as_of`/mounted snapshot at kickoff so all reads see one consistent
knowledge version even as write-backs land (MVCC-style). Treat the agent as disposable and frequently
re-spawned, reconstructing working state from Praxis + the event log each cycle rather than accumulating
a context buffer that rots. Test: kill at round-trip 9, respawn, lose nothing.
**Axis:** 4 — Long-horizon control
**Basis:** `direct:` bitemporal `as_of` + mounts; `external:` MVCC snapshot isolation, context rot 8–12,
erosion is structural.
**Rationale:** If erosion/rot are structural, making session length irrelevant is the only durable answer — and it makes runs replayable.
**Downsides:** Reconstruction cost per cycle; "no fresher-than-kickoff knowledge mid-run" needs an escape hatch.
**Confidence:** 80% · **Complexity:** Medium-High · **Status:** Unexplored

### 4. Task nodes are binary pre/post contracts, sized to one turn
**Description:** Decomposition emits nodes with a machine-checkable **precondition** (fail fast if an
upstream task drifted the world), a **postcondition** gate (binary done), and a complexity budget —
each sized to fit one context window. Oversized nodes are a planning bug, auto-split at plan time.
**Axis:** 2 — Plan-building
**Basis:** `external:` Hoare logic / design-by-contract, error compounding (1-p)^N; `reasoned:`.
**Rationale:** Moves long-horizon coherence upstream into planning; the precondition halts a doomed task before it adds another lossy multiply.
**Downsides:** Authoring executable pre/postconditions for every node is real work; some criteria resist binary encoding.
**Confidence:** 78% · **Complexity:** Medium · **Status:** Unexplored

### 5. Verification-first, external-signal-only loop
**Description:** For each node, generate the gate (failing test / type contract / build target) and
observe it red *for the right reason* before any code. Corrections fire only on external signals;
"the model decided to revise" is forbidden as a transition. An LLM judge — a *separate* model — is the
fallback oracle only for residue with no external check.
**Axis:** 3 — Execution + verification
**Basis:** `direct:` intrinsic self-correction degrades coding, separate evaluator model; `reasoned:` a
pre-observed red gate is the purest external signal.
**Rationale:** Kills the "agent passes a gate it quietly wrote to pass" failure and the biggest known quality leak (unmoored self-revision).
**Downsides:** Test-first on fuzzy/UI requirements is harder; some gates costly to author before code.
**Confidence:** 85% · **Complexity:** Medium · **Status:** Unexplored

### 6. Structural-erosion regulator + poka-yoke
**Description:** A complexity-delta regulator with an **integral term** that catches cumulative drift
(ten individually-legal steps that sum to erosion) — structural code that halts/escalates on budget
breach, not a prompt. Every defect class caught twice auto-installs a guard (lint rule / forbidden-pattern
check), so the verifier *prevents* recurrence instead of re-detecting.
**Axis:** 3 — Execution + verification
**Basis:** `direct:` erosion is structural, needs complexity-delta gates; `external:` PID control, Toyota
poka-yoke/andon.
**Rationale:** Prompt-level quality enforcement doesn't bend the erosion curve; this does — and the poka-yoke half is how verification compounds.
**Downsides:** Tuning the budget/PID risks false halts; choosing the right structural metrics is non-trivial.
**Confidence:** 72% · **Complexity:** Medium-High · **Status:** Unexplored

### 7. Outcome-ranked convention packs, mounted per project
**Description:** Compose mountable read-only Praxis packs from the highest outcome-scored facts (the H1
score from #1 drives selection); mount the relevant pack at project start so conventions are present from
token zero. Reversible — a bad pack just gets unmounted.
**Axis:** 4 / 5 — Long-horizon + write-back
**Basis:** `direct:` mounts + H1 score; `external:` 49% compliance lift when org conventions are provided.
**Rationale:** Cross-project compounding made concrete and auditable: project N+1 starts where N left off.
**Downsides:** Depends on #1's outcome scoring first; pack curation/staleness needs a policy.
**Confidence:** 75% · **Complexity:** Medium · **Status:** Unexplored

### 8. Self-hosting build sequence
**Description:** The factory's first *real* task is building its own next component (e.g. the write-back
gate), driven end-to-end through plan → code → verify → promote. Anything too complex for the factory to
build is too complex (simplify or push to Praxis). Honest compounding signal from commit one.
**Axis:** 2 / build strategy
**Basis:** `reasoned:` dogfooding directly stress-tests the thin-harness + single-agent bets.
**Rationale:** Continuous, brutal test of whether the loop works, instead of finding gaps only on external tasks.
**Downsides:** Chicken-and-egg — needs a minimal working loop before it can self-host; circularity risk if over-scoped.
**Confidence:** 68% · **Complexity:** Medium (sequencing) · **Status:** Unexplored

## Cross-cutting stances (shape all eight, not standalone components)
- **Build-vs-reuse:** configure Claude Code / the Agent SDK for the agent loop, tool dispatch, and run
  telemetry; build *only* the Praxis-shaped glue. Each local module should name the SDK feature it replaces.
- **Thin-harness discipline:** a hard size budget (~500 lines) forces every local feature to justify why
  it can't live behind the port or as a gate.

## Implied dependency order (a build sequence hiding in the set)
1. **Foundations:** #1 event log + #2 knowledge port.
2. **Minimal loop:** #4 task contracts + #5 verification-first loop + #3 reproducible/disposable runs.
3. **Quality + compounding:** #6 erosion regulator/poka-yoke; #7 convention packs (needs #1's outcome scores).
4. **Proof:** #8 self-hosting (needs a minimal #2–#5 loop to exist first).

## Rejection Summary

| Idea | Reason |
|---|---|
| MCP-direct / no knowledge port | Rejected — deletes the write-policy boundary #2 depends on; re-exposes every Praxis quirk to the agent |
| Plan as a mounted Praxis overlay | Folded into #3 (snapshot isolation) / #7 (packs) |
| Precedent-assembled plan skeletons | Folded into #1 (compounding from the event log) |
| Backpressure scheduler (rot as queue-depth) | Folded into #3 (disposable/reconstruct attacks rot at root) |
| WAL-as-plan resumability | Folded into #1 / #3 (event log replay + reproducible runs) |
| Immune negative-selection promotion | Folded into #2 (write-gate) + Praxis contradiction engine |
| Spec-grounded-via-KG / retrieve-then-assemble | Folded into #5 (external grounding) / #1 |
| git-vs-KG-vs-ephemeral router | Folded into #2 (port write-gate) |
