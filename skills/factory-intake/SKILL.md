---
name: factory-intake
description: >
  The extraction front-end that turns source material — prose PRD/spec docs AND a clickable
  wireframe — into a structured candidate-requirement inventory, then hands off to factory-plan
  for hardening. Use when starting a new project (or re-baselining one) from a PRD + wireframe and
  you need the hardened prd-<project> Praxis fact-set. It does NOT admit or gate the plan itself
  (factory-plan owns that); it produces the atomic candidates factory-plan consumes, and the
  surface<->requirement bindings the later wireframe->code step queries.
---

# Factory Intake (dual-source extraction)

Two inputs, one output. **Inputs:** the prose source docs (the behavioral truth — `docs/inspiration/`)
and the wireframe HTML (the surface truth + the completeness cross-check). **Output:** a structured
candidate-requirement inventory that `factory-plan` hardens into the `prd-<project>` Praxis snapshot.

The division of labor is deliberate:
- **Prose docs** are the source of record for *behavior* — rules, data model, acceptance criteria.
- **Wireframe** is the source of record for *surfaces* — screens, states, actions, navigation —
  and the **completeness cross-check** (it already enumerates the implied states: empty, offline,
  error, completed, fallback). It is **not** a second behavioral truth.
- This skill **extracts and reconciles**; `factory-plan` **admits, challenges, gates**. Don't
  duplicate hardening here.

All Praxis access follows **`factory-memory`**. This is a single decision-making agent that may use
the **read-only retrieval sub-agent** (`factory-execute` §1a) for bulk reading — never a crew.

## Step 0 — Read the sources (read-fully guard)

1. **Read the prose docs FULLY in your own context** (no limit/offset). They are the named source
   of behavioral truth — do not delegate them away. List the PRD folder; read every doc.
2. **Delegate the wireframe surface enumeration** to the read-only sub-agent. Wireframe HTML is
   large and mechanical; have the sub-agent return a compact **surface inventory** — one row per
   screen (`id="s-X"`), its title, the states it shows, and its inert actions (`go(...)`, button
   labels) — filtering ruthlessly. The parent never ingests the raw HTML.

## Step 1 — Extract candidates (two passes, then reconcile)

**Pass A — behavioral, from prose.** Atomize the rules. Your Dev-Ready Spec is already near-
structured (epics + explicit acceptance + data model + REST API), so this is *atomize + mint binary
conditions + dedupe across docs*, not invention. Over-generate; the gate filters.

**Pass B — surface, from the wireframe inventory.** Each screen, each state, each action becomes a
candidate. This is where the implied states we forced into the wireframe (offline / empty / invalid-
invite / completed / fallback) become first-class requirements instead of being forgotten.

**Reconcile.** Merge duplicates by *concept* (the same rule stated in the Dev-Spec and the
Requirements doc is ONE candidate with two citations) so you don't admit five near-duplicates and
lean entirely on Praxis dedup. Where prose and wireframe disagree, keep BOTH as candidates and let
factory-plan's contradiction queue settle it (e.g. wireframe shows a coach 1:1 inbox; prose says
post-MVP — surfaces as a pending pair, human tags scope).

### The candidate-record schema (the crux — everything downstream keys off this)

Emit the inventory to `<project>/.factory/requirement-candidates.json` (a local, reviewable,
diffable staging artifact — not the source of truth; the hardened snapshot is). One record:

```json
{
  "id": "R1",
  "statement": "completion = daily rep submitted AND all three ratings present; the habit checklist is recorded but never gates completion",
  "source": ["Requirements §3", "Dev-Spec Epic D", "wireframe-player.html#s-today"],
  "acceptance": "given a rep + effort/focus/support all set, status=complete; with the checklist left unchecked, status is still complete",
  "verify": "automated",
  "surfaces": ["s-today"],
  "defines": ["completion"],
  "references": ["daily rep", "ratings", "habit checklist"],
  "scope": "mvp",
  "project": "team-app"
}
```

Field rules:
- **`statement`** — ONE atomic behavior, written as a **single semicolon-joined sentence** (the
  Praxis sentence-fragmentation workaround — multi-sentence insights split per sentence; see
  CONSTITUTION §8). This is mandatory: emit the shape Praxis can admit whole.
- **`source`** — cite prose section/epic AND the wireframe screen(s); `file.html#s-X` form.
- **`acceptance`** — a draft binary condition ("when X, system does Y, observable via Z"). If the
  prose gives one, use it; if not, leave a best-draft and flag it for factory-plan's ambiguity forge.
- **`verify`** — `"automated"` (a command the loop runs: test/build/type-check/lint — the default)
  or `"manual"` (needs human confirmation: UX feel, a visual). Drives the C4 split downstream.
- **`surfaces`** — wireframe screen ids this requirement governs, or `["backend-only"]`. This is
  the seed of the surface<->requirement binding (Step 3).
- **`defines` / `references`** — concepts, for factory-plan's H14 dangling-reference gate.
- **`scope`** — `"mvp"` or `"post-mvp"` (the badged wireframe items). This is the **tier** tag only
  (`meta.scope`, read by `build_target.py`); it is NOT the project identity. Do not put the project
  name here.
- **`project`** — the project this candidate belongs to (e.g. `"team-app"`). This is the project
  identity: on handoff each candidate is admitted with **`source="prd-<project>"`** (here
  `source="prd-team-app"`), which is what the completeness query and the done-gate's `R-HAS-SOURCE`
  rule key off. Keep `project` distinct from `scope`; a candidate carrying only `scope` and no
  `project`/`source` is the generation drift the gate now rejects.

## Step 2 — Review gate (mode-aware), then hand off to factory-plan

Extraction is the **highest-leverage error point** (a bad requirement spawns thousands of bad
lines — see factory-plan's review-leverage note), and it deliberately over-generates, and admission
mutates the graph (facts + surface facts + edges) which is costly to unwind. So the candidate file
is a deliberate checkpoint **before** admission — but a *lightweight, high-signal* one, not a
line-by-line proofread (factory-plan does the deep per-requirement review next).

**Attended runs (default): pause and present a compact review surface** — not the raw JSON:
- counts by `source` and `scope` (e.g. "37 candidates: 31 mvp, 6 post-mvp");
- the **bidirectional coverage cross-check, computed here and cheaply** from the candidates' own
  `surfaces[]` vs the wireframe surface inventory: every wireframe surface that no candidate covers,
  and every `mvp` candidate with no surface (and no `backend-only`). This is the extraction-time
  preview of the graph-native `praxis_surface_coverage` gate (which runs post-admission, Step 2/3);
- a short **flagged list**: low-confidence / uncertain extractions, prose↔wireframe conflicts you
  spotted, and any record whose `acceptance` is still a placeholder.

The human eyeballs that, edits `requirement-candidates.json` directly if needed, and approves. Only
then do you continue into hardening. Don't admit anything before approval.

**Unattended runs (Constitution / owner asleep): do not pause** — there is no one to approve. Auto-
continue to hardening, `praxis_record_episode` ("intake: extracted N candidates, auto-admitted,
owner reviews AM" + the flagged list as alternatives/notes), and drop the candidate file + the
coverage cross-check + flagged list into the ledger for morning review. (Same attended/unattended
split as the C4 automated|manual gate.)

On approval (or unattended auto-continue), invoke **`factory-plan`** with the candidate inventory as
its input. factory-plan runs unchanged:
- Admit each record as a fact with `source="prd-<project>"`, `category="requirement"`, and
  `meta={requirement_id, surfaces, scope, verify}` — `statement` as the content, `acceptance` as the
  binary condition. **A whole fresh intake is a *bulk* admission** — hand it to factory-plan's **raw
  fast-lane** (`praxis_add_insights(insights=[...], raw=True)`, factory-plan Step 1 item 4), which
  skips Praxis dedup + the per-item conflict check (that times out on large batches and wrongly
  collapses near-duplicate requirements). **Intake's Step-1 Reconcile IS the dedup for this path** —
  raw trusts that you already merged duplicates by concept here — and the audit's cold-eyes pass is
  the contradiction net. (Incremental single-requirement edits later use `add_insight(...,
  on_conflict="surface")`.) **`source="prd-<project>"` (the candidate's `project`) is mandatory** —
  the project identity the completeness query and the `R-HAS-SOURCE` gate filter on, distinct from
  `meta.scope` (the mvp/post-mvp tier); a requirement admitted without `source` is rejected.
- Adversarial / gap lenses; contradiction queue (incl. the prose↔wireframe clashes you preserved).
- **H14, now bidirectional** (the completeness check intake exists to enable): once bindings are
  written (Step 3), **`praxis_surface_coverage(project, scope="mvp")`** is the graph-native gate —
  its `uncoveredSurfaces` (a screen with no backing requirement) and `uncoveredRequirements` (an MVP
  requirement with no screen) must both be empty, or each exception justified, before the done-gate
  clears.
- Then run **`factory-audit`** — the separate cold-eyes judgment pass (adversarial challenge +
  underspecification routing + cross-requirement gaps) over the admitted-but-not-yet-blessed set.
  Its Stop-hook gate blocks the snapshot until plan_gate passes, contradictions are empty, and every
  requirement is challenged-and-resolved. Admit *during* ingestion; audit + bless as this last step.
- Human clears the gate → `save_snapshot("prd-<project>")`.

## Step 3 — Persist the surface↔requirement binding (first-class `renders` relation)

The binding is a **first-class typed graph edge in Praxis** — `renders` (requirement fact → surface
fact) — not metadata. After factory-plan admits each requirement, persist its candidate `surfaces[]`:
- For each screen id, call **`praxis_bind_surface(requirement_fact_id, screen_id, project, title,
  file, states)`** — it ensures the surface fact (`category="surface"`, `scope=project`, idempotent
  on `screen_id`) AND adds the `renders` edge in one call. (`praxis_ensure_surface` exists if you
  ever need a surface without a binding.) A `backend-only` requirement gets no bind — it's reached
  by task/DAG dependency instead.

This edge is the queryable bridge the wireframe→code step uses: to build a screen it calls
**`praxis_requirements_for_surface(project, screen_id)`** and gets exactly the active requirement
facts governing that screen — a per-screen hermetic context (behavior from Praxis, layout from the
wireframe HTML in git). Rejecting or deleting a requirement drops it from these queries
automatically (active-only filtering + `ON DELETE CASCADE`); no `meta.surfaces` bookkeeping.

## Never
- Never treat the wireframe as a behavioral source of truth — behavior comes from the prose; the
  wireframe contributes surfaces, states, and the coverage cross-check.
- Never emit a multi-sentence `statement` — one semicolon-joined sentence (fragmentation workaround).
- Never admit or gate the plan here — that is factory-plan's job; intake only produces candidates.
- Never delegate the prose docs to a sub-agent — read the named behavioral source fully yourself;
  only the bulk wireframe HTML is delegated.
- Never let extraction's over-generation reach the snapshot unfiltered — the gate is the filter.
- Never admit candidates to Praxis before the attended review gate is cleared (Step 2). The
  candidate file is the cheap checkpoint; the graph is the expensive one to unwind.

## Compounding
When a correction reveals a class of miss (a requirement the prose stated but extraction dropped, a
wireframe state with no rule, a recurring prose↔wireframe clash), tighten the relevant pass above
and record a `factory-memory` learning so the next intake starts from a stricter extractor.
