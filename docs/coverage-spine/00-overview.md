# The Coverage Spine — overall design

> Consolidated design for reframing the agent factory around **data-driven coverage gates**.
> Companion files: [`01-praxis-changes.md`](01-praxis-changes.md) · [`02-planner.md`](02-planner.md) · [`03-eval-agent.md`](03-eval-agent.md) · [`05-coverage-engine.md`](05-coverage-engine.md).
> Background design (brownfield framing that this supersedes/simplifies): `../plans/2026-06-26-brownfield-refactor-support-design.md`.

## Core principle
Praxis is the foundation. The factory's method is **heavy planning → exhaustive verification → insert the verified plan into Praxis, so that NO decision remains for execution** (execution is a mechanical reducer). Build features so they are ~80% a planning-surface problem.

## The one spine
Every substantive gate is the same machine:

> **for every item in a coverage SET, prove it is addressed against a TARGET; recompute from evidence; never trust a self-flag; loop-guard; fail-open; block until zero holes.**

This already exists three times in the code:
- `hooks/plan_audit_gate.py` — every requirement has every challenge closed (+ techDecisions, testStrategy).
- `hooks/build_completeness_gate.py` — every build-target requirement verified-complete.
- `hooks/review_gate.py` — every review finding closed.

The reframe: **make the coverage SET come from Praxis instead of being hard-coded**, and recognize that planning, validation (the coding agent), and the eval are all *the same spine with different parameters*.

## The parameters that vary (none forks the spine)
| Parameter | Planning | Coding agent (validation) | Plan-repro eval |
|---|---|---|---|
| Coverage **SET** | planning checklist (Praxis `planning` snapshot) | validation checks bound to the surface (Praxis `validation` snapshot) | the **golden** feature set (checked-in file) |
| **TARGET** | the plan / requirement graph | the code | the reproduced plan |
| Per-item **evaluator** | semantic "is this represented in the plan?" | "does the code pass this?" (run test / agent-eval) | semantic "is this feature covered?" |
| **Remediation** on a hole *(lives in the AGENT, not the gate)* | ask the user **or** expand the plan | run/write a test, then fix the code | ask the user **or** expand the plan |

Gates never remediate — they block and report. The differing responses are the agent loop the gate drives, so they don't split the engine.

## Data-driven gates (the mechanism)
Hooks **deliberately never call Praxis** (replicating MCP auth from a hook is fragile — see `build_completeness_gate.py:14-18`). So:

> **skill pulls the checklist from the Praxis snapshot → writes each applicable check into the `.factory/*.json` manifest → the generic hook enforces "every check entry is closed-with-evidence."**

Result: the hook gets *simpler and fully generic* (it stops knowing `GAP_LENSES`); all Praxis-awareness lives in the skill where MCP access already is. **Adding a check = adding a Praxis fact. No code change.**

Check rigor by kind:
- `deterministic` → a registered `Gate` in `src/agent_factory/gate.py` `REGISTRY` (today's `plan_gate` rules); the hook re-runs it.
- `agent-evaluated` → an **independent** (evaluator ≠ author) recorded pass + evidence; the hook recomputes closure from the evidence (exactly how challenges/findings work today).

## Eval vs. gate (same spine, different epistemics)
- The **eval** scores against a **GOLDEN** (ground truth — the known-good plan) → it *measures the planner's hole rate*. Offline.
- The **live gate** has no golden; it enforces against a **CHECKLIST** of considerations from Praxis → it *forces the planner to address each*. Inline.
- The eval is therefore the **meta-proof of the gate**: if the checklist-driven planner reproduces the golden with zero holes, the checklist has no holes.
- **The golden's `derived: true` features are the evidence for what the planning checklist must contain** (e.g. `AUTH-password-reset` being derived ⇒ the checklist needs a "credential-recovery flow" item). The eval and the planning checklist co-design each other.

## Brownfield = greenfield
Nothing in the spine cares about existing vs. empty code. A refactor is just a plan whose target acts on existing code; the gates and coding agent don't branch. (See the background plan doc for the fuller brownfield treatment this simplifies.)

## Closed-loop learning (why this compounds)
- A fix — *especially of something built wrong the first time* — must persist a **lesson** to Praxis (`category="learning"`, `derived_from` the requirement + failure), promoted to `general-pool` when general. Enforce with a gate (`lesson_gate`).
- A lesson is **proven by an eval** that reproduces the mistake-prone situation and asserts the fix — across any surface (planning, validation, …). A lesson with no passing eval is "unproven."
- `factory-fix` is the thin **write path**: fix + PR + add the check/lesson to Praxis.

## Current workstreams
1. **Planning eval** (this thread) — coverage of a plan reproduced from `docs/inspiration/` vs. the golden. See `03-eval-agent.md`. Lives in `evals/plan_repro/`.
2. **Validation checks on `../team-app`** (separate thread) — seed the `validation` snapshot from real team-app bugs, build the verify gate + the fail→regress→re-pick loop.
3. **The shared coverage engine** (`evals/plan_repro/coverage.py`) — built once, instantiated by both planning-coverage and validation-coverage. Design: [`05-coverage-engine.md`](05-coverage-engine.md) (per-part sweep + thorough per-part query + targeted adversarial; scales to thousands of insights).

## What exists today (ground truth)
- Gate machinery: `hooks/*.py`, `src/agent_factory/gate.py` (uniform `Reason`/`Verdict`/`Gate`/`REGISTRY`), `src/agent_factory/plan_gate.py` (deterministic rules), `src/agent_factory/build_target.py`.
- Eval harness: `evals/` (deterministic `case.yaml` cases under `evals/cases/plan_gate/`; loader rejects non-deterministic input).
- The golden: live Praxis `prd-team-app` graph (~78 requirements) → extracted to `evals/plan_repro/team-app/golden-features.yaml`.

## Relevant memories
`factory-dev-methodology`, `factory-planning-validation-snapshots`, `factory-closed-loop-learning` (in the user's memory dir).
