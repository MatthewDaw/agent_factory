# Agent Factory

A Praxis-backed **agent factory** delivered as a Claude Code plugin: a single-agent
plan → execute → verify loop with compounding memory, coding-first behind a general
task + oracle seam.

- **Knowing system** → [Praxis](https://github.com/Antonelli-Tech-Solutions/praxis) knowledge graph (retrieval, dedup,
  contradiction handling, provenance), reached via the `praxis_*` MCP tools.
- **Doing system + glue** → this repo: skills that drive the loop, plus small
  deterministic helpers in `src/agent_factory/`.

See [docs/](/docs/) for the full picture:
- [docs/agent-factory-vision.md](/docs/agent-factory-vision.md) — the why.
- [docs/agent-coding-factory-reference.md](/docs/agent-coding-factory-reference.md) — neutral reference model.
- [docs/praxis-and-how-we-use-it.md](/docs/praxis-and-how-we-use-it.md) / [docs/praxis-gaps.md](/docs/praxis-gaps.md) — the substrate and its holes.
- [docs/factory-local-components.md](/docs/factory-local-components.md) — what we build here.
- [docs/brainstorms/2026-06-25-agent-factory-product-shape-requirements.md](/docs/brainstorms/2026-06-25-agent-factory-product-shape-requirements.md) — product shape.
- [docs/plans/2026-06-25-agent-factory-build-plan.md](/docs/plans/2026-06-25-agent-factory-build-plan.md) — the build plan (milestones M0–M5).

## Install

The factory ships as a Claude Code plugin. Install it from a local clone:

```bash
git clone https://github.com/MatthewDaw/agent_factory.git
```

Then, in Claude Code, register the clone as a plugin marketplace and install the plugin:

```
/plugin marketplace add ./agent_factory
/plugin install agent-factory@agent-factory-local
```

`/plugin marketplace add` accepts the path to your clone (the directory containing
[.claude-plugin/marketplace.json](/.claude-plugin/marketplace.json)). After installing,
run `/plugin` to confirm `agent-factory` is enabled.

## Prerequisite: Praxis

The factory's knowing system is **Praxis**, a separate knowledge-graph service reached
through its `praxis_*` MCP tools. Installing this plugin does **not** install or configure
Praxis — you need a running Praxis instance (local or hosted) and its MCP server registered
in your Claude Code config before the factory's memory operations will work.

For how to run Praxis and register its MCP server, follow the setup docs in the
**[Praxis repository](https://github.com/Antonelli-Tech-Solutions/praxis)**. See
[docs/praxis-and-how-we-use-it.md](/docs/praxis-and-how-we-use-it.md) for
how the factory connects (HTTP vs MCP, local vs prod backends) and the tenancy rules it
relies on.

## Dependency: compound-engineering (cold-eyes review panel)

The factory's holistic **cold-eyes review panel** (`skills/factory-review`) uses the
[compound-engineering](https://github.com/EveryInc/compound-engineering-plugin) plugin's reviewer
agents as its **default, required panel** — for both plan-review (coherence / feasibility / scope /
security / product / design lenses) and work-review (architecture / correctness / security /
maintainability / performance / testing). The factory's eval engine already leverages those
reviewers; this **formalizes** that reliance by declaring compound-engineering as a hard plugin
dependency, so Claude Code resolves and installs it automatically:

- [.claude-plugin/plugin.json](/.claude-plugin/plugin.json) and the
  [.claude-plugin/marketplace.json](/.claude-plugin/marketplace.json) entry declare
  `dependencies: [{ "name": "compound-engineering", "marketplace": "compound-engineering-plugin" }]`;
- the local marketplace allows the cross-marketplace pull via
  `allowCrossMarketplaceDependenciesOn: ["compound-engineering-plugin"]`.

Installing/enabling `agent-factory` auto-installs `compound-engineering`. If it is ever missing, the
review panel performs a **presence check** and **blocks the phase** (it never silently skips the
panel) until you install the dependency:

```
/plugin marketplace add EveryInc/compound-engineering-plugin
/plugin install compound-engineering@compound-engineering-plugin
```

## Usage

Once the plugin is installed and Praxis is reachable, Claude Code activates these skills
from intent — describe the task and the matching skill runs (you can also invoke one by
name, e.g. `factory-plan`):

- **factory-plan** — harden a PRD or rough idea into a self-consistent plan, saved as its
  own `prd-<project>` Praxis snapshot. Human-controlled: you clear the gate.
- **factory-execute** — build a task from that hardened plan: assemble context, do the
  work, gate it, and write confirmed learnings back.
- **factory-verify** — the pass/fail gate `factory-execute` runs against **external**
  signals only (tests, build, type-check, lint).
- **factory-memory** — the single policy surface for all Praxis reads/writes; used by the
  other skills, rarely invoked directly.
- **factory-wireframe** — standalone one-shot: turn a PRD into complete, clickable HTML
  wireframes with a self-audited coverage gate.

Typical flow: harden the plan with `factory-plan`, then run `factory-execute` against it.
For a quick visual from a spec, point `factory-wireframe` at a PRD.

## Layout

```
.claude-plugin/plugin.json     # Claude Code plugin manifest
skills/factory-memory/         # the "knowledge port" — Praxis access policy (M0)
src/agent_factory/
  event_log.py                 # append-only run log (the compounding spine)
  tabular.py                   # deterministic table linearizer (H6 ingestion shim)
tests/                         # unit tests for the helpers
```

## Memory backend

The factory runs in the dedicated `agent-factory` Praxis org. Tenancy is single-principal,
so projects are partitioned with **snapshots + read-only mounts**, not per-project user_ids.
All access flows through the `factory-memory` skill's policy.

## Develop

```bash
uv run --with pytest pytest -q
```
