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

**FIRST — Preflight: prove the environment is provisioned before any coding (GATED).** A build fails,
or ships something that can't run, if its external dependencies aren't actually there. Before writing
a line of app code, **DERIVE** the dependencies this build needs from the plan's `techDecisions`
(auth provider, data store, deploy target, external services, secrets/config) — NOT a fixed list —
and for each, define and run a concrete **check** that it is present and usable: a required env var /
secret / API key is set, a cloud CLI is authenticated and the credential valid, a service (DB,
queue, cache) is reachable, a CLI tool / runtime is installed at the needed version. Write the result
to `<project>/.factory/preflight.json` (`deps:[{name,kind,check,status,remediation}]` with
`status` ∈ present|missing|unknown|na; top-level `status` pending→ready). The **preflight gate**
(`hooks/preflight_gate.py`) **BLOCKS coding until every dependency is `present` (or `na`)** — only
after it reports READY do you build. For anything missing, surface EXACTLY what the user must provide
(which key, which credential, which service) and re-check; **never stub or fake a credential** to get
past the gate. (Unattended: if a dep only the owner can provide is missing, set `status:"parked"`
with a `parkedReason` + `praxis_record_episode`, and find other forward progress.)

- **Pin knowledge at kickoff.** Record the run's `as_of` timestamp so every retrieval this run sees
  one stable plan, even as write-backs land — runs are reproducible and replayable.
- **Mount read-only** `general-pool` (conventions) + the project's `prd-<project>` snapshot via
  `factory-memory`. The live graph is this run's scratch; the plan + conventions are mounted, not
  copied in.
- **Walk the work by completeness, not a static list:** the next task is the next *incomplete*
  requirement from `praxis_incomplete_requirements(prd-<project>)` (§0b), in dependency order. Do
  tasks **serially** (single agent; also respects the serial-write rule).

## 0b. Drive to completeness (the worker is FORCED to iterate until the build set is done)

The build is **not done when the agent thinks so** — it's done when every requirement in the
**build set** has passed `factory-verify`. Completeness is derived from *verified outcomes +
staleness* (never-built / regressed / stale) via `praxis_incomplete_requirements(prd-<project>)`
(PR #106), so a requirement only counts complete once it has actually passed verify.

But `praxis_incomplete_requirements` returns **all** active requirements, which is the wrong target
for an *automated* forced gate: post-mvp scope would make the gate chase forever, and manual-verify
requirements can never earn an automated "succeeded" outcome (the gate would be structurally
trapped). So the worker first **computes its completion target** with
**`select_build_target`** (`src/agent_factory/build_target.py`), partitioning the requirements —
using each one's plan tags, the tier (`meta.scope` ∈ {`mvp`, `post-mvp`}) and verify mode
(`meta.verify` ∈ {`automated`, `manual`}) — into four disjoint groups:

- **build** (`tier==mvp` AND `verify==automated`) — the gate's completion set. The **only**
  requirements the forced loop is responsible for finishing.
- **deferred_manual** (`tier==mvp`, `verify==manual`) — in-scope for the MVP but parked: recorded
  separately and surfaced to the human (no automated success signal is possible). **Never blocks the
  gate.**
- **excluded_post_mvp** (`tier==post-mvp`, any verify) — recorded as out-of-scope for this build.
- **needs_triage** (missing/unrecognized tier or verify) — **surface loudly**: a mis-tagged
  requirement must NOT be silently auto-built. Routing it here forces a human to fix the tag.

**Validation checks — live, from Praxis (the fail→regress trigger).** The checks live in the
**validation graph** (`category="check"`, `scope="validation"`), each carrying `meta.applies_to` (a
requirement id OR a class tag like `auth`) and `meta.run` (the command). **Before computing the build
target each run, pull them from Praxis:** query the active validation checks (via `factory-memory`),
build them with `validation_target.checks_from_facts`, `resolve_bindings` against the plan's
requirements (class tags from `meta.tags`), and `select_validation_incomplete`
(`src/agent_factory/validation_target.py`). For every ticket bound to a check it has **not passed
this build** that currently shows complete, call **`praxis_record_outcome(req, "failed")`** so it
**regresses** and re-enters `incomplete_requirements`. That is the trigger: inserting a check in
Praxis forces the matching ticket(s) back into the build set with the new rule attached, and
`factory-verify` then runs the check's `meta.run` command as a blocking gate (the ticket can't
re-complete until it passes). Surface any `unbound_checks` (an `applies_to` that matched nothing — a
typo) loudly. Do this **first**, so the regressed tickets are counted by the completeness query below.
Nothing about *what* is tested lives in this skill or any file — only *how* to pull it from Praxis.

Run the build as a forced loop:
1. At build start, query `praxis_incomplete_requirements(prd-<project>)`, run the result (joined with
   the plan's tier/verify tags) through `select_build_target`, and write
   `<project>/.factory/build-status.json` with `status:"building"`, the `project`, and the
   **build-set-only** completion target: `incompleteCount` / `incomplete:[{id,reason}]` counting
   **ONLY the build group** (mvp+automated still incomplete). Record the other groups separately for
   transparency: `deferredManual:[{id}]`, `excludedPostMvp:[{id}]`, `needsTriage:[{id}]` — these are
   surfaced, never folded into `incompleteCount`. This **arms the build-completeness gate**
   (`hooks/build_completeness_gate.py`).
2. Each pass: compute the **buildable frontier** — every incomplete build-set requirement whose
   dependencies are already complete — and **FAN IT OUT as parallel builder agents via a Workflow**
   (the default, not a serial todo queue — CONSTITUTION §0). One agent owns each independent slice;
   give concurrent file-mutating builders **worktree isolation** so they don't collide. Each builder
   builds its slice (§1), gates it via `factory-verify`, and on a verified pass calls
   `praxis_record_outcome(req, "succeeded")` (`"failed"` on a failed attempt). Build **serially only**
   along a genuine dependency chain, or for a trivial 1–2-slice build. (A long single-threaded task
   queue burning down slice-by-slice is the anti-pattern — fan out the frontier.)
3. **Re-query** `praxis_incomplete_requirements`, re-partition via `select_build_target`, and rewrite
   the manifest (bump `checkedAt`, refresh `incompleteCount`/`incomplete` over the **build set**, and
   the `deferredManual`/`excludedPostMvp`/`needsTriage` lists).
4. Repeat. The Stop hook **blocks the turn from ending while `incompleteCount > 0`** — you cannot
   stop or declare the build done until the build set is empty. Before finishing, **surface** any
   `deferredManual` (hand to the human) and `needsTriage` (mis-tagged — must be resolved) items; they
   were never built by the loop.
5. **Deploy — a hard gate (the plan is NOT done until it's deployed).** Once the build set is empty,
   **deploy to the `techDecisions` deploy target and verify the deployment is reachable/healthy**
   (a real check — the deployed URL responds / a health endpoint is green), then set
   `deployment:{target, verifyCheck, status:"verified"}` in `.factory/build-status.json`. The
   build-completeness gate will NOT flip to `done` until `deployment.status=="verified"` — **unless
   the USER explicitly opted out**, recorded as `deployment.required:false` + a non-empty
   `deployment.optOutReason`. Never skip deployment on your own judgment. Only at `done` does the gate
   arm the work-review (§0c).

To intentionally yield (hand back to the human, or a hard blocker you can't pass), set
`status:"paused"` in the manifest and say why — never fake `incompleteCount`. Completeness is
outcome-grounded, so the only honest way to reach 0 is to actually build and verify the whole build
set.

**Fan out via Workflow — the DEFAULT for a substantial build (CONSTITUTION §0), not an option.** Do
NOT walk the build set as a serial task queue. For any build past a couple of slices the build set is
a fan-out target: author and run a Workflow with **parallel per-screen / per-slice builders** (one agent owns
each independent slice — give concurrent file-mutating builders **worktree isolation** so they don't
collide), an **adversarial reviewer per slice** that tries to falsify the slice rather than bless it,
and **loop-until-dry** gap-finding — keep fanning out until a pass surfaces no new incomplete
requirement. This does **not** loosen the gates or the single-decision-maker discipline: the
**completeness gate** (§0b) and the **work-review gate** (§0c) still hold exactly as written, and the
**one-decision-maker-per-slice** rule is preserved — each builder owns its slice end-to-end (decides,
edits, writes its slice's learnings, commits its slice), and the read-only retrieval sub-agent rule
(§1a) is unchanged. Workflows *orchestrate* builders that each own a slice; they never reintroduce a
crew that splits the decision for a single slice across agents. Re-query
`praxis_incomplete_requirements` and re-partition after each fan-out batch lands, same as the serial
loop.

**Yielding to a running workflow (so the gates don't kick you back to work).** When you launch a
background Workflow and intend to *wait* for it, record it so the Stop gates **defer** instead of
forcing you to keep working: write `<project>/.factory/awaiting-subagents.json` =
`{"workflows": [{"taskId": "<id>", "outputPath": "<the output-file path the Workflow tool
returned>"}]}`. While that workflow runs, every gate stands down — and it's liveness-verified, not a
free pass: the gate confirms the workflow is genuinely still running (its output file stays empty
until it completes). When the workflow finishes, **delete the marker**, fold in its results,
`praxis_record_outcome` per verified slice, re-query / re-partition, and the gates resume enforcing.
Never leave the marker behind once the work is done.

## 0c. Work-review (auto, the ship gate)

Once the build-completeness gate flips the manifest to **`done`** (build **FINISHED** — the build
set is empty), **auto-run `factory-review` in WORK mode** over the whole diff/codebase (not one
requirement — the full change set this run produced). Same shape as the plan-side gate in
`factory-audit` §6: the `review_gate` (`hooks/review_gate.py`, armed by `.factory/review-status.json`)
**blocks 'shipped' from ending** until the work-review is either **done with no open findings** or
**skipped-with-reason** — never silently. This is the cold-eyes pass on the generated code, the
counterpart to the plan review.

Mode-aware:
- **Attended:** run the review as the panel and present its findings as **one batched review**;
  resolve or consciously dismiss each before the gate clears.
- **Unattended (owner asleep):** **auto-skip-if-small** — if the diff is below the review heuristic's
  size/risk floor, skip with a recorded reason + `praxis_record_episode` and let the gate pass.
  Otherwise **run** it and **defer** open findings as owned-decisions (episode each, drop them in the
  ledger for morning review) rather than blocking — done-or-skipped clears the gate, every deferral
  is explicit.

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
