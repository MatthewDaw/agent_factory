---
date: 2026-06-25
topic: agent-factory-product-shape
---

# Agent Factory — Product Shape (MVP Requirements)

## Summary

A Praxis-backed **agent factory delivered as a Claude Code plugin** that drives a
plan→execute→verify loop with compounding memory. Coding is the first deeply-built task
type with autonomous, deterministic verification; a general **task + oracle** abstraction
keeps non-coding work (form-filling, video) a small stretch, verified human-in-the-loop. It
runs **unattended for long jobs** — proceeding autonomously while confidence is high and
parking low-confidence steps for later batch review.

## Problem Frame

Coding agents are gated by the context and memory they're given, and most "factory" effort
goes into the *doing* loop while the *knowing* loop — what's relevant, what contradicts what,
what was already learned — stays unsolved and non-compounding. We already have a knowledge
graph (Praxis) that does the knowing work. The opportunity is to build a thin harness that
leans on Praxis as durable memory so the factory compounds across projects, and to do it in a
shape that (a) plugs directly into how work already happens in Claude, (b) can run unattended,
and (c) isn't locked to coding. The first real workload is the team mental-performance app
(`docs/inspiration/`), used to find where Praxis is enough and where the harness must fill in.

## Key Decisions

- **Coding-first behind a general task+oracle seam.** The factory's unit is an abstract
  "task with a success oracle." Coding is built deeply now; other task types ride the same
  seam later. We build the seam, not the task types.
- **Human-in-the-loop is the default oracle for non-coding.** Coding uses deterministic
  oracles (tests/build/type-check). Soft task types fall back to human confirmation, so adding
  a task type doesn't require building a verifier first.
- **Confidence-gating is escalation triage, not success grading.** For unattended soft tasks,
  a confidence signal (separate-model judge) only decides *park-for-review vs. proceed*. The
  human remains the oracle; the judge never declares success.
- **Delivered as a Claude Code plugin.** Reuse Claude Code's agent loop, tool dispatch,
  sandbox, telemetry, and remote/web execution. Build mostly the Praxis glue and the
  plan→execute→verify workflow as skills/commands.
- **Single agent; thin harness; Praxis owns the *knowing* system.** No agent-level domain
  split (Praxis partitions by tenancy/scope, not by agent). Retrieval, dedup, contradiction
  handling, and provenance are Praxis's job, consumed through one knowledge port; we do not
  rebuild them. (Carried from prior ideation, `docs/ideation/2026-06-25-...`.)

## Actors

- A1. **Operator (you)** — kicks off runs, reviews parked checkpoints, is the verification
  oracle for non-coding tasks.
- A2. **The factory (single agent)** — runs the plan→execute→verify loop inside Claude Code.
- A3. **Praxis** — durable memory: project pool + shared general pool, retrieval, contradiction
  handling, provenance.
- A4. **Review queue** — where low-confidence checkpoints from unattended runs park for batch
  approval.

## Requirements

**Product shape & task abstraction**
- R1. The factory must model work as a **task with an associated success oracle**; coding and
  non-coding tasks are instances of the same abstraction.
- R2. Coding tasks must run **fully autonomously**, verified by deterministic oracles
  (tests, build, type-check, lint).
- R3. Adding a new task type must not require a programmatic oracle; absent one, the task type
  defaults to **human-in-the-loop verification**.
- R4. The task+oracle seam must be the documented extension point, such that a new task type is
  defined by its prompt/tools/oracle without changing the core loop.

**Claude Code integration**
- R5. The factory must be installed and driven as a **Claude Code plugin** (skills/commands),
  not a standalone application.
- R6. The factory must reuse Claude Code's execution harness (agent loop, tool dispatch,
  sandbox, telemetry) rather than reimplementing it.

**Execution & verification loop**
- R7. Each run must follow a **plan → execute → verify** loop with externally-grounded
  verification (coding: deterministic signals; non-coding: human or escalation triage).
- R8. Corrections must be triggered by **external signals**, not by the agent deciding on its
  own to revise.

**Unattended / remote running**
- R9. The factory must support **unattended long-running jobs** that proceed while the operator
  is away and surface results on return.
- R10. During an unattended run, a non-coding step whose confidence is **below threshold** must
  **park a checkpoint** in the review queue and continue with work that doesn't depend on it;
  above threshold it proceeds autonomously.
- R11. The operator must be able to **batch-review parked checkpoints** (approve/reject), after
  which the run resumes from the affected point.

**Memory & compounding (Praxis)**
- R12. All durable knowledge — requirements, decisions, learnings — must live in Praxis;
  code lives in git; ephemeral run state is local.
- R13. Praxis access must flow through a **single knowledge port** that encodes routing,
  retrieval, ingestion-integrity auditing, and write-back policy.
- R14. Confirmed learnings must be **written back** so the general pool compounds across
  projects, gated through Praxis's contradiction handling.

## Key Flows

- F1. **Unattended coding run.** **Trigger:** operator starts a build and leaves. The agent
  plans → implements → verifies against deterministic oracles, self-corrects on failing
  signals, writes learnings back, and ships (or stops at a hard gate). No human needed mid-run.
- F2. **Unattended non-coding run with parking.** **Trigger:** operator starts a soft task and
  leaves. The agent proceeds; at each verification step the confidence signal decides
  proceed-vs-park. Low-confidence steps park in the review queue; independent work continues.
  **On return:** operator batch-reviews, the run resumes from approved points.
- F3. **Add a task type.** **Trigger:** operator wants a new capability. They define the task
  type's prompt/tools/oracle on the seam; with no programmatic oracle it defaults to HITL. No
  change to the core loop.

## Acceptance Examples

- AE1. **Covers R2, R8.** A coding task whose tests fail re-enters the loop with the failure as
  context and retries; it never marks itself done without a passing external signal.
- AE2. **Covers R10.** During an unattended non-coding run, a step the judge rates low-confidence
  is parked (not auto-approved) and the run continues other work rather than stalling.
- AE3. **Covers R10, R11.** A high-confidence non-coding step proceeds unattended; a parked
  low-confidence step waits and resumes only after the operator approves it.

## Scope Boundaries

**Deferred for later (eventually, not v1)**
- Parallel / scaled concurrency across many simultaneous runs — "remote" here means unattended
  long jobs, not throughput.
- Pre-built non-coding task types (video, forms) — only the seam ships; coding is the built type.
- Full *autonomous* verification for non-coding tasks — stays human-in-the-loop until a real
  oracle exists for a given type.

**Outside this product's identity**
- A standalone app or general agent framework — it is a Claude Code plugin.
- Reimplementing retrieval, dedup, contradiction handling, or provenance — those are Praxis's.
- A multi-user / team / multi-tenant product — solo dogfooding first; tenancy stays simple.

## Dependencies / Assumptions

- **Unattended runs imply a reachable Praxis backend with the machine off** — i.e. the prod
  (App Runner) or another hosted Praxis, since `localhost:8000` won't be reachable. (Assumption
  to confirm — see Outstanding Questions.)
- **Praxis tabular-ingestion integrity (gap H6)** is being addressed separately
  (`../../praxis/docs/proposals/2026-06-24-tabular-ingestion-integrity.md`); the factory's
  ingestion-integrity shim depends on it.
- Built on Claude Code's plugin runtime; remote execution relies on Claude Code's
  cloud/web/scheduled capabilities.
- Single-agent design; no multi-agent orchestration assumed.

## Outstanding Questions

**Resolve before planning**
- **Build-vs-reuse:** fork/extend the existing `compound-engineering` skills (lfg, ce-plan,
  ce-work) or build clean Praxis-native skills? Leaning "study lfg's shape, build Praxis-native."
- **Praxis backend for unattended runs:** confirm prod/hosted Praxis is acceptable (and
  auth/key minting for it), or constrain unattended runs to when local Praxis is reachable.

**Deferred to planning**
- The concrete shape of the **review queue** (where parked checkpoints live and how the operator
  approves them).
- The **confidence signal / threshold** mechanism for park-vs-proceed.
- Whether the **event log** is built fresh or derived from Claude Code session transcripts.
- Sandbox/execution environment for remote coding runs.

## Sources / Research

- `docs/agent-factory-vision.md` — vision and why.
- `docs/agent-coding-factory-reference.md` — neutral reference model of factory capabilities.
- `docs/praxis-and-how-we-use-it.md` — Praxis substrate.
- `docs/praxis-gaps.md` — knowledge-side holes (H1–H8).
- `docs/factory-local-components.md` — local build partition.
- `docs/ideation/2026-06-25-local-factory-components-ideation.md` — eight build ideas + dependency order.
- `docs/inspiration/` — first workload (team mental-performance app).
