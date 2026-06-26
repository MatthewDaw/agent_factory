---
name: factory-execute
description: >
  The single-agent execution loop for the agent factory. Use to build a task from a hardened
  prd-<project> plan: assemble hermetic context, do the work, gate it through factory-verify, and
  write confirmed learnings back. One decision-making agent — it orchestrates phases and tools,
  and may dispatch a disposable read-only retrieval sub-agent for bulk reading (never a crew that
  decides or writes). Consumes the plan factory-plan produced; verifies via factory-verify; all
  memory through factory-memory.
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
- **Walk the work by completeness, not a static list:** the next task is the next *incomplete*
  requirement from `praxis_incomplete_requirements(prd-<project>)` (§0b), in dependency order. Do
  tasks **serially** (single agent; also respects the serial-write rule).

## 0b. Drive to completeness (the worker is FORCED to iterate until every requirement is done)

The build is **not done when the agent thinks so** — it's done when
**`praxis_incomplete_requirements(prd-<project>)` returns empty** (PR #106). That query derives
completeness from *verified outcomes + staleness* (never-built / regressed / stale), so a
requirement only counts complete once it has actually passed `factory-verify`.

Run the build as a forced loop:
1. At build start, write `<project>/.factory/build-status.json` with `status:"building"`, the
   `project`, and the current `praxis_incomplete_requirements` result (`incompleteCount`,
   `incomplete:[{id,reason}]`). This **arms the build-completeness gate**
   (`hooks/build_completeness_gate.py`).
2. Each pass: pick the next incomplete requirement (dependency order, then `never-built` →
   `regressed` → `stale`), build it (§1), gate via `factory-verify`, and on a verified pass call
   `praxis_record_outcome(req, "succeeded")` (and `"failed"` on a failed attempt).
3. **Re-query** `praxis_incomplete_requirements` and rewrite the manifest (bump `checkedAt`, refresh
   `incompleteCount`/`incomplete`).
4. Repeat. The Stop hook **blocks the turn from ending while `incompleteCount > 0`** — you cannot
   stop or declare the build done until the query is empty. At 0 the gate flips the manifest to
   `done` and lets you finish.

To intentionally yield (hand back to the human, or a hard blocker you can't pass), set
`status:"paused"` in the manifest and say why — never fake `incompleteCount`. Completeness is
outcome-grounded, so the only honest way to reach 0 is to actually build and verify everything.

## 1. Per-task loop

**a. Assemble hermetic context (declare it; don't free-query mid-task).** Up front, pull exactly:
the task's requirement + its **binary acceptance condition**, the conventions/invariants it touches,
and any task-specific facts — via declared `factory-memory` queries (scope + top_k + `as_of`).
Budget it (hot constitution always in; warm/cold to a ceiling well below the context-rot threshold).
The agent works from this sealed bundle; if it discovers it needs more, that's a new declared pull,
logged — not unbounded mid-task querying. For a **screen-scoped build task**, pull the governing
behavior with **`praxis_requirements_for_surface(project, screen_id)`** — the active requirement
facts bound to that wireframe screen via the `renders` relation (factory-intake §3) — and take the
layout from the wireframe HTML in git.

**Read-only retrieval sub-agent (the one permitted delegation).** When populating the bundle (or
researching in `factory-plan`) needs reading many files or large surfaces, dispatch a *disposable,
single-shot* sub-agent to do that reading and return a compact digest — so the parent's window
never absorbs the raw noise. Hard constraints, or it degrades into a crew:
- **Read-only tools only** (Read/Grep/Glob/LS). It never edits, runs state-changing commands,
  writes to Praxis, or commits.
- **One shot, no dialogue.** It returns once; you don't converse with it or chain it into a decision.
- **Cheap model, fixed compact schema.** Output is a curator's digest, not a dump: *file → role*,
  the specific facts/patterns asked for, constraints/gotchas found, and what's *still unknown*.
  Instruct it to **filter ruthlessly — it is a curator of insights, not a summarizer.**
- You remain the **only** agent that decides, edits, writes to Praxis, or commits. This is context
  hygiene, not orchestration; a crew that divides decision/domain work or writes in parallel is
  still forbidden (see `docs/factory-local-components.md`).
- **Read-fully guard:** any file the human or the plan names *explicitly* is read **fully in your
  own context first** (no limit/offset) — only *exploratory / bulk* reading is delegated. Never
  delegate away the one artifact you must hold yourself.

**b. Re-anchor the goal.** Restate the task's acceptance condition at the start of each cycle (and
after any context compaction). Goal drift comes from semantic accumulation, not token count —
re-injecting the objective is the cheap, proven defense.

**c. Act.** The single agent does the work with real tools in the sandbox/repo (edit, run, search).
Make the change that satisfies the acceptance condition — nothing broader (resist scope creep into
adjacent requirements).

**d. Gate via `factory-verify`.** Hand the output to the verify skill. On **fail**, re-enter (c)
with the **captured failing signal** as context — corrections are signal-driven, never
self-directed. Respect verify's bounded loop: N identical failures → replan the task; M replans →
escalate to the human. On **pass**, continue. Verify the task's **automated** acceptance criteria
yourself; for any criterion tagged **manual** (factory-plan §2b), in an attended run pause and hand
it off for human confirmation (do not self-check it), and in an unattended run record it as a
deferred owned decision (per the Constitution) and proceed.

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
- **Compact early, don't drop:** at **~50–60%** context fill (not 70–80% — the lower band keeps
  you clear of the rot cliff with headroom to recover), summarize old turns into a fixed
  **compaction artifact**: (1) end goal; (2) current approach; (3) steps completed; (4) **dead-ends
  tried and why they failed** (so a later reset doesn't re-tread them); (5) key file locations +
  their roles; (6) next step + its binary acceptance condition. Drop raw tool output, keep its
  conclusions. (Same shape a retrieval sub-agent returns — §1a.)
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
- Never run a crew — one decision-making agent. The only permitted delegation is the disposable
  read-only retrieval sub-agent (§1a): it reads and digests, never decides/edits/writes/commits,
  and you never chain it into the decision.
- Never write code or run state into Praxis; code is git, ephemeral state is the event log.
- Never free-query Praxis ad hoc mid-task — declare the hermetic bundle; new needs are new declared pulls.
- Never mark a task done without `factory-verify` returning pass (external signal).
- Never write a learning back that wasn't externally confirmed; never block the loop on a write.
- Never widen a task beyond its acceptance condition into adjacent requirements.
