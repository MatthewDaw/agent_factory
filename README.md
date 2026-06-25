# Agent Factory

A Praxis-backed **agent factory** delivered as a Claude Code plugin: a single-agent
plan → execute → verify loop with compounding memory, coding-first behind a general
task + oracle seam.

- **Knowing system** → [Praxis](../praxis) knowledge graph (retrieval, dedup,
  contradiction handling, provenance), reached via the `praxis_*` MCP tools.
- **Doing system + glue** → this repo: skills that drive the loop, plus small
  deterministic helpers in `src/agent_factory/`.

See `docs/` for the full picture:
- `docs/agent-factory-vision.md` — the why.
- `docs/agent-coding-factory-reference.md` — neutral reference model.
- `docs/praxis-and-how-we-use-it.md` / `docs/praxis-gaps.md` — the substrate and its holes.
- `docs/factory-local-components.md` — what we build here.
- `docs/brainstorms/2026-06-25-agent-factory-product-shape-requirements.md` — product shape.
- `docs/plans/2026-06-25-agent-factory-build-plan.md` — the build plan (milestones M0–M5).

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
