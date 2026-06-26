---
name: factory-review
description: >
  The holistic cold-eyes review layer that runs at the two finalization moments the per-item gates
  can't see: AFTER the plan is finalized (factory-audit passed + save_snapshot) and AFTER the build
  is done (build-completeness flips to done). Per-item gates (plan_gate, factory-audit, factory-verify,
  build-completeness) catch per-requirement defects; this layer catches the EMERGENT, cross-cutting
  ones — a source/scope contract inconsistency, an unsatisfiable build target — that are invisible
  per item and only visible to an independent panel over the WHOLE artifact. Auto-triggered at each
  moment, GATED (the review_gate Stop hook blocks "planning done" / "build done" until review is
  resolved), and skippable for small/low-risk work via an explicit, never-silent policy.
---

# Factory Review (holistic cold-eyes panel — the missing layer)

The factory already has strong **per-item** gates: `plan_gate` (binary acceptance / no-vague /
no-dangling, per requirement), `factory-audit` (adversarial challenge per requirement +
tech-decision sweep), `factory-verify` (external-signal pass per task), `build-completeness` (every
build-target requirement verified). Each judges **one item against its own contract**. None of them
stands back and looks at the **whole artifact at once**, so a defect that is *correct per item but
wrong in aggregate* sails straight through. Two real bugs proved it:

- a **source/scope contract inconsistency** — every requirement individually well-formed, but the
  `source` convention and the scope boundary disagreed across the set (a **coherence** defect);
- an **unsatisfiable build target** — a requirement tagged so it could never be satisfied (a manual
  / post-MVP item routed into the automated build set), individually plausible, collectively
  impossible (a **feasibility/architecture** defect).

Both are *emergent*: invisible to a per-requirement check, obvious to a diverse panel reading the
whole fact-set / whole diff with cold eyes. This skill is that panel, run at two moments and **gated**.

## Why independent (cold eyes), not self-review

`factory-verify` already records the core lesson: **a model judging its own output inflates its own
pass rate.** A holistic review the builder runs on itself is the weak kind. So the panel is
**separate sub-agents** spawned via the **Agent tool**, each a different
compound-engineering reviewer with its own lens — they did not write the plan or the code, so they
challenge harder and disagree with each other. **Do not reinvent reviewers**; the
compound-engineering reviewers (listed per mode below) ARE the panel.

### compound-engineering is the DEFAULT panel — and a declared dependency

The cold-eyes panel is **not** a "use them if installed" preference — the **compound-engineering**
plugin's reviewer agents are the **default, required panel** for both modes. The factory **declares
this as a hard plugin dependency** so Claude Code resolves and installs it automatically:

- `\.claude-plugin/plugin.json` and the marketplace entry declare
  `dependencies: [{ "name": "compound-engineering", "marketplace": "compound-engineering-plugin" }]`;
- the root marketplace (`agent-factory-local`) allows the cross-marketplace pull via
  `allowCrossMarketplaceDependenciesOn: ["compound-engineering-plugin"]`.

On install/enable of agent-factory, Claude Code auto-installs and enables compound-engineering. This
is **general** — it holds for any project the factory runs in, not one app. The factory's **eval
engine already leverages compound-engineering's reviewers**; declaring the dependency here and
defaulting the panel to those reviewers simply **formalizes** that existing reliance so the gate can
depend on it.

### PRESENCE CHECK — run at panel time, before deciding the phase is done

Before spawning the panel (in **either** mode), **verify the compound-engineering reviewer agents
for this mode are actually available** (the subagent types in the table below resolve via the Agent
tool / `/code-review`). The dependency declaration makes this true automatically, but the check is
the backstop for a half-installed or disabled environment:

- **Present** → spawn the panel as normal.
- **Absent** (compound-engineering not installed/enabled, or its reviewer subagents do not resolve)
  → **do NOT proceed and do NOT skip the panel**. The gate must **not** pass on a skipped panel.
  Set `panelRan:false`, leave `status:"pending"`, and surface the remediation to install the
  declared dependency:

  ```bash
  claude plugin marketplace add EveryInc/compound-engineering-plugin
  claude plugin install compound-engineering@compound-engineering-plugin
  ```

  (or `/reload-plugins`, which re-resolves the declared dependency from the configured marketplace).
  A missing panel is a **blocked phase**, never a silent pass — `panelRan:false` keeps `review_gate`
  BLOCKING. Absence is distinct from a deliberate, recorded **skip** (small/low-risk policy below):
  you may only mark `status:"skipped"` through that explicit policy, never because the reviewers
  weren't there.

---

## MODE 1 — PLAN-REVIEW (after the plan is finalized)

**Trigger:** immediately after `factory-audit` passes **and** `save_snapshot("prd-<project>")`
blesses the plan. The audit hardened each requirement; this reviews the **whole `prd-<project>`
fact-set + tech decisions** as one artifact.

**Surface the panel reads:** the full admitted requirement set (`praxis_list_graph` /
`praxis_get_context` on the snapshotted graph), `out_of_scope`, the `techDecisions` from
`.factory/plan-audit.json`, plus the PRD prose and wireframe. Hand each reviewer the **whole** set,
not one requirement.

**Lenses (≥1 independent reviewer each — the DEFAULT panel is the compound-engineering plan
reviewers below, spawned via the Agent tool with these subagent types; run the PRESENCE CHECK first):**

| Lens | ce subagent type | Catches (e.g.) |
|---|---|---|
| contract / convention coherence | `ce-coherence-reviewer` | the **source/scope** inconsistency |
| architecture / feasibility | `ce-feasibility-reviewer` | the **unsatisfiable manual / post-MVP target** |
| scope / strategy | `ce-scope-guardian-reviewer` | scope creep, mismatch to STRATEGY |
| security | `ce-security-lens-reviewer` | missing authz/PII/secret decisions across reqs |
| completeness / product | `ce-product-lens-reviewer`, `ce-design-lens-reviewer` | gaps between requirements, unmet user journeys |

Run them as cold-eyes sub-agents (not self-review). Each returns findings; collect them all.

---

## MODE 2 — WORK-REVIEW (after the build is done)

**Trigger:** immediately after the `build-completeness` gate flips `.factory/build-status.json` to
`status:"done"` (build target empty, every targeted requirement verified). This reviews the **whole
diff / codebase** as one artifact — emergent defects across files, not one task.

**Surface the panel reads:** the full diff for the build (`git diff` against the build's base) and
the touched modules in context.

**Lenses (≥1 independent reviewer each — the DEFAULT panel is the compound-engineering code
reviewers below, spawned via the Agent tool with these subagent types, or the `/code-review` skill
which orchestrates them; run the PRESENCE CHECK first):**

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

---

## Findings are GATED, not advisory

A holistic review that only *prints suggestions* changes nothing under context pressure — the same
reason the wireframe coverage and plan-audit gates are forcing functions, not good intentions. So:

1. **Dedupe.** Multiple reviewers will report the same emergent issue from different angles; merge
   into one finding per distinct defect (carry the strongest severity/lens).
2. **Each finding must be CLOSED before the phase is truly done** — one of:
   - **resolved** — the artifact changed to fix it (re-plan/edit a requirement; fix the code),
     recorded in `resolution`;
   - **accepted** — a conscious decision to ship it as-is, with a **non-empty reason** in
     `resolution` (an owned trade-off, not silence).
   No finding may remain `open`.
3. **Write them into the manifest** (`<project>/.factory/review-status.json`) — that artifact is the
   gate's source of truth.

---

## SKIPPABLE — explicit policy, never silent

Compute a **size/risk signal** and set `size.small`:

- **plan:** `metric:"changed-requirements"`, `value` = number of new/changed requirements since the
  last blessed snapshot; `small` = `value <= threshold` (default 20).
- **work:** `metric:"diff-lines"`, `value` = changed lines in the build diff; `small` = under
  threshold (default ~400) **AND no high-risk area touched** (auth/authz, payments, secrets/config,
  migrations/data-lifecycle, deploy/CI). Touching a high-risk area forces `small:false` regardless
  of size.

**Policy = AUTO-HEURISTIC + HUMAN OVERRIDE:**

| Situation | Action |
|---|---|
| **small AND attended** | **propose** skip to the human; they confirm → `status:"skipped"`, record `skipReason`. No confirm → run the panel. |
| **small AND unattended** (Constitution / owner asleep) | **auto-skip** → `status:"skipped"`, `skipReason:"auto-skip: small/low-risk, unattended"`, plus `praxis_record_episode` (so the heuristic compounds) **and** a ledger note. |
| **NOT small** | review is **mandatory**. A human MAY still force-skip, but it requires BOTH `forceSkip:true` AND a non-empty `skipReason` (their explicit override) — the gate rejects a `"skipped"` on non-small work that lacks `forceSkip`. |

**Never skip silently** — every skip leaves a `skipReason` in the manifest (and, when auto, an
episode + ledger note).

---

## THE GATE — the skill WRITES it, the `review_gate` hook ENFORCES it

This skill **writes** `<project>/.factory/review-status.json`. The **`review_gate` Stop hook**
*enforces* it: while `status:"pending"`, it **blocks the turn from ending** (blocks any claim of
"planning done" / "build done") until the review is resolved. A SKILL can only *ask*; the hook is
what makes it non-skippable under pressure — the same enforcement shape as
`plan_audit_gate.py` / `build_completeness_gate.py`.

**Manifest — `<project>/.factory/review-status.json` (matches the shared contract verbatim):**

```json
{
  "phase": "plan",
  "project": "prd-team-app",
  "status": "pending",
  "skipReason": "",
  "forceSkip": false,
  "size": { "metric": "changed-requirements", "value": 12, "threshold": 20, "small": true },
  "panelRan": true,
  "findings": [
    { "id": "F1", "lens": "coherence", "severity": "high", "summary": "...", "status": "open", "resolution": "" }
  ],
  "attempts": 0,
  "maxAttempts": 30
}
```

- `phase`: `"plan"` | `"work"` — which review surface.
- `status`: `"pending"` (gate armed) | `"done"` | `"skipped"`.
- `skipReason`: REQUIRED non-empty when `status=="skipped"`.
- `size.metric`: `"changed-requirements"` | `"diff-lines"` | `"..."`.
- `panelRan`: the independent cold-eyes panel actually ran (≥1 compound-engineering reviewer per
  lens). Stays `false` when the PRESENCE CHECK fails (compound-engineering absent) — install the
  declared dependency and re-run; never flip it true or `skip` to get past a missing panel.
- `findings[].severity`: `"high"` | `"med"` | `"low"`; `findings[].status`: `"open"` | `"resolved"`
  | `"accepted"`.

**GATE RULE (what `review_gate` enforces — it recomputes the bar from evidence; a self-reported
`status` is never a free pass):**

- The bar, checked for `pending` AND `done` alike: `panelRan==true` AND every finding is
  **closed** (`status` in `resolved`/`accepted` AND a **non-empty `resolution`**). Met → ALLOW (the
  gate flips `status` to `done`); not met → **BLOCK**. Marking `status:"done"` with `panelRan:false`,
  an open finding, or an empty resolution does NOT pass — the gate ignores the claim and recomputes.
- **ALLOW** when `status=="skipped"` only if `skipReason` is non-empty **AND** (`size.small==true`
  **OR** `forceSkip==true`). Non-small / high-risk work cannot be skipped without an explicit
  `forceSkip` override.
- **Armed upstream, not by this skill:** `plan_audit_gate` writes a `{phase:"plan",status:"pending"}`
  manifest when the audit passes, and `build_completeness_gate` writes `{phase:"work",...}` when the
  build finishes — so the gate is armed at finalization whether or not the worker remembers to run
  the panel. This skill **fills in** that armed manifest (panel results, findings, resolutions); it
  doesn't create it.
- **Inert** if no manifest. **Fail-open** on any error. **Loop-guarded** by `maxAttempts` (default
  30): on giving up it surfaces the open findings to the human rather than blessing.

You don't set `status:"done"` to pass — you make the evidence true (run the panel, resolve/accept
every finding with a reason) and the gate flips it for you. Hand-waving the status past open findings
is the one thing the gate now structurally prevents.

## Never

- **Never advisory-only** — findings are gated; an unresolved finding blocks the phase.
- **Never self-review the panel** — the reviewers are independent sub-agents (different installed ce
  reviewer per lens), never the agent that wrote the plan/code grading itself.
- **Never skip silently** — every skip records a `skipReason` (auto-skip also records an episode + a
  ledger note).
- **Never bless with open findings** — `status:"done"` requires every finding `resolved`/`accepted`
  with a non-empty `resolution`.
- **Never pass on a missing panel** — if the compound-engineering reviewers aren't available, the
  phase is BLOCKED (install the declared dependency); absence is never a skip.

## Compounding

This layer is where the factory *learns its own blind spots*. Each emergent finding is a class of
defect the per-item gates structurally can't see — so feed it back: `praxis_record_episode` on every
auto-skip (to tune the size/risk heuristic) and on recurring finding patterns (a lens that keeps
firing on a defect class is a signal to harden an upstream gate, e.g. add a `plan_gate` rule for a
recurring coherence break). Over time the cold-eyes panel converts one-off whole-artifact catches
into cheaper per-item checks — the review layer makes the next plan and the next build start ahead.
