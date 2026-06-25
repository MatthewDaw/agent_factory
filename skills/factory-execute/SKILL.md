---
name: factory-execute
description: >
  The single-agent execution loop for the agent factory. Use to build a task from a hardened
  prd-<project> plan: assemble hermetic context, do the work, gate it through factory-verify, and
  write confirmed learnings back. One agent, no crew — it orchestrates phases and tools, not
  sub-agents. Consumes the plan factory-plan produced; verifies via factory-verify; all memory
  through factory-memory.
---

# Factory Execute

One agent builds the project, one task at a time, against a plan that's already hardened
(`factory-plan` → `prd-<project>`). This skill is the *doing* loop; it leans on the others:
**`factory-memory`** for all Praxis access, **`factory-verify`** for the pass/fail gate. Code lives
in **git**, not Praxis; only judgments and learnings go to the graph. Every step is an event-log
entry; cite the fact(s) that grounded each decision.

## 0. Run setup (once)

- **Pin knowledge at kickoff.** Record the run's `as_of` timestamp so every retrieval this run sees
  one stable plan, even as write-backs land — runs are reproducible and replayable.
- **Mount read-only** `general-pool` (conventions) + the project's `prd-<project>` snapshot via
  `factory-memory`. The live graph is this run's scratch; the plan + conventions are mounted, not
  copied in.
- **Walk the task DAG** the plan produced, in dependency order. Do tasks **serially** (single agent;
  also respects the serial-write rule).

## 1. Per-task loop

**a. Assemble hermetic context (declare it; don't free-query mid-task).** Up front, pull exactly:
the task's requirement + its **binary acceptance condition**, the conventions/invariants it touches,
and any task-specific facts — via declared `factory-memory` queries (scope + top_k + `as_of`).
Budget it (hot constitution always in; warm/cold to a ceiling well below the context-rot threshold).
The agent works from this sealed bundle; if it discovers it needs more, that's a new declared pull,
logged — not unbounded mid-task querying.

**b. Re-anchor the goal.** Restate the task's acceptance condition at the start of each cycle (and
after any context compaction). Goal drift comes from semantic accumulation, not token count —
re-injecting the objective is the cheap, proven defense.

**c. Act.** The single agent does the work with real tools in the sandbox/repo (edit, run, search).
Make the change that satisfies the acceptance condition — nothing broader (resist scope creep into
adjacent requirements).

**d. Gate via `factory-verify`.** Hand the output to the verify skill. On **fail**, re-enter (c)
with the **captured failing signal** as context — corrections are signal-driven, never
self-directed. Respect verify's bounded loop: N identical failures → replan the task; M replans →
escalate to the human. On **pass**, continue.

**e. Write back (only what an external signal confirmed).** On a verified pass, write confirmed
learnings/fixes via `factory-memory` (`on_conflict="surface"`, serial or `add_insights` for a batch,
read-back-on-timeout). Stamp `source`, `category="learning"`, and **`derived_from=[the fact ids that
grounded it]`** (so a flipped basis later surfaces this learning via `praxis_get_stale_derivations`).
Then call **`praxis_record_outcome(requirement_fact_id, "succeeded")`** to feed the H1 trust loop
(and `"failed"` on the facts behind a failed attempt). Never write speculative facts; **never block
the loop on a write** — queue it and proceed.

## 2. Long-horizon control (so the run survives length)

- **Disposable agent:** keep durable state in Praxis + the event log, not the context window. If the
  context is compacted or the agent is re-spawned, reconstruct the working set from the pinned
  `as_of` view + the log — losing the window should lose nothing.
- **Compact, don't drop:** at ~70–80% context fill, summarize old turns (preserve the goal, key
  decisions, current task, constraints discovered); drop raw tool output, keep its conclusions.
- **Checkpoint at task boundaries:** snapshot the project graph (via `factory-memory`) after each
  task clears, so a bad later task can roll back.
- **Saturation detector / circuit breaker:** watch round-trip count and repetition; trip before the
  rot threshold (re-anchor + compact) and on degeneration (escalate, per `factory-verify`).

## 3. Decisions are episodes (the why, not just the what)

When the loop makes a non-obvious choice (picked library X; defaulted Y because the plan was silent),
record it with **`praxis_record_episode`** (per `factory-memory` §1b) — `text` = decision + rationale,
`alternatives` = options not taken, `derived_from` = the facts it rested on. Episodes are store-only
and excluded from semantic recall by default, so the "why" compounds and stays traceable without
polluting task-grounding retrieval. Flip `outcome` later via `praxis_record_outcome` when the
decision proves out or fails.

## Never
- Never run a crew — this is one agent orchestrating phases and tools.
- Never write code or run state into Praxis; code is git, ephemeral state is the event log.
- Never free-query Praxis ad hoc mid-task — declare the hermetic bundle; new needs are new declared pulls.
- Never mark a task done without `factory-verify` returning pass (external signal).
- Never write a learning back that wasn't externally confirmed; never block the loop on a write.
- Never widen a task beyond its acceptance condition into adjacent requirements.
