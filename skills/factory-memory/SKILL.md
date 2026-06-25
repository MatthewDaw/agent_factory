---
name: factory-memory
description: >
  The single policy surface for all Praxis knowledge-graph access in the agent factory
  (the "knowledge port" as policy). Use whenever the factory reads from or writes to
  Praxis memory — seeding a project, retrieving grounding context, writing back a
  learning, or ingesting a document/table. Encodes which MCP tool to use, the
  tabular ingestion-integrity audit, tenancy via snapshots/mounts, and write-back rules.
---

# Factory Memory Policy

All durable knowledge lives in **Praxis**, reached through its MCP tools (`praxis_*`).
Code lives in git; ephemeral run state lives in the local event log. Only judgments,
decisions, and learnings *about* the work go to Praxis. **Every Praxis read/write also
gets an event-log entry** (`memory_read` / `memory_write` / `memory_audit`).

This skill is the one place that decides *how* the factory touches memory. Other skills
call these rules; they do not call `praxis_*` with their own ad-hoc conventions.

## 0. Always confirm tenancy first

The factory operates **only** in the `agent-factory` org. Before any memory operation in
a fresh session, run `praxis_whoami`; if the active org is not `agent-factory`, run
`praxis_select_org("agent-factory")`. Never write factory knowledge into the `praxis`
org (it holds unrelated test data).

- **General pool** = the org's **live graph** (cross-project conventions and learnings).
- **Project pool** = a **snapshot** (`praxis_save_snapshot`), **mounted read-only**
  (`praxis_mount_snapshot`) while working so retrieval composes general + project without
  merging the project into the live graph. Single-principal tenancy means there is **no**
  per-project user_id — snapshots and mounts are the partition primitive.

## 1. Choose the write path

| Input | Tool | Why |
|---|---|---|
| A shaped, already-true atomic fact (a chosen library, a confirmed fix, a convention) | `praxis_add_insight` | Fast, synchronous, low-loss; runs dedup/merge/contradiction. |
| Raw unstructured prose we have not digested | `praxis_ingest` | Server-side distillation. Slow/async — keep it off the critical path. |
| **Tabular / templated input** (tables, row-per-field specs, `key: value` blocks) | **Linearize first, then `praxis_add_insight` per row** | Distillation silently under-emits on tables (gap H6). **Never raw-`ingest` a table.** |
| A raw record that must bypass the pipeline for review | `praxis_insert_fact` | Lands in `proposed`; special cases only. |

Prefer shaping facts and using `add_insight` over `ingest` wherever practical — it avoids
both the latency and the distillation loss.

## 2. Tabular ingestion integrity (the H6 audit) — REQUIRED on any table/bulk write

Loss happens at two points: distillation under-emits rows (A), and the deduper over-merges
siblings (B). A is shimmed locally; B is server-side and can only be *caught*, not prevented.

1. **Linearize** tabular input with `agent_factory.tabular.linearize` → atomic,
   lexically-distinct fact sentences (one per row/cell, row+column identity folded in).
   Route the result's `residual_prose` to `praxis_ingest` and each `fact` to `add_insight`.
2. **Write** each linearized fact via `praxis_add_insight`.
3. **Audit the rejected pile.** After the batch, run `praxis_list_graph(state="rejected")`.
   For every row that is a genuinely distinct requirement but was dropped/merged, re-add it
   with more distinctive phrasing (add more of the row's columns into the sentence). Record
   the audit as a `memory_audit` event with counts: `{rows_submitted, active, rejected}`.
4. **Do not trust** a tabular write until `active + legitimately-merged + rejected` accounts
   for every submitted row.

> Known live example: a standard-deduction table left the "Married filing jointly" row in
> `rejected` while its siblings stayed `active`. Always audit.

## 3. Retrieve for grounding

- Use `praxis_get_context(query, top_k)` for task grounding. Mount the relevant project
  snapshot first so general + project facts compose in one ranked result.
- **Cite provenance.** Every decision the agent makes should name the Praxis fact(s) that
  grounded it (the hit's `source`/`score`), logged on the `decision` event.
- Retrieval returns only currently-valid `active` facts. To reconstruct what was believed at
  a past point, pass an `as_of` timestamp (used by reproducible runs in M2).

## 4. Write-back policy (compounding)

- **Only write a learning that an external signal confirmed** — a passing test/build for
  coding, or human approval for non-coding. Never write speculative "this probably works"
  facts; that poisons the pool.
- Promote a project-pool learning into the **general pool** only when it generalizes beyond
  the one project.
- On a write, if Praxis flags a **contradiction**, do not force it through silently — inspect
  with `praxis_get_contradictions` and settle with `praxis_resolve_contradiction` (keep one
  side or supply reconciled text). Record the resolution as a `decision` event.
- Attach outcome context from the event log so future milestones can weight facts by how they
  fared (local stand-in for Praxis gaps H1/H4/H5).

## 5. Never

- Never write code or ephemeral session state into Praxis.
- Never operate in the `praxis` org.
- Never raw-`ingest` tabular input.
- Never write an unverified learning back to the pool.
