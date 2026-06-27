# Agent Factory

A Praxis-backed **agent factory**, delivered as a Claude Code plugin: it turns a PRD into a
clickable wireframe, a hardened plan, and a built-and-deployed app — via a **plan → execute →
verify** loop with compounding memory. Every phase is **gated** (Stop-hook forcing functions, not
just prose), and the gates lean on a **cold-eyes review panel** so emergent defects per-item checks
miss get caught.

- **Knowing system** → [Praxis](https://github.com/Antonelli-Tech-Solutions/praxis) knowledge graph
  (retrieval, dedup, contradiction handling, provenance, requirement-completeness), via the
  `praxis_*` MCP tools.
- **Doing system + glue** → this repo: skills that drive the loop, gate hooks that enforce it, and
  small deterministic helpers in `src/agent_factory/`.

---

## The pipeline at a glance

```
 PRD (docs/inspiration/*.txt) ─┐
                               ├─►  factory-wireframe   →  clickable HTML wireframes  [wireframe gate]
 wireframe ────────────────────┘
                               │
            PRD + wireframe ───►  factory-intake        →  requirement-candidates.json [candidate review]
                               │
                               ├─►  factory-plan         →  admit + harden requirements in Praxis
                               │
                               ├─►  factory-audit        →  cold-eyes challenge + tech/test sweep [plan-audit gate]
                               │                            → save_snapshot("prd-<project>")
                               ├─►  factory-review(plan)  →  cold-eyes panel over the whole plan   [review gate]
                               │
            blessed plan ──────►  factory-execute        →  preflight [preflight gate]
                               │                            → fan-out build (mvp+automated)
                               │                            → factory-verify each slice
                               │                            → deploy  [build-completeness gate, incl. deploy]
                               └─►  factory-review(work)  →  cold-eyes panel over the diff          [review gate]
                                                            → shipped
```

The **five Stop-hook gates** (in `hooks/`) make each phase non-skippable; they read small JSON
manifests under `<project>/.factory/` and block the turn from ending until their bar is met. They
**defer** automatically while a fanned-out Workflow / subagents are still running.

---

## One-time setup

### 1. Install the plugin

```bash
git clone https://github.com/MatthewDaw/agent_factory.git
```

In Claude Code, register the clone as a **local directory** marketplace and install it:

```
/plugin marketplace add /absolute/path/to/agent_factory
/plugin install agent-factory@agent-factory-local
```

A *directory* marketplace reads the **live repo**, so the plugin's skills and gate hooks always
reflect your working tree (restart the session to pick up edits). Run `/plugin` to confirm
`agent-factory` is enabled.

### 2. compound-engineering (the cold-eyes panel) — auto-installed

The factory declares [compound-engineering](https://github.com/EveryInc/compound-engineering-plugin)
as a hard plugin **dependency** (in `.claude-plugin/plugin.json` + `marketplace.json`), so enabling
`agent-factory` auto-installs it. If it's ever missing, the review panel **blocks the phase** (never
silently skips) until you install it:

```
/plugin marketplace add EveryInc/compound-engineering-plugin
/plugin install compound-engineering@compound-engineering-plugin
```

### 3. Python on PATH

The gate hooks are Python scripts. Ensure `python` is on PATH — if it isn't, the hooks **fail open**
(they won't trap you, but they also can't enforce). `python --version` should work in a plain shell.

### 4. Raise the Stop-hook block cap

A real plan/build legitimately makes the gates block many times while the model iterates. Claude
Code's default cap (9 consecutive blocks → force-override) is far too low. In `~/.claude/settings.json`:

```json
"env": { "CLAUDE_CODE_STOP_HOOK_BLOCK_CAP": "250" }
```

(Takes effect next session.)

### 5. Connect Praxis

The factory's memory is **Praxis** — a separate knowledge-graph service, reached over its `praxis_*`
MCP tools. Installing this plugin does **not** install Praxis. You need:

**a. A running Praxis backend.** From the [Praxis repo](https://github.com/Antonelli-Tech-Solutions/praxis):

```bash
uv run --no-sync python -m knowledge.serve     # serves http://127.0.0.1:8000
```

`curl http://127.0.0.1:8000/health` should return `200`.

**b. The Praxis MCP, registered per project.** The MCP is configured per-repo in
`~/.claude.json`. A Praxis *identity/org* is pinned by a local cache file (`PRAXIS_MCP_CACHE`) —
**reuse the same cache across every repo that should share a plan**, so they're the same authenticated
user on the same org (don't create a fresh cache/org per repo — it'd be empty). Run, from each repo
that needs Praxis:

```bash
claude mcp add praxis -e PRAXIS_MCP_CACHE=/abs/path/to/your-cache.json -- \
  uv run --directory /abs/path/to/praxis python -m knowledge.mcp
```

**c. The right space.** In a session, verify before relying on it:
- `praxis_whoami` → authenticated, and your build org is the **active** org (`praxis_select_org <org>` if not).
- `praxis_list_snapshots` / `praxis_list_graph` → you actually see your project's snapshot + requirements.

> The factory runs in a dedicated Praxis org. Tenancy is single-principal, so projects are
> partitioned with **snapshots + read-only mounts**, not per-project user ids. All access flows
> through the `factory-memory` policy. See
> [docs/praxis-and-how-we-use-it.md](/docs/praxis-and-how-we-use-it.md).

---

## End-to-end walkthrough

Throughout, `<project>` is your project's slug (e.g. `team-app`); requirements are stored under
`source="prd-<project>"`. Paste the prompts into Claude Code with the plugin enabled and Praxis
connected. Run **attended** the first time (you answer the audit's questions and clear gates).

### Step 1 — Wireframe (optional but recommended)

`factory-wireframe` turns a PRD into complete, clickable HTML wireframes (split by persona, e.g. a
mobile player app + a web admin console), with a coverage gate that won't let it claim done until
every requirement + implied state maps to a screen.

> Build a complete, clickable HTML wireframe for the app described by the PRD in `docs/inspiration/`.
> Read every doc there. Cover the full MVP and post-MVP, split by user persona, mobile-responsive
> for the player app. Output to `wireframe-rebuild/`, and show me a coverage table.

### Step 2 — Plan (intake → plan → audit → plan-review)

This is one continuous, human-controlled phase that ends with a blessed `prd-<project>` snapshot.

> Run factory-intake to turn the prose PRD in `docs/inspiration/` plus the approved wireframes
> (`wireframe-rebuild/wireframe-player.html`, `wireframe-rebuild/wireframe-admin.html`) into the
> hardened `prd-<project>` requirement set in Praxis. Use **Rigorous** mode. Admit during ingestion
> with `source="prd-<project>"`, then run the factory-audit step and the plan-review before
> `save_snapshot`.

What happens, and where you're involved:
1. **factory-intake** extracts a candidate inventory from the PRD (behavior) + wireframe (surfaces),
   reconciles duplicates, and pauses at a **candidate review** (`.factory/requirement-candidates.json`).
2. **factory-plan** admits each requirement (`source="prd-<project>"` = the project identity;
   `meta.scope` = `mvp`/`post-mvp` tier; `meta.verify` = `automated`/`manual`). Large plans use the
   **raw bulk fast-lane** (`add_insights(raw=True)`) to avoid the per-item dedup that times out /
   over-merges; small edits keep live contradiction surfacing.
3. **factory-audit** runs an independent **cold-eyes** pass: adversarially challenges every
   requirement, routes underspecification (research / default / ask you / defer), forces a derived
   technical-architecture sweep **and a mandatory test strategy + CI**, and **reconciles** near-dup
   requirements in the graph. The **plan-audit gate** (`.factory/plan-audit.json`) blocks the
   snapshot until all of that is clean.
4. `save_snapshot("prd-<project>")` blesses the plan.
5. **factory-review (plan mode)** runs the compound-engineering panel over the *whole* plan
   (coherence / feasibility / scope / security / completeness). The **review gate**
   (`.factory/review-status.json`) blocks "planning done" until findings are resolved/accepted (or
   the review is skipped-with-reason for small work).

### Step 3 — Build (preflight → fan-out execute → deploy → work-review)

Run this in the **app repo**, in a session with Praxis pointed at the same org (so it sees the plan).

> Run factory-execute to build the app from the blessed `prd-<project>` snapshot into this repo.
> Preflight the environment first, build the MVP + automated-verify set (fan out in parallel), gate
> every slice via factory-verify, deploy to the techDecisions target, and run the work-review before
> shipping.

What happens:
1. **Preflight** — `factory-execute` derives the build's external dependencies from the plan's
   techDecisions (credentials, API keys, services, tooling) and checks each into
   `.factory/preflight.json`. The **preflight gate** blocks coding until every dep is present — if
   something's missing it tells you *exactly* what to provide; it never stubs a credential.
2. **Fan-out build** — each pass it computes the *buildable frontier* (the mvp+automated build set,
   dependencies satisfied) and **fans it out as parallel worktree-isolated builders via a Workflow**
   (not a serial queue). Each builder builds its slice, gates it through **factory-verify** (external
   signals only — tests / type-check / build), and on a verified pass records an outcome.
3. **Completeness gate** — "done" is mechanical: `praxis_incomplete_requirements(prd-<project>)`
   over the build set must be empty. The **build-completeness gate** (`.factory/build-status.json`)
   won't let the worker stop while anything's unbuilt. (Post-MVP and manual-verify requirements are
   excluded/deferred — never block the gate.)
4. **Deploy** — a **hard gate**: the plan isn't done until it's deployed and the deployment verified,
   unless you explicitly opt out (`deployment.required:false` + a reason).
5. **factory-review (work mode)** — the panel reviews the whole diff before "shipped".

> **Resuming:** completeness is outcome-grounded, so you can stop and restart a build any time —
> a fresh `factory-execute` re-queries `incomplete_requirements` and **resumes exactly where it left
> off** (only the not-yet-verified slices remain).

---

## The skills

Claude Code activates these from intent (or invoke by name, e.g. `factory-plan`):

| Skill | Role |
|---|---|
| **factory-wireframe** | One-shot PRD → complete, clickable HTML wireframes, self-audited coverage gate. |
| **factory-intake** | Extract a candidate-requirement inventory from PRD (behavior) + wireframe (surfaces); reconcile; hand to factory-plan. |
| **factory-plan** | Human-controlled plan hardening — admit requirements, surface contradictions, run the deterministic `plan_gate`. |
| **factory-audit** | The separate cold-eyes judgment audit — adversarial challenge, underspecification routing, technical + **test-strategy** sweep, near-dup reconciliation. |
| **factory-review** | The holistic cold-eyes **panel** (compound-engineering reviewers) at plan-finalization and build-finalization. |
| **factory-execute** | The build loop — preflight, fan-out build, verify, deploy. |
| **factory-verify** | The pass/fail gate `factory-execute` runs against **external** signals only. |
| **factory-memory** | The single policy surface for all Praxis reads/writes; used by the others. |

## The gates (`hooks/`)

Five Stop-hook forcing functions, each armed by a `<project>/.factory/*.json` manifest, fail-open,
loop-guarded, and **deferring while real subagents/workflows run** (via `_gate_common.py`):

| Gate | Enforces |
|---|---|
| `wireframe_gate.py` | Every requirement maps to a screen; no dead nav links. |
| `plan_audit_gate.py` | `plan_gate` clean + no open contradictions + every requirement challenged + tech decisions + **test strategy** complete. |
| `review_gate.py` | The cold-eyes panel ran and every finding is resolved/accepted (or skipped-with-reason). |
| `build_completeness_gate.py` | The mvp+automated build set is verified-complete **and deployed** (unless opted out). |
| `preflight_gate.py` | The build's derived environment dependencies are all provisioned before coding starts. |

## Key conventions

- **`source="prd-<project>"`** is the project identity (what the completeness query and the
  `R-HAS-SOURCE` gate filter on). It is **not** `meta.scope`, which is the `mvp`/`post-mvp` tier.
- **Build target = `mvp` + `automated`** (`src/agent_factory/build_target.py`); `post-mvp` and
  `manual` are excluded/deferred so the forced gate can't chase or trap on them.
- **Raw bulk inserts** (`add_insights(raw=True)`) for a whole-plan admission skip Praxis dedup; the
  intake reconcile + the audit's cold-eyes pass are the dedup/contradiction net there.

## Autonomous (overnight) mode

[CONSTITUTION.md](/CONSTITUTION.md) is the operating contract for **unattended** runs: it drives the
same plan → execute → verify loop with no human, records every owned decision as a Praxis episode,
defaults to **fanning out via Workflow** for substantial work, and treats the gates' attended pauses
as deferred owned-decisions for morning review. Read it before launching an overnight loop.

## Layout

```
.claude-plugin/                # plugin.json + marketplace.json (declares the CE dependency)
CONSTITUTION.md                # the autonomous-run operating contract
skills/                        # factory-wireframe / intake / plan / audit / review / execute / verify / memory
hooks/                         # the 5 Stop-hook gates + _gate_common (subagent deferral) + hooks.json
src/agent_factory/
  plan_gate.py                 # deterministic plan done-gate (acceptance / vague / dangling / source)
  build_target.py              # mvp+automated build-set selector
  gate.py                      # shared gate Verdict/Reason contract
  tabular.py                   # deterministic table linearizer (H6 ingestion shim)
  event_log.py                 # append-only run log
evals/cases/plan_gate/         # plan-gate eval cases
tests/                         # unit tests
docs/                          # vision, reference model, Praxis notes, plans
```

## Develop

```bash
uv run --with pytest pytest -q
```

See [docs/](/docs/) for the deeper picture — the
[vision](/docs/agent-factory-vision.md), the neutral
[reference model](/docs/agent-coding-factory-reference.md), and
[what we build here vs. what Praxis owns](/docs/factory-local-components.md).
