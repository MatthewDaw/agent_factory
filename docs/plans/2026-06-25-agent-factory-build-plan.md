---
date: 2026-06-25
topic: agent-factory-build-plan
origin: docs/brainstorms/2026-06-25-agent-factory-product-shape-requirements.md
status: active
---

# Agent Factory — Build Plan

How we build the product shaped in
[`../brainstorms/2026-06-25-agent-factory-product-shape-requirements.md`](../brainstorms/2026-06-25-agent-factory-product-shape-requirements.md),
combining that requirements set with the research in
[`../agent-coding-factory-reference.md`](../agent-coding-factory-reference.md) and the build
ideas in [`../ideation/2026-06-25-local-factory-components-ideation.md`](../ideation/2026-06-25-local-factory-components-ideation.md).

## What we're building (one line)

Our own **Claude Code plugin** — skills/commands that drive a single-agent plan→execute→verify
loop, using the **Praxis MCP** as durable compounding memory, coding-first behind a general
task+oracle seam, runnable as long unattended sessions with confidence-gated parking.

## Locked decisions (this plan assumes them)

- **Our own plugin, Praxis-native.** Not built on compound-engineering; the agent uses the
  **Praxis MCP** tools directly. We study other factories for shape only.
- **The "knowledge port" is policy-as-skill, not a module.** Praxis access happens through the
  MCP; our skills encode routing (`insight` vs `ingest`), ingestion-integrity audit, retrieval
  conventions, and write-back policy. One documented policy surface, enforced by skill design.
- **Local Praxis only for now.** Unattended = a long-running local session, not machine-off.
  Hosted/remote Praxis is deferred.
- **Single agent, thin harness, Praxis owns the knowing system.** Verification is
  external-signal-grounded; coding uses deterministic oracles, non-coding defaults to HITL with
  confidence-gated escalation.
- **Dedicated `agent-factory` org; partition by snapshots/mounts, not principals.** Verified
  against the live MCP: a Cognito login is a **single principal**, so the earlier
  "per-project principal (distinct user_id)" partition is **not achievable** via MCP. The factory
  runs in its own clean org (`agent-factory`).
- **Durable knowledge = named snapshots; the live graph = scratch.** Because `save_snapshot`
  captures the *entire* live graph, the only way to mint a clean PRD-only snapshot is to author
  it in an otherwise-empty live graph. So every durable pool — `general-pool` (a.k.a. planning
  knowledge), each `prd-<project>`, learnings packs — is a **named snapshot**, and the live graph
  is just the current session's working set. You **`mount`** the snapshots you need (read-only,
  composed at read time, never merged into live or carried into a save) and **save** back to the
  appropriate snapshot. `mount` is "read without loading"; `load` (merge into live) is reserved
  for editing a snapshot in place.
- **Planning is human-controlled.** The factory does **not** autonomously author or approve
  plans. Its planning job is to pressure-test for completeness, research, and enforce
  self-consistency via the KG. Autonomy lives in *execution*, not planning.

## Build sequence rationale

The ideation set has a dependency order: foundations (memory access + event log) → minimal
coding loop → reproducibility/long-horizon control → compounding → self-hosting proof. We build
the **thinnest coding loop that compounds** first, prove it on a slice of the real workload, then
generalize the seam and add unattended parking. Each milestone is shippable and dogfoodable.

---

## Milestone 0 — Foundations: memory access + event log

**Goal:** the agent can read/write Praxis correctly and every run leaves a structured trace.

- Praxis MCP wired into the plugin; confirm identity/tenancy with `praxis_whoami`. ✅ done —
  connected, logged in as `mattdaw7@gmail.com`, dedicated `agent-factory` org created (empty).
- **Tenancy setup:** durable pools are **named snapshots** (`general-pool` / planning knowledge,
  per-project `prd-<project>`, learnings), the **live graph is scratch**, and reference knowledge
  is composed with **`mount`** (read-only). Document the save-back and mount conventions.
- **Save-before-clear guardrail.** `clear_graph` truncates the live graph; the access-policy
  skill must save the live graph to a snapshot before any clear. (Immediate bootstrap: the 6 M0
  seed facts are currently live and **unsnapshotted** — save them to `general-pool` first.)
- **Access-policy skill** (the "port"): `insight` vs `ingest` routing, the **ingestion-integrity
  audit** (linearize tabular input + check the rejected pile), retrieval conventions, mount/save
  rules, and **auto-resolution OFF** during planning so contradictions surface instead of being
  silently rejected. ✅ skill drafted (`skills/factory-memory/`).
- **Event log** as the compounding spine: an append-only structured record of decisions, tool
  calls, gate results, outcomes — the local source for outcome/episodic/derivation data Praxis
  doesn't store (gaps H1/H4/H5). ✅ built (`src/agent_factory/event_log.py`); own structured log
  (not transcript-derived).

**Covers:** R12, R13. **Exit:** general pool saved as a snapshot; a project snapshot can be
minted, mounted, and retrieved against; the rejected-pile audit runs on tabular input; every run
leaves a complete event-log trace. **Status:** done except the live snapshot/mount round-trip
(blocked on a local Praxis backend restart).

## Milestone 1 — Plan-hardening + minimal coding loop

**Goal:** a human-controlled planning loop that produces a self-consistent, fully-spec'd
`prd-<project>` snapshot, then a fully-autonomous plan → execute → verify loop on a single coding
task that consumes it.

### M1a — Plan skill (human-controlled hardening loop, NOT an autonomous planner)

The human drives the plan; the factory **pressure-tests, researches, and enforces
self-consistency via the KG**. It never authors or approves the plan itself — it reports what's
inconsistent or under-specified and the human clears the gate.

Planning-session lifecycle:
1. **Save-before-clear**, then `clear_graph` → clean live scratch.
2. **`mount` the planning-knowledge snapshot** (`general-pool`) read-only — fixed reference that
   stays out of the PRD.
3. **Author/iterate the PRD in the live graph** — human-driven. The factory researches (codebase,
   web, Praxis recall) and pressure-tests for completeness. Tabular requirements go through the
   H6 linearizer + rejected-pile audit.
4. **Self-consistency via the KG** — run contradiction detection with **auto-resolution OFF** so
   conflicts surface (`praxis_get_contradictions`) instead of silently rejecting; report
   contradictions + under-specified requirements; human resolves.
5. **`save_snapshot("prd-<project>")`** ("push") — PRD-only, since the mount isn't carried.

**Definition of done for a plan (the gate the human clears):** every requirement maps to ≥1
binary acceptance condition, and zero unresolved contradictions in the PRD snapshot. Editing a
plan later = `load_snapshot("prd-<project>", mode=replace)` → edit → re-save.

### M1b — Execute + verify (autonomous, coding)

- **Execute:** `mount` `general-pool` + `prd-<project>` read-only over a fresh working graph; the
  single agent (Claude Code) does the task, pulling grounding context from Praxis via MCP and
  citing the facts that grounded each decision.
- **Verify skill:** external-signal gates — tests / build / type-check / lint — as blocking.
  Corrections fire **only** on a failing external signal (no self-directed revision).

**Covers:** R1 (plan→execute→verify shape), R2, R7, R8. **Exit:** a human hardens a small PRD to
the done-gate; the agent then builds and verifies one task from it end-to-end, self-correcting on
a failing test, no human mid-execution.

**Covers:** R2, R7, R8. **Exit:** the loop builds and verifies one real coding task end-to-end,
self-correcting on a failing test, with no human mid-run.

## Milestone 2 — Reproducible, long-horizon runs

**Goal:** runs survive long horizons without erosion and are replayable.

- Pin run knowledge to a consistent read at kickoff (Praxis `as_of`); reconstruct working state
  from Praxis + event log rather than accumulating context (disposable-agent pattern).
- Goal re-anchoring on a round-trip counter; context compaction (summarize, don't drop).
- **Structural-erosion guard:** per-iteration complexity-delta check that halts/escalates;
  begin the poka-yoke pattern (a twice-caught defect class installs a guard).
- Checkpoint/replay so a run can resume.

**Covers:** R9 (the "long-running" half). **Exit:** a multi-step run can be interrupted and
resumed losslessly; an induced complexity blow-up trips the guard instead of pushing through.

## Milestone 3 — Task+oracle seam + HITL

**Goal:** non-coding is a small stretch on the same loop.

- Generalize the task definition to **task + oracle**; coding's deterministic oracle is one
  implementation. Document the seam (prompt/tools/oracle).
- **HITL oracle** as the default for any task type without a programmatic one.
- Prove with one simple non-coding task (e.g. a form-fill or doc-generation slice) verified by
  human confirmation.

**Covers:** R1, R3, R4. **Exit:** a non-coding task runs through the same loop and is accepted
via human confirmation; adding it required no core-loop change.

## Milestone 4 — Unattended runs with confidence-gated parking

**Goal:** leave a run going; it parks only what it's unsure of.

- Run the loop as a **long unattended session**.
- **Confidence triage** (separate-model judge) decides park-vs-proceed for non-coding
  verification steps — escalation only, never success-grading.
- **Review queue:** low-confidence steps park; independent work continues; operator
  **batch-reviews** (approve/reject) and the run resumes from affected points.

**Covers:** R9, R10, R11. **Exit:** an overnight-style run proceeds autonomously, parks a
low-confidence step, continues other work, and resumes after batch approval.

## Milestone 5 — Compounding + self-hosting proof

**Goal:** the factory gets better across runs, and proves it on itself.

- **Write-back:** confirmed learnings → Praxis, gated through contradiction handling; attach
  outcome metadata from the event log (local manufacture of gap H1/H4/H5 data).
- **Convention packs:** compose mountable read-only Praxis snapshots from high-outcome facts;
  mount the relevant pack at project start so conventions are present from token zero.
- **Self-hosting proof:** drive the factory to build its own next component end-to-end.
- **Workload proof:** build a real slice of the team mental-performance app
  (`../inspiration/`) to surface where Praxis is enough and where the harness must fill in.

**Covers:** R14 (and validates R1–R13 under real load). **Exit:** a second run measurably reuses
a prior run's learning; the factory ships one of its own components; one app slice is built.

---

## Cross-cutting (every milestone)

- **Thin-harness discipline:** prefer pushing logic into Praxis or a verification gate over
  growing the plugin. Each skill justifies why it isn't a Praxis call.
- **Provenance:** every decision the agent makes cites the Praxis fact(s) that grounded it.
- **Dogfood continuously:** each milestone is used on a real task, not just demoed.

## Risks & open items carried into the build

- **Ingestion integrity (Praxis H6)** must land for trustworthy plan-building; tracked at
  `../../praxis/docs/proposals/2026-06-24-tabular-ingestion-integrity.md`. M0's audit shim is the
  interim guard.
- **Event-log mechanism** (own vs. session-transcript-derived) — decide in M0; it's the
  compounding spine, so the schema is a near one-way door.
- **Confidence-triage reliability** — the judge gates escalation, not success; keep the human as
  the oracle so a weak signal can't silently pass bad non-coding work.
- **Local-only "unattended"** means a machine left running; revisit hosted Praxis if true
  machine-off operation becomes a requirement.
- **Praxis async-ingest latency** — keep `ingest` off the loop's critical path; prefer `insight`
  for shaped facts.

## Requirement → milestone map

| Milestone | Requirements |
|---|---|
| M0 Foundations | R12, R13 |
| M1 Coding loop | R2, R7, R8 |
| M2 Long-horizon | R9 (long-running) |
| M3 Task+oracle seam | R1, R3, R4 |
| M4 Unattended + parking | R9, R10, R11 |
| M5 Compounding + proof | R14 |
| Cross-cutting | R5, R6 (plugin shape + harness reuse, assumed throughout) |
