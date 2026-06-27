---
name: factory-intake
description: >
  The extraction front-end that turns source material — prose PRD/spec docs AND a clickable
  wireframe — into candidate requirements and surface↔requirement bindings WRITTEN DIRECTLY INTO
  PRAXIS, then hands off to factory-plan for hardening. Use when starting a new project (or
  re-baselining one) from a PRD + wireframe and you need the hardened prd-<project> Praxis fact-set.
  It does NOT admit-as-blessed or gate the plan (factory-plan + factory-audit own that); it produces
  the atomic candidate facts factory-plan hardens and the surface↔requirement `renders` edges the
  later wireframe→code step queries.
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

In this skill: intake runs UPSTREAM of the build loop — it MINTS the tickets the loop later FINDs.
It extracts candidate requirements from prose + wireframe and writes them as Praxis facts (each carrying
identity — tags, surfaces, semantics — but NEVER an authored check list), plus the surface↔requirement
`renders` bindings the RESOLVE step and the wireframe→code build query read. It records no build/claim/
pass state and writes no JSON; factory-plan + factory-audit harden what intake produces.

# Factory Intake (dual-source extraction → Praxis)

Two inputs, one store. **Inputs:** the prose source docs (the behavioral truth — `docs/inspiration/`)
and the wireframe HTML (the surface truth + the completeness cross-check). **Output:** candidate
requirement facts and `renders` bindings **live in Praxis**, which `factory-plan` then hardens and
`factory-audit` blesses into the `prd-<project>` snapshot.

**Praxis is the single source of dynamic truth and a HARD dependency.** Everything intake produces is
written to Praxis — there is no local staging manifest, no `.factory/*.json` file. If Praxis is
unreachable, intake CRASHES AND STOPS (fail-closed); it never writes work to a side file and never
proceeds as if the writes landed.

The division of labor is deliberate:
- **Prose docs** are the source of record for *behavior* — rules, data model, acceptance criteria.
- **Wireframe** is the source of record for *surfaces* — screens, states, actions, navigation —
  and the **completeness cross-check** (it already enumerates the implied states: empty, offline,
  error, completed, fallback). It is **not** a second behavioral truth.
- This skill **extracts, reconciles, and writes candidate facts to Praxis**; `factory-plan` +
  `factory-audit` **challenge, gate, and bless**. Don't duplicate hardening here.

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
conditions + dedupe across docs*, not invention. Over-generate; the plan/audit gates are the filter.

**Pass B — surface, from the wireframe inventory.** Each screen, each state, each action becomes a
candidate. This is where the implied states we forced into the wireframe (offline / empty / invalid-
invite / completed / fallback) become first-class requirements instead of being forgotten.

**Reconcile.** Merge duplicates by *concept* (the same rule stated in the Dev-Spec and the
Requirements doc is ONE candidate with two citations) so you don't admit five near-duplicates and
lean entirely on Praxis dedup. Where prose and wireframe disagree, keep BOTH as candidates and let
factory-audit's contradiction pass settle it (e.g. wireframe shows a coach 1:1 inbox; prose says
post-MVP — surfaces as a pending pair, human tags scope).

### The candidate shape (a Praxis fact, not a file record)

Each candidate is admitted **directly to Praxis** as a fact. There is NO `requirement-candidates.json`
staging file — Praxis *is* the staging store as well as the source of truth. The conceptual shape of
one candidate (the insight you hand to the admission call in Step 2):

```jsonc
{
  // `statement` → the fact content (ONE atomic behavior, single semicolon-joined sentence)
  "content": "completion = daily rep submitted AND all three ratings present; the habit checklist is recorded but never gates completion",
  "category": "requirement",
  "source": "prd-team-app",          // PROJECT IDENTITY — mandatory; see field rules
  "meta": {
    "acceptance": "given a rep + effort/focus/support all set, status=complete; with the checklist left unchecked, status is still complete",
    "verify": "automated",            // or "manual"
    "surfaces": ["s-today"],          // wireframe screen ids, or ["backend-only"]
    "defines": ["completion"],
    "references": ["daily rep", "ratings", "habit checklist"],
    "scope": "mvp",                   // mvp | post-mvp — the TIER tag, not the project
    "citations": ["Requirements §3", "Dev-Spec Epic D", "wireframe-player.html#s-today"],
    "tags": ["completion", "today-screen"]   // identity tags; check applicability queries against these later
  }
}
```

Field rules:
- **`content` (the statement)** — ONE atomic behavior, written as a **single semicolon-joined
  sentence** (the Praxis sentence-fragmentation workaround — multi-sentence insights split per
  sentence; see CONSTITUTION §8). Mandatory: emit the shape Praxis can admit whole.
- **`source`** — `"prd-<project>"` (here `prd-team-app`). This is the **project identity** the
  completeness query and the done-gate's `R-HAS-SOURCE` rule key off. **Mandatory** — a candidate
  admitted without `source` is rejected. Keep it distinct from `meta.scope` (the mvp/post-mvp tier).
- **`meta.citations`** — cite prose section/epic AND the wireframe screen(s); `file.html#s-X` form.
  (Prose provenance lives in meta; the Praxis `source` field is reserved for project identity.)
- **`meta.acceptance`** — a draft binary condition ("when X, system does Y, observable via Z"). If
  the prose gives one, use it; if not, leave a best-draft and flag it for factory-plan's ambiguity
  forge.
- **`meta.verify`** — `"automated"` (a command the loop runs: test/build/type-check/lint — the
  default) or `"manual"` (needs human confirmation: UX feel, a visual). Drives the C4 split downstream.
- **`meta.surfaces`** — wireframe screen ids this requirement governs, or `["backend-only"]`. Seeds
  the `renders` bindings written in Step 3.
- **`meta.defines` / `meta.references`** — concepts, for factory-plan's H14 dangling-reference gate.
- **`meta.scope`** — `"mvp"` or `"post-mvp"` (the badged wireframe items). The tier tag only; it is
  NOT the project identity. Do not put the project name here.
- **`meta.tags`** — identity tags (concepts / surfaces / semantics) carried by the requirement. A
  ticket carries identity, NEVER an authored list of its checks; later, *which checks apply* is a
  fresh query (tag ∪ surface) resolved at build time. Tag honestly so that query resolves correctly.

## Step 2 — Write candidates to Praxis, then review, then hand off

Extraction is the **highest-leverage error point** (a bad requirement spawns thousands of bad lines —
see factory-plan's review-leverage note), and it deliberately over-generates. So there is a review
checkpoint — but it reviews the **live Praxis fact-set**, not a JSON file.

**Admit the whole batch to Praxis.** A fresh intake is a *bulk* admission — hand it to factory-plan's
**raw fast-lane** (`praxis_add_insights(insights=[...], raw=True)`), which skips Praxis dedup + the
per-item conflict check (that times out on large batches and wrongly collapses near-duplicate
requirements). **Intake's Step-1 Reconcile IS the dedup for this path** — raw trusts that you already
merged duplicates by concept here — and factory-audit's cold-eyes pass is the contradiction net.
(Incremental single-requirement edits later use `add_insight(..., on_conflict="surface")`.) Every
record MUST carry `source="prd-<project>"`; one without it is the generation drift the gate rejects.

**Attended runs (default): present a compact review surface computed from Praxis** — not raw facts:
- counts by `source` and `meta.scope` (e.g. "37 candidates: 31 mvp, 6 post-mvp"), via `facts_by`;
- the **bidirectional coverage cross-check** — once the Step-3 bindings exist, run
  `praxis_surface_coverage(project, scope="mvp")`: every wireframe surface with no backing
  requirement (`uncoveredSurfaces`) and every `mvp` requirement with no surface and no
  `backend-only` (`uncoveredRequirements`);
- a short **flagged list**: low-confidence extractions, prose↔wireframe conflicts you preserved, and
  any record whose `meta.acceptance` is still a placeholder.

The human eyeballs that and, if a candidate is wrong, **edits the fact in Praxis directly**
(`praxis_edit_fact` / `praxis_reject_fact`) — Praxis is the only store, so corrections happen there,
not in a side file. On approval, continue to hardening.

**Unattended runs (Constitution / owner asleep): do not pause** — there is no one to approve. The
candidates are already in Praxis; record a `praxis_record_episode` ("intake: extracted N candidates,
auto-admitted, owner reviews AM" + the flagged list as alternatives/notes) so morning review has the
counts, the coverage cross-check, and the flagged list — all queried back from Praxis, no file.

**Hand off to `factory-plan`** (which reads the candidate facts live from Praxis):
- Adversarial / gap lenses; contradiction queue (incl. the prose↔wireframe clashes you preserved).
- **H14, bidirectional** — `praxis_surface_coverage(project, scope="mvp")` must come back with both
  `uncoveredSurfaces` and `uncoveredRequirements` empty (or each exception justified) before the gate
  clears.
- Then **`factory-audit`** — the cold-eyes judgment pass (adversarial challenge + underspecification
  routing + cross-requirement gaps + forced architecture decisions) over the admitted-but-not-yet-
  blessed set. Planning is **human-gated** (the one Stop hook is build-completeness, for the build
  phase): the human blesses only once `plan_gate` passes, contradictions are empty, every requirement
  is challenged-and-resolved, and a panel-ran episode exists — all live from Praxis, no manifest file.
- Human clears the gate → `save_snapshot("prd-<project>")`.

## Step 3 — Persist the surface↔requirement binding (first-class `renders` relation)

The binding is a **first-class typed graph edge in Praxis** — `renders` (requirement fact → surface
fact) — not metadata, and not a file. After the candidates are admitted, persist each candidate's
`meta.surfaces`:
- For each screen id, call **`praxis_bind_surface(requirement_fact_id, screen_id, project, title,
  file, states)`** — it ensures the surface fact (`category="surface"`, `scope=project`, idempotent
  on `screen_id`) AND adds the `renders` edge in one call. (`praxis_ensure_surface` exists if you
  ever need a surface without a binding.) A `backend-only` requirement gets no bind — it's reached
  by task/DAG dependency instead.

This edge is the queryable bridge the wireframe→code step uses: to build a screen it calls
**`praxis_requirements_for_surface(project, screen_id)`** and gets exactly the active requirement
facts governing that screen — a per-screen hermetic context (behavior from Praxis, layout from the
wireframe HTML in git). Rejecting or deleting a requirement drops it from these queries
automatically (active-only filtering + `ON DELETE CASCADE`); no `meta.surfaces` bookkeeping to sync.

## Never
- Never write a `.factory/*.json` candidate manifest (or any local build/validation state file).
  Candidates and bindings live in Praxis — the single source of dynamic truth. JSON is static config
  only.
- Never proceed if Praxis is unreachable — fail closed: crash and stop. Do not buffer work to a file.
- Never treat the wireframe as a behavioral source of truth — behavior comes from the prose; the
  wireframe contributes surfaces, states, and the coverage cross-check.
- Never emit a multi-sentence `content`/statement — one semicolon-joined sentence (fragmentation
  workaround).
- Never author a list of checks onto a candidate — a candidate carries identity (tags, surfaces,
  semantics); which checks apply is a fresh query resolved later at build time, never pre-bound here.
- Never admit a candidate without `source="prd-<project>"` — that is the project identity the
  completeness query and the `R-HAS-SOURCE` gate filter on.
- Never bless or snapshot the plan here — that is factory-plan + factory-audit's job; intake only
  produces candidate facts and bindings.
- Never delegate the prose docs to a sub-agent — read the named behavioral source fully yourself;
  only the bulk wireframe HTML is delegated.

## Compounding
When a correction reveals a class of miss (a requirement the prose stated but extraction dropped, a
wireframe state with no rule, a recurring prose↔wireframe clash), tighten the relevant pass above
and record a `factory-memory` learning so the next intake starts from a stricter extractor.
