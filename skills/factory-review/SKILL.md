---
name: factory-review
description: >
  The holistic cold-eyes review layer that runs at the two finalization moments the per-item checks
  can't see: AFTER the plan is finalized (factory-audit passed + save_snapshot) and AFTER the build
  reaches completeness. Per-item checks catch per-requirement defects; this panel catches the
  EMERGENT, cross-cutting ones — a source/scope contract inconsistency, an unsatisfiable build target
  — that are invisible per item and only visible to an independent panel over the WHOLE artifact. It
  convenes a cold-eyes panel and emits every finding as a Praxis TICKET or CHECK (which the one
  build_completeness gate then drives to done) plus a single panel-ran Praxis EPISODE so the act of
  reviewing can never be silently skipped.
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

In this skill: this skill does NOT itself build tickets — it collapses the holistic review into the loop.
It convenes an independent cold-eyes panel over the WHOLE artifact at the two finalization moments, then
emits each emergent finding as a Praxis TICKET (a missing/changed requirement → incomplete, so the loop's
FIND→FINISH drives it to done) or CHECK (a "this must hold" rule, which RESOLVEs onto matching tickets as a
pinned check), plus ONE panel-ran Praxis EPISODE. There is no separate review gate: the one
build_completeness gate already refuses "done" while any emitted finding's ticket/check is still incomplete.

# Factory Review (holistic cold-eyes panel — the missing layer)

The factory has strong **per-item** checks: each requirement carries its own pinned checks, resolved
fresh at ticket start (the RESOLVE step), and a ticket is `finished` only when every pinned check
passes (FINISH). The one **`build_completeness`** Stop gate then enforces, live against Praxis, that
**no incomplete ticket or check remains** for a scope. Every per-item check judges **one item against
its own contract**. None of them stands back at the **whole artifact at once**, so a defect that is
*correct per item but wrong in aggregate* sails straight through. Two real bugs proved it:

- a **source/scope contract inconsistency** — every requirement individually well-formed, but the
  `source` convention and the scope boundary disagreed across the set (a **coherence** defect);
- an **unsatisfiable build target** — a requirement tagged so it could never be satisfied (a manual /
  post-MVP item routed into the automated build set), individually plausible, collectively impossible
  (a **feasibility/architecture** defect).

Both are *emergent*: invisible to a per-requirement check, obvious to a diverse panel reading the
whole fact-set / whole diff with cold eyes. This skill is that panel — run at two moments, and made
non-skippable not by a private state file but by **turning each finding into a Praxis ticket/check
the existing completeness gate already enforces.**

## How it works in the locked model

This skill writes **NO** local state — no manifest, no status file, no arming flag, no findings state
machine, no separate review gate. Praxis is the single source of dynamic truth. The skill does exactly
three things:

1. **Convene the panel** — spawn independent cold-eyes reviewers over the whole artifact.
2. **Emit each finding as a Praxis ticket or check** (`meta.build_state:"incomplete"`), bound to the
   project / surfaces so the **`build_completeness`** gate refuses "done" until it is built/passed.
   A finding that is a missing requirement becomes a **ticket**; a finding that is a "this must hold"
   rule becomes a **check** (which then RESOLVEs onto matching tickets as a pinned check).
3. **Record ONE panel-ran Praxis EPISODE** asserting the panel actually ran for this scope — the only
   residue kept, so the act of reviewing cannot be silently skipped. It is an assertion, not a status
   machine.

There is no separate gate to satisfy: a finding is "closed" exactly when its emitted ticket/check
reaches `meta.build_state:"finished"` (built or accepted-and-marked-finished), which is precisely what
the one completeness gate already measures. You don't flip a status to pass — you admit the work and let
the build loop drive it to done.

## Why independent (cold eyes), not self-review

`factory-verify` records the core lesson: **a model judging its own output inflates its own pass
rate.** A holistic review the builder runs on itself is the weak kind. So the panel is **separate
sub-agents** spawned via the **Agent tool**, each a different compound-engineering reviewer with its
own lens — they did not write the plan or the code, so they challenge harder and disagree with each
other. **Do not reinvent reviewers**; the compound-engineering reviewers (listed per mode below) ARE
the panel.

### compound-engineering is the DEFAULT panel — and a declared dependency

The cold-eyes panel is **not** a "use them if installed" preference — the **compound-engineering**
plugin's reviewer agents are the **default, required panel** for both modes. The factory **declares
this as a hard plugin dependency** so Claude Code resolves and installs it automatically:

- `\.claude-plugin/plugin.json` and the marketplace entry declare
  `dependencies: [{ "name": "compound-engineering", "marketplace": "compound-engineering-plugin" }]`;
- the root marketplace (`agent-factory-local`) allows the cross-marketplace pull via
  `allowCrossMarketplaceDependenciesOn: ["compound-engineering-plugin"]`.

On install/enable of agent-factory, Claude Code auto-installs and enables compound-engineering.

### PRESENCE CHECK — run before convening the panel

Before spawning the panel (in **either** mode), **verify the compound-engineering reviewer agents for
this mode resolve** via the Agent tool / `/code-review`:

- **Present** → spawn the panel as normal.
- **Absent** (compound-engineering not installed/enabled, or its reviewer subagents do not resolve)
  → **do NOT proceed and do NOT record a panel-ran episode**. With no panel-ran episode, this scope
  has not been reviewed; surface the remediation:

  ```bash
  claude plugin marketplace add EveryInc/compound-engineering-plugin
  claude plugin install compound-engineering@compound-engineering-plugin
  ```

  (or `/reload-plugins`). A missing panel is a **blocked review**, never a silent pass. Absence is
  distinct from a deliberate, recorded **skip** (small/low-risk policy below): you may only skip
  through that explicit policy, never because the reviewers weren't there.

---

## MODE 1 — PLAN-REVIEW (after the plan is finalized)

**Trigger:** immediately after `factory-audit` passes **and** `save_snapshot("prd-<project>")` blesses
the plan. The audit hardened each requirement; this reviews the **whole `prd-<project>` fact-set +
tech decisions** as one artifact.

**Surface the panel reads:** the full admitted requirement set (`praxis_list_graph` /
`praxis_get_context` on the snapshotted graph), the out-of-scope set, the tech decisions (read from
Praxis, never from a local file), plus the PRD prose and wireframe. Hand each reviewer the **whole**
set, not one requirement.

**Lenses (≥1 independent reviewer each — the DEFAULT panel is the compound-engineering plan reviewers
below, spawned via the Agent tool with these subagent types; run the PRESENCE CHECK first):**

| Lens | ce subagent type | Catches (e.g.) |
|---|---|---|
| contract / convention coherence | `ce-coherence-reviewer` | the **source/scope** inconsistency |
| architecture / feasibility | `ce-feasibility-reviewer` | the **unsatisfiable manual / post-MVP target** |
| scope / strategy | `ce-scope-guardian-reviewer` | scope creep, mismatch to STRATEGY |
| security | `ce-security-lens-reviewer` | missing authz/PII/secret decisions across reqs |
| completeness / product | `ce-product-lens-reviewer`, `ce-design-lens-reviewer` | gaps between requirements, unmet user journeys |

Run them as cold-eyes sub-agents (not self-review). Each returns findings; collect them all.

**Emitting plan findings into Praxis:** for each distinct (deduped) emergent finding, admit a Praxis
fact (the `prd-<project>` source convention applies to the fact itself):

- a **missing/changed requirement** → a new requirement **ticket** with
  `meta.build_state:"incomplete"` and the identity tags/surfaces it concerns (so its checks RESOLVE
  and the build loop must build it). The ticket carries identity only — NEVER an authored list of its
  checks;
- a **"this must hold across the plan" rule** → a **check** fact carrying its own applicability
  predicate (`meta.applies_to` tag / bound surface) — never an authored per-ticket list. It then
  RESOLVEs onto matching tickets as a pinned check at their next start.

Create these via `factory-memory` (`praxis_add_insight` / `praxis_insert_fact`). Re-opening already-
finished tickets to apply a new plan-level check is the `factory-redo-plan-add-check` path.

---

## MODE 2 — WORK-REVIEW (after the build reaches completeness)

**Trigger:** immediately after the build for a scope reaches completeness — no incomplete
tickets/checks remain, read live from Praxis. Use the BARE project name: query
`incomplete_requirements("team-app")` (or `/requirements/incomplete?project=team-app`); the endpoint
prepends `prd-` itself. **NEVER pass the already-prefixed `prd-team-app`** — that searches for
`prd-prd-team-app`, returns EMPTY, and would make every build look complete. This reviews the **whole
diff / codebase** as one artifact — emergent defects across files, not one task.

**Surface the panel reads:** the full diff for the build (`git diff` against the build's base) and the
touched modules in context.

**Lenses (≥1 independent reviewer each — the DEFAULT panel is the compound-engineering code reviewers
below, spawned via the Agent tool with these subagent types, or the `/code-review` skill which
orchestrates them; run the PRESENCE CHECK first):**

| Lens | ce subagent type |
|---|---|
| architecture / strategy | `ce-architecture-strategist` |
| correctness | `ce-correctness-reviewer` |
| security | `ce-security-reviewer` |
| maintainability | `ce-maintainability-reviewer` |
| performance | `ce-performance-oracle` |
| testing | `ce-testing-reviewer` |

Don't reinvent these — `/code-review` already merges/dedups their tiered output; either drive it or
spawn the subagents directly.

**Emitting work findings into Praxis:** for each distinct (deduped) emergent finding, admit a Praxis
fact (the `prd-<project>` source convention applies to the fact itself):

- a defect that demands a fix → a **ticket** with `meta.build_state:"incomplete"` and the tags/surfaces
  of the touched area, so the build loop re-opens (FIND) and the completeness gate stays blocked until
  it is `finished`;
- a recurring "this must be proven" rule → a **check** (e.g. an e2e test requirement) — the
  `factory-redo-ticket-add-validation` path when it must also regress already-finished tickets.

---

## Findings are enforced by the ONE completeness gate

A holistic review that only *prints suggestions* changes nothing under context pressure. In the locked
model the forcing function is structural and needs no second gate:

1. **Dedupe.** Multiple reviewers will report the same emergent issue from different angles; merge into
   one finding per distinct defect (carry the strongest severity/lens) BEFORE emitting it, so you admit
   one ticket/check per real defect, not five.
2. **Emit each finding as an `incomplete` Praxis ticket/check** (above). That is the entire enforcement
   mechanism: `build_completeness` already refuses "done" while any incomplete ticket/check exists for
   the scope, so an unaddressed finding structurally blocks the phase.
3. **Closing a finding** = its emitted ticket/check reaching `meta.build_state:"finished"`:
   - **resolved** — the artifact changed and the ticket's pinned checks pass → the build loop marks it
     `finished` (the FINISH step);
   - **accepted** — a conscious decision to ship as-is: this is an owned trade-off, recorded as a Praxis
     EPISODE (the reason) and the ticket released `finished` deliberately, never silently dropped.

There is no `open`/`resolved`/`accepted` field in a JSON manifest — the ticket's `meta.build_state` in
Praxis IS the state. Praxis is a HARD dependency here: if it is unreachable you cannot admit findings
or read completeness, and the factory FAILS CLOSED (the completeness gate blocks) — it never proceeds
as if the review passed.

---

## Panel-ran assertion — the only residue

After the panel runs for a scope, record exactly **one** Praxis EPISODE asserting it ran:
`praxis_record_episode` with the phase (`plan` | `work`), the project, the panel composition, and the
count of findings emitted. This is an **assertion that reviewing happened**, not a findings state
machine — its sole job is that the act of reviewing cannot be silently skipped. (A completeness
policy that wants to require review-happened-before-done can assert against this episode; this skill
just records it truthfully.)

---

## SKIPPABLE — explicit policy, never silent (recorded as an episode, not a file)

Compute a **size/risk signal**:

- **plan:** number of new/changed requirements since the last blessed snapshot; `small` =
  `value <= threshold` (default 20).
- **work:** changed lines in the build diff; `small` = under threshold (default ~400) **AND no
  high-risk area touched** (auth/authz, payments, secrets/config, migrations/data-lifecycle,
  deploy/CI). Touching a high-risk area forces non-small regardless of size.

**Policy = AUTO-HEURISTIC + HUMAN OVERRIDE:**

| Situation | Action |
|---|---|
| **small AND attended** | **propose** skip to the human; they confirm → record a `praxis_record_episode` skip assertion with the reason. No confirm → run the panel. |
| **small AND unattended** | **auto-skip** → record a `praxis_record_episode` skip assertion (`"auto-skip: small/low-risk, unattended"`) so the heuristic compounds. |
| **NOT small** | review is **mandatory**. A human MAY still force-skip, but only with an explicit, recorded reason in the skip episode — never a default. |

**Never skip silently** — every skip leaves a reason in a Praxis episode. A skip is the *absence* of a
panel-ran episode plus the *presence* of a skip episode; it never fabricates a panel-ran assertion and
never edits config to get past the panel.

## Never

- **Never write or read any local state file** — no manifest, status file, arming flag, or
  `panelRan`/findings field on disk. Praxis is the only dynamic store.
- **Never advisory-only** — every finding becomes an `incomplete` Praxis ticket/check the completeness
  gate enforces; an unaddressed finding structurally blocks the phase.
- **Never self-review the panel** — the reviewers are independent sub-agents (a different installed ce
  reviewer per lens), never the agent that wrote the plan/code grading itself.
- **Never pass the prefixed project name** to the incomplete endpoint — `prd-<project>` becomes
  `prd-prd-<project>`, returns EMPTY, and fakes completeness. Pass the BARE name.
- **Never skip silently** — every skip records a reason as a Praxis episode.
- **Never accept a finding silently** — accepting (ship as-is) records the reason as a Praxis episode
  before the ticket is released `finished`.
- **Never pass on a missing panel** — if the compound-engineering reviewers aren't available, record
  NO panel-ran episode and surface the remediation; absence is never a skip.
- **Never fail open** — if Praxis is unreachable you cannot prove the review or read completeness, so
  the phase BLOCKS.

## Compounding

This layer is where the factory *learns its own blind spots*. Each emergent finding is a class of
defect the per-item checks structurally can't see — so feed it back: `praxis_record_episode` on every
auto-skip (to tune the size/risk heuristic) and on recurring finding patterns. A lens that keeps
firing on a defect class is a signal to **harden it into a declarative check** (via
`factory-add-validation` / `factory-add-planning-check`) so the next plan and the next build catch it
per-item for free — the cold-eyes panel converting one-off whole-artifact catches into cheaper
standing checks.
