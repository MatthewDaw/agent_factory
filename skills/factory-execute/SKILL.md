---
name: factory-execute
description: >
  The single-ticket execution loop for the agent factory. Use to build ONE incomplete ticket from a
  hardened prd-<project> plan: claim the ticket's lease, resolve + pin the checks that apply, assemble
  hermetic context, do the work, run the pinned checks, gate through factory-verify, and release the
  ticket finished. One decision-making agent — it orchestrates phases and tools, and may dispatch a
  disposable read-only retrieval sub-agent for bulk reading (never a crew that decides or writes). All
  dynamic state lives in Praxis (claim, build_state, pinned_checks); this skill writes NO local
  manifests. To drive a WHOLE build set to completeness, the multi-ticket loop (factory-churn-tickets)
  calls this skill per ticket.
---

## How work flows (this factory's methodology — read first)

State lives in ONE place: Praxis. There are no JSON status files, no locks on disk, no self-set "done"
flags. A ticket (requirement) and a check are Praxis facts; everything about what is built/claimed/passed
is state ON THE TICKET'S Praxis node. To do ANY unit of work you follow exactly this loop:

1. FIND   — query Praxis for the next incomplete ticket in scope (incomplete = never-built | regressed |
            stale, derived from recorded outcomes). Pass the BARE project name (e.g. "team-app"); the
            endpoint adds the "prd-" prefix itself — passing "prd-team-app" returns EMPTY and silently
            hides all work.
2. CLAIM  — atomically set the ticket's meta.build_state="in_progress" with claim_owner=you + a heartbeat.
            The claim is a LEASE: refresh the heartbeat while working; a stale lease auto-reclaims so a
            dead agent never strands a ticket. Parallel agents never double-work because a live claim is
            visible to all.
3. RESOLVE— determine which checks this ticket must pass by QUERY (its tag ∪ its surfaces ∪ semantic
            match against active checks). The ticket NEVER stores its own check list. Truncate any prior
            per-check state, then PIN the freshly-resolved set onto the ticket as this pass's contract.
4. BUILD  — do the work to satisfy the ticket's acceptance condition.
5. VERIFY — run each pinned check; record each pass ON THE TICKET NODE (never on the check — checks are
            read-only during builds). External signals only; never self-judge.
6. FINISH — only when EVERY pinned check passed: record a succeeded outcome and release the lease
            (build_state="finished"). If any check fails, record a failed outcome — that regresses the
            ticket so it re-enters the FIND set and is re-done.

Praxis is a HARD dependency: if it is unreachable the factory STOPS (the gate blocks) — it never proceeds
on a guess. The single Stop gate (build_completeness) enforces this loop: it blocks the turn from ending
while you hold an unfinished claim or scoped incomplete tickets remain.

In this skill: single-ticket execution — steps CLAIM→RESOLVE→BUILD→VERIFY→FINISH for ONE ticket handed to
you by id. On start you truncate+resolve+pin the checks, set build_state=in_progress with a claim, and
heartbeat the lease while working. There is no Step-0 preflight manifest (env readiness now surfaces as
failing checks) and no .factory/*.json anywhere. The multi-ticket FIND loop that picks the next ticket and
drives the whole set to completeness is factory-churn-tickets, which calls this skill once per ticket.

# Factory Execute

One agent builds **one ticket** to done, against a plan that's already hardened (`factory-plan` →
`prd-<project>`). A ticket is a requirement Praxis node; its lifecycle state lives **on that node**.
This skill is the *doing* loop for a single ticket; the multi-ticket completeness loop
(`factory-churn-tickets`) drives the build set by calling this skill once per incomplete ticket.

**Praxis is the single source of dynamic truth and a HARD dependency.** All build/validation state —
`build_state`, the claim lease, `pinned_checks`, per-check pass results — lives on the ticket node in
Praxis, read and written live via `hooks/_ticket_state.py` (which sits on `hooks/_praxis.py`). Read
`docs/factory-state-contract.md` for the meta-key names, lifecycle, and function signatures; conform
to it exactly. If Praxis is unreachable the factory **crashes and stops** (fail-closed) — never invent
or cache state to keep going.

**There are NO `.factory/*.json` manifests.** This skill writes no build/validation/review/check/preflight
state to any file. JSON is static config only; any such state written to a file is the bug being purged.
Code lives in **git**, not Praxis; only judgments and learnings go to the graph. Every step is an
event-log entry; cite the fact(s) that grounded each decision.

## 0. Start the ticket (claim + resolve + pin — one call)

A ticket is handed to this skill by id (`cid`). On start, do all three of the following — they are the
single transaction `_ticket_state.start_ticket(cid, owner, project)` performs (pass the BARE project
name):

1. **Claim the lease.** `incomplete → in_progress`, stamping `meta.claim_owner`, `meta.claim_at`,
   `meta.claim_heartbeat_at`, `meta.claim_lease_ttl` (default `DEFAULT_LEASE_TTL_S = 900`). The claim
   is a **lease, not a lock**: a stale lease (`now - claim_heartbeat_at > claim_lease_ttl`) is
   auto-reclaimable so nothing dangles. "A build run is active" ≡ *this session owns a live,
   unfinished `in_progress` claim*, read from Praxis — never a file flag. Claiming is race-tolerant
   (read-modify-write via `patch_meta`); a rare double-claim is harmless wasted work, not corruption.
2. **Resolve which checks apply — a fresh QUERY, never a list authored on the ticket.**
   `resolve_checks(ticket, project)` returns the de-duplicated union of: **tag match** (active
   `category="check"` facts whose `meta.applies_to` contains any of the ticket's tags, incl. `"*"`)
   and **surface match** (active checks bound via the `renders` edge to any surface the ticket
   renders). The ticket carries identity (tags, surfaces, semantics) but NEVER an authored list of its
   checks. Checks are declarative and **read-only during a build** — you resolve them, you do not edit
   them.
3. **Pin the resolved set as this pass's completion contract.** `pin_checks(cid, checks)` **TRUNCATES**
   any prior `meta.pinned_checks` and writes the FRESH resolved set, each entry
   `{check_id, passed: null, ran_at: null}`. This pin is what "finished" will be measured against.

There is **no preflight manifest and no separate env-readiness step**. Environment readiness now
surfaces as ordinary checks: a missing env var / unauthenticated CLI / unreachable service is a
**failing check** in the resolved set, and the ticket simply can't finish until it passes. For
anything only the owner can provide (a secret, a credential), surface EXACTLY what's needed and record
a `praxis_record_episode`; never stub or fake a credential to make a check pass.

**Heartbeat the lease while you work.** Periodically call `_ticket_state.heartbeat(cid, owner)` (it
bumps `claim_heartbeat_at` iff you still hold a live lease) so a long build doesn't go stale and get
reclaimed out from under you.

**Pin knowledge at kickoff.** Record the run's `as_of` timestamp (via `factory-memory`) so every
retrieval this run sees one stable plan even as write-backs land, and **mount read-only**
`general-pool` (conventions) + the project's `prd-<project>` snapshot. The live graph is this run's
scratch; the plan + conventions are mounted, not copied in.

## 1. Build the ticket

**a. Assemble hermetic context (declare it; don't free-query mid-task).** Up front, pull exactly: the
ticket's requirement + its **binary acceptance condition**, the conventions/invariants it touches, and
any ticket-specific facts — via declared `factory-memory` queries (scope + top_k + `as_of`). Budget it
(hot constitution always in; warm/cold to a ceiling well below the context-rot threshold). The agent
works from this sealed bundle; if it discovers it needs more, that's a new declared pull, logged — not
unbounded mid-task querying. For a **screen-scoped ticket**, pull the governing behavior with
**`praxis_requirements_for_surface(project, screen_id)`** — the active requirement facts bound to that
wireframe screen via the `renders` relation (factory-intake §3) — and take the layout from the
wireframe HTML in git.

**Read-only retrieval sub-agent (the one permitted delegation).** When populating the bundle needs
reading many files or large surfaces, dispatch a *disposable, single-shot* sub-agent to do that
reading and return a compact digest — so the parent's window never absorbs the raw noise. Hard
constraints, or it degrades into a crew:
- **Read-only tools only** (Read/Grep/Glob/LS). It never edits, runs state-changing commands, writes
  to Praxis, or commits.
- **One shot, no dialogue.** It returns once; you don't converse with it or chain it into a decision.
- **Cheap model, fixed compact schema.** Output is a curator's digest, not a dump: *file → role*, the
  specific facts/patterns asked for, constraints/gotchas found, and what's *still unknown*. Instruct
  it to **filter ruthlessly — it is a curator of insights, not a summarizer.**
- You remain the **only** agent that decides, edits, writes to Praxis, or commits. This is context
  hygiene, not orchestration.
- **Read-fully guard:** any file the human or the plan names *explicitly* is read **fully in your own
  context first** (no limit/offset) — only *exploratory / bulk* reading is delegated.

**b. Re-anchor the goal.** Restate the ticket's acceptance condition at the start of each cycle (and
after any context compaction). Goal drift comes from semantic accumulation, not token count —
re-injecting the objective is the cheap, proven defense.

**c. Act.** The single agent does the work with real tools in the sandbox/repo (edit, run, search).
Make the change that satisfies the acceptance condition — nothing broader (resist scope creep into
adjacent tickets). Heartbeat the lease (§0) across long stretches of work.

**d. Run the pinned checks + gate via `factory-verify`.** Run each check in `meta.pinned_checks`, and
record its result **on the ticket node** with `_ticket_state.record_check_pass(cid, check_id, passed,
ran_at)` — **never on the check fact**. Hand the output to `factory-verify` for the pass/fail
judgment against external signals (tests, build, type-check, lint). On **fail**, re-enter (c) with the
**captured failing signal** as context — corrections are signal-driven, never self-directed. Respect
verify's bounded loop: N identical failures → replan the ticket; M replans → escalate to the human.
Verify the ticket's **automated** acceptance criteria yourself; for any criterion tagged **manual**
(factory-plan §2b), in an attended run pause and hand it off for human confirmation, and in an
unattended run record it as a deferred owned decision (per the Constitution) and proceed.

**e. Write back (only what an external signal confirmed).** On a verified pass, write confirmed
learnings/fixes via `factory-memory` (`on_conflict="surface"`, serial or `add_insights` for a batch,
read-back-on-timeout). Stamp `source`, `category="learning"`, and **`derived_from=[the fact ids that
grounded it]`** (so a flipped basis later surfaces this learning via `praxis_get_stale_derivations`).
Never write speculative facts; **never block the loop on a write** — queue it and proceed.

## 2. Finish (or yield) the ticket

The ticket is **finished IFF every pinned check passed** — `_ticket_state.all_checks_passed(ticket)`
(≥1 pinned check, all `passed == true`). The agent's say-so is not enough; completion is grounded in
the recorded check results plus `factory-verify`'s external signal.

- **Finished:** call `_ticket_state.release(cid, owner, state="finished")` (sets
  `meta.build_state="finished"` and NULLs the lease keys), and
  `praxis_record_outcome(cid, "succeeded")` to feed the trust loop. The ticket leaves
  `incomplete_requirements`; the one `build_completeness` gate sees it as done.
- **Yield cleanly** (handing back to the human, or a blocker you can't pass — e.g. a check only the
  owner can satisfy): `release(cid, owner, state="incomplete")` so the lease drops and the ticket is
  reclaimable, and say why. Never fake a check pass to escape the loop — completeness is
  outcome-grounded, so the only honest finish is to actually build and pass every pinned check.
- **On a failed attempt:** `praxis_record_outcome(cid, "failed")` on the facts behind the failure —
  this regresses the ticket so it re-enters the FIND set and is re-done.

Review/audit is NOT a state machine in this skill: a review or audit *finding* becomes its own Praxis
ticket or check (it re-enters as work), and the only review residue is a tiny "panel-ran" Praxis
**episode** so the act of reviewing can't be silently skipped. This skill finishes one ticket; it does
not run a separate review/deploy/completeness gate.

## 3. Long-horizon control (so the run survives length)

- **Disposable agent:** keep durable state in Praxis (the ticket node) + the event log, not the
  context window. If the context is compacted or the agent is re-spawned, reconstruct the working set
  from the pinned `as_of` view + the ticket's `meta.pinned_checks` + the log — losing the window
  should lose nothing.
- **Compact early, don't drop:** at **~50–60%** context fill, summarize old turns into a fixed
  **compaction artifact**: (1) end goal; (2) current approach; (3) steps completed; (4) **dead-ends
  tried and why they failed**; (5) key file locations + their roles; (6) next step + its binary
  acceptance condition. Drop raw tool output, keep its conclusions.
- **Heartbeat across the gap:** before any long-running step, `heartbeat` the lease so the ticket
  doesn't go stale and get reclaimed mid-build.
- **Saturation detector / circuit breaker:** watch round-trip count and repetition; trip before the
  rot threshold (re-anchor + compact) and on degeneration (escalate, per `factory-verify`).

## 4. Decisions are episodes (the why, not just the what)

When the loop makes a non-obvious choice (picked library X; defaulted Y because the plan was silent),
record it with **`praxis_record_episode`** (per `factory-memory` §1b) — `text` = decision + rationale,
`alternatives` = options not taken, `derived_from` = the facts it rested on. Episodes are store-only
and excluded from semantic recall by default, so the "why" compounds without polluting task-grounding
retrieval. Flip `outcome` later via `praxis_record_outcome` when the decision proves out or fails.

## Never
- Never write any `.factory/*.json` (or any other file) holding build/validation/review/check/preflight
  STATE. Dynamic state lives ONLY on the Praxis ticket node. JSON is static config.
- Never invent, cache, or fail-open around missing Praxis state. Praxis is a hard dependency; if it's
  unreachable, crash and stop.
- Never author a list of checks onto a ticket. Which checks apply is a fresh QUERY (`resolve_checks`)
  at ticket start, pinned as the pass contract — and checks are read-only during a build.
- Never record a check result on the check fact; record it on the ticket node (`record_check_pass`).
- Never mark a ticket finished unless every pinned check passed and `factory-verify` returned pass
  (external signal). Never fake a check pass to escape the loop.
- Never run a crew — one decision-making agent. The only permitted delegation is the disposable
  read-only retrieval sub-agent (§1a): it reads and digests, never decides/edits/writes/commits.
- Never write code or run state into Praxis; code is git, ephemeral state is the event log.
- Never free-query Praxis ad hoc mid-task — declare the hermetic bundle; new needs are new declared pulls.
- Never write a learning back that wasn't externally confirmed; never block the loop on a write.
- Never widen a ticket beyond its acceptance condition into adjacent tickets.
- Never query incomplete requirements with the "prd-" prefix — pass the BARE project name, or the
  endpoint searches "prd-prd-<project>", returns EMPTY, and the build looks falsely complete.
