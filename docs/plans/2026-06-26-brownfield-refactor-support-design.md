# Brownfield / Refactor Support — Hardened Design & Build Plan

**Status:** design blessed in planning session 2026-06-26. Ready for an implementation session.
**Scope of this doc:** the new/changed pieces, how each reuses/extends the existing spine, the new gates, the Praxis vocabulary, resolved decisions with rationale, risks, and a sequenced build plan. **No production code was written this session.**

---

## 0. Core principle (the spine this all hangs on)

The factory's own method applied to the factory: **heavy planning → exhaustive verification → insert the verified plan into Praxis, such that NO decision remains for execution.** Execution is a mechanical reducer: read next buildable frontier from Praxis → apply → `factory-verify` → `record_outcome`. Brownfield is therefore **~80% a planning-surface problem, ~20% an execution problem.**

**Praxis is the substrate, not storage.** The transformation is *computed on the graph*. We reuse Praxis's existing dedup + contradiction/conflict-resolution machinery rather than building new comparison logic.

### The one reframe: ONE unified spine

There is no separate brownfield pipeline. **Every build is a transformation from a current state `S0` + a goal → a target state `S1`. Greenfield is the degenerate case where `S0` is empty.** Brownfield activates stages that *no-op on empty `S0`*. The factory branches on **data, not orchestration**, via a new requirement field:

```
meta.kind ∈ { feature | preserve | change | migrate | cutover }
```

Gates and audit read `meta.kind`. There is no second codebase to drift. Test for any proposed brownfield-only code: *"why isn't this the empty-`S0` case of an existing stage?"*

---

## 1. Resolved decisions (owner sign-off 2026-06-26)

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| D1 | Architecture | **Unified spine** (greenfield = empty `S0`) | Keeps proven gates/Praxis/review intact; no pipeline fork to drift. |
| D2 | `factory-understand` | **Separate skill, in the wireframe slot** | Its output is a durable, gate-recomputable, reusable Praxis asset with a different lifetime than intake's staging file. The wireframe's real job (human-reviewable "what binds to what," blessed before code) generalizes to a **seam/dependency diagram**. |
| D3 | PRESERVE → "complete" | **Characterization-first; counts via existing outcome machinery** | Auto-synthesized golden-master/characterization tests are admitted as ordinary requirements (`meta.kind="preserve"`, binary acceptance = "suite green"); `factory-verify` → `record_outcome("succeeded")`. A broken one becomes `regressed` — that *is* the no-regression signal. |
| D4 | Oracle trust | **Mutation-gate with graceful degradation** | Existing suite is a *candidate* oracle, not trusted. A new `oracle_gate` runs mutation testing per touched seam; where tooling is absent, record explicit lower **oracle confidence** + accept-with-reason instead of silently passing. |
| D5 | Gate machinery | **Reuse + 3 new gates** (`understand_gate`, `oracle_gate`, `keep_green_gate`); extend `build_target`, `build_completeness_gate`, `plan_audit_gate` | Most refactor needs are already modeled (never-built/regressed/stale). Only oracle-trust and keep-green are genuinely new checks. |
| D6 | Coupled slices | **Parallelism is an OUTPUT of decoupling** | Dependency-ordered "green spine" of anchored pitches (Branch-by-Abstraction / Parallel-Change); inject BBA seams as their own requirements; only genuinely independent slices fan out. Mechanical mass edits → one deterministic **codemod**, not N LLM slices. |
| D7 | Cutover | **Factory AUTHORS, human/CD EXECUTES** | Auto-expand `migrate|cutover` goals into the staged ladder + paired *exercised* rollback as gated requirements; verify everything in-repo (reconciliation tests, flag wiring, rollback against local/staging); hand live production flips to a human. Honest about the infra boundary. |
| D8 | Ingest scope | **Goal blast-radius only** (with dependency-graph expansion guard) | Avoids stressing Praxis with whole-repo write bursts (known concurrent-write 500s); keeps the contradiction set tractable. Under-scoping mitigated by expanding along the dependency graph. |
| D9 | Reconciliation | **Praxis contradiction machinery** | Feed current-state facts + goal requirements into Praxis; existing pending-pair machinery surfaces every delta, resolved human-gated via `resolve_contradiction` during planning. **Constraint:** current-state facts must be written **claim-shaped** so contradictions actually fire (see §4). |
| D10 | First-build "done" | **Exhaustive plan-in-Praxis as a gated milestone, THEN decision-free execute** | Bless a fully decision-closed plan (understand + reconcile + audit closing ALL execution decisions incl. cutover ladder/thresholds/rollback) as its own milestone; then execute. Matches the dev process; localizes failure. |
| D11 | Generality validation | **sotos + `../team-app`** | Validate against sotos (AWS/TS/Nx, auth→Cognito) AND `../team-app` (the app the factory itself built) so nothing about sotos leaks into the design and we exercise refactoring a factory-built codebase. sotos is illustration only; may be read read-only. |
| D12 | Closed-loop lesson capture | **Mandatory, gate-enforced** | When the factory fixes/improves something — especially something it implemented wrong the first time — the lesson MUST be written to Praxis as a learning so the system remembers and future builds avoid the same mistake. Enforced by `lesson_gate` (§3.10). Applies to the whole unified spine, not just brownfield. |
| D13 | Lessons must be PROVEN by evals | **Each generalized lesson spawns an eval case** | Recording a lesson is necessary but not sufficient; as knowledge accumulates we must *prove* the coding agents won't repeat the mistake — across any surface (validation, planning, understand, audit, execute). Each promoted lesson is paired with a surface-agnostic eval case that reproduces the mistake-prone situation and asserts correct behavior; CI runs the suite (§3.11). |

---

## 2. Pipeline (brownfield path; greenfield = the empty-`S0` walk of the same stages)

```
existing repo + goal
  └─ factory-understand        [NEW skill; wireframe slot]  → current-state facts (blast-radius) + seam/dep diagram
        gate: understand_gate  (citations resolve to real file:line; blast-radius covers the goal)
  └─ characterization capture  [within understand or its own step] → preserve requirements (golden-master)
        gate: oracle_gate      (mutation score per seam ≥ threshold, OR recorded confidence + accept-with-reason)
  └─ factory-intake[brownfield]  → feed current-state + goal to Praxis; contradictions = deltas; classify meta.kind
  └─ factory-plan              [REUSE]  → admit/harden requirements (incl. preserve/change/migrate/cutover)
  └─ factory-audit             [REUSE + extended]  → close ALL execution decisions (blast radius, slice order,
        gate: plan_audit_gate           seam insertions, cutover ladder+thresholds, rollback, MEL, oracle gaps)
  └─ factory-review (PLAN)     [REUSE]  → cold-eyes panel
  ════════════════════════ "EXHAUSTIVE PLAN BLESSED" milestone (D10) ════════════════════════
  └─ factory-execute[refactor] [REUSE + extended]  → DECISION-FREE reducer:
        - dependency-ordered green spine of anchored pitches; independent slices fan out
        - BBA seam injection (already a requirement); codemod path for mechanical mass edits
        - each slice verify INCLUDES the preserve suite for its blast radius
        gates: keep_green_gate (every anchor commit builds/deploys-green),
               build_completeness_gate (extended: preserve/regression + staged-cutover terminal)
  └─ deploy / staged cutover   → author-verifiable portion of the cutover ledger; live flips handed off (D7)
  └─ factory-review (WORK)     [REUSE]  → cold-eyes panel
  └─ SHIPPED
```

---

## 3. New / changed components

### 3.1 NEW skill: `factory-understand` (wireframe slot)
- **Produces:** blast-radius current-state facts in Praxis (`source="map-<project>"`, `category="structure"`/`"current-state"`), each with `file:line` citations; a dependency/call graph; seams; surface bindings to *existing* code; a human-reviewable **seam/dependency diagram** (the brownfield analog of the wireframe).
- **Scope (D8):** only code the goal could touch, expanded along the dependency graph until closure; whole-repo ingestion explicitly avoided.
- **Degradation ladder:** structural (AST / language-server / tree-sitter repo-map) → **black-box** (execution traces, I/O probes) when no parser exists for the stack. Keeps it general; the chosen mode is recorded.
- **NEW gate `understand_gate`:** recomputes that every cited `file:line` resolves to real code and that the blast radius covers the goal's stated surface. No agent say-so.

### 3.2 Characterization + oracle trust
- Over the blast radius, **auto-synthesize characterization / golden-master tests** capturing *current* behavior; admit as `meta.kind="preserve"`, `meta.verify="automated"`, binary acceptance = *"characterization suite X green."*
- **NEW gate `oracle_gate`:** mutation-test the candidate suite per touched seam; block `preserve` requirements from *counting* until mutation score clears threshold. **Degradation (D4):** where mutation tooling is unavailable, record explicit lower **oracle confidence** + require accept-with-reason, never silent pass. Surviving-mutant gaps are written back as new `preserve` requirements to auto-strengthen.
- **Mystery-behavior quarantine:** behavior that looks like a latent bug (dead branches, swallowed errors, suspicious constants) is tagged `pinned-but-questioned` and routed to the human — *preserve or fix?* — so the factory doesn't canonize bugs and then block itself defending them.

### 3.3 `factory-intake[brownfield]` (mode of existing skill)
- Feeds current-state facts + goal into Praxis; **contradictions are the deltas** (D9). Agreement → preserve; contradiction → change/migrate, resolved during planning. Classifies each resulting requirement's `meta.kind`.
- **Implementation constraint:** current-state facts must be **claim-shaped** (subject/attribute/value) so Praxis's structural contradiction detector fires against goal requirements. This is the load-bearing detail of the reconciliation choice.

### 3.4 REUSED unchanged: `factory-plan`, `factory-review` (plan + work)

### 3.5 `factory-audit` (extended — the exhaustive decision-closing surface)
Brownfield adds **mandatory closed decision classes** to `plan-audit.json` (same "every challenge closed" gate, new required items):
- blast-radius is closed/justified;
- slice **dependency order** is closed;
- **Branch-by-Abstraction seam insertion points** chosen;
- **cutover ladder** stages + **metric thresholds** + **rollback procedure** specified (for `migrate|cutover`);
- **minimum-equipment-list**: which capabilities may be temporarily degraded mid-refactor + required compensating control;
- **oracle confidence / accepted gaps** recorded.
By bless time the graph fully specifies the transformation.

### 3.6 `factory-execute[refactor]` (extended — decision-free reducer)
- **Dependency-ordered green spine** of anchored pitches; each pitch ends at a named, independently-green, deployable anchor commit (BBA / Parallel-Change). Only genuinely independent slices fan out to parallel worktrees.
- **BBA seam injection:** where coupling blocks green, the injected seam is already a requirement (from audit) — decouple first, then the two sides are independent slices.
- **Codemod path:** mechanical mass edits (e.g. a 1000-site signature change) become one deterministic codemod, sample-verified and applied atomically, recorded as a single fact + outcome.
- Each slice's `factory-verify` runs the **full preserve suite for its blast radius**.
- **NEW gate `keep_green_gate`:** every anchor commit must build/deploy-green (tolerates only *declared* MEL degradations with their compensating control; grounds undeclared breakage).
- **`deploy` hard-gate generalized:** "deployed+verified" becomes "cutover ledger advanced to its declared **author-verifiable** terminal stage AND old path removed (or explicitly retained with reason)." A refactor's end state is *not* "deploy succeeded once."

### 3.7 Cutover ladder (for `meta.kind ∈ {migrate, cutover}`)
Auto-expand a single "replace X with Y" goal into child requirements: `expand → dual-write → shadow → live → ramp-down → contract`, each with a **metric-gated binary acceptance** and a **paired rollback requirement that must be exercised** (flip forward, flip back, confirm parity) to count complete. A **double-entry reconciliation ledger** provides the provable equivalence signal during shadow/live. Per D7, the factory authors + verifies the in-repo portion; live production flips are handed off.

### 3.8 Praxis vocabulary (NO Praxis code changes — all free-form, confirmed in the Praxis map)
- `source="map-<project>"`, `category="structure"`/`"current-state"` (claim-shaped).
- `meta.kind` on requirements.
- cutover-ledger facts; preserve requirements; `meta.degradable=true` + `meta.compensating_control` for MEL items.
- **Compounding:** seam learnings promoted to the read-only `general-pool` snapshot (repo B benefits from repo A); completed cutovers recorded as outcome-scored **recipes** (with rollback scars) the next migration instantiates; the same current-state map serves both refactor and greenfield feature-adds on the app.

### 3.9 Gate summary
| Gate | New/changed | Checks |
|------|-------------|--------|
| `understand_gate` | NEW | cited `file:line` resolve; blast-radius covers goal |
| `oracle_gate` | NEW | mutation score per seam ≥ threshold OR recorded confidence + accept-with-reason |
| `keep_green_gate` | NEW | each anchor commit builds/deploys-green; only declared MEL degradations allowed |
| `plan_audit_gate` | EXTENDED | brownfield decision classes all closed (§3.5) |
| `build_target` | EXTENDED | partition on `meta.kind` (preserve/change/migrate alongside scope/verify) |
| `build_completeness_gate` | EXTENDED | preserve/regression counted; staged-cutover terminal as deploy condition |
| `lesson_gate` | NEW | every requirement whose outcome history contains a failure has an associated lesson fact (`derived_from`) before ship (§3.10) |

### 3.10 Closed-loop lesson capture (failure memory) — D12
**Hard requirement:** whenever the factory fixes or improves something — most importantly something it implemented **wrong the first time** — it must persist the lesson to Praxis so the system *remembers it failed and why*, and future builds (any project) avoid repeating it. This is the factory compounding on its own mistakes.

Mechanism (reuses existing Praxis machinery; no new Praxis code):
- On a failed verify then a passing one, the outcome history already carries `record_outcome("failed")` → `record_outcome("succeeded")`. That history is the *trigger*.
- A **lesson fact** is then written: `category="learning"`, `derived_from=[requirement_id, failing_outcome]`, text capturing **what the wrong first implementation did, why it was wrong, and the correct approach** (claim-shaped so it's retrievable and contradiction-checkable).
- Generalizable lessons are **promoted to the read-only `general-pool` snapshot** so repo B inherits repo A's scar (and greenfield builds inherit refactor scars).
- **NEW gate `lesson_gate`:** the build cannot ship while any requirement has a failure in its outcome history but no associated lesson fact. Forcing-function-backed, consistent with the factory's "evidence, not say-so" philosophy. Fail-open + loop-guarded like the other gates.
- The retrieval side closes the loop: `factory-understand` / hermetic-context assembly queries these lessons for the blast radius, so a relevant past failure is *in context* before the agent writes code.

This generalizes the existing learnings/`derived_from`/`record_outcome` pattern from "optional good practice" to a **gated, mandatory** step for anything that needed fixing.

### 3.11 Lessons → evals: prove the mistake won't recur — D13
A recorded lesson (§3.10) changes *retrieval*; an **eval** proves it changed *behavior*. As the `general-pool` accumulates lessons, we accumulate a regression suite that proves the coding agents won't repeat past mistakes — **whatever surface the mistake occurred on: validation, planning, understanding, audit, or execution.**

Lifecycle of an **eval-backed lesson**:
1. **Recorded** — lesson fact written on a failure→fix (§3.10).
2. **Generalized** — promoted to `general-pool` when not project-specific.
3. **Eval-encoded** — a paired **eval case** is authored that reproduces the mistake-prone situation and asserts the now-correct behavior. The case names its **surface** so it runs against the right harness:
   - *planning/validation* → extends the existing deterministic-gate eval harness (`evals/cases/plan_gate/*` today) to other gates;
   - *understand/audit/execute* → a scenario fixture (a seeded mini-repo or recorded context) + an asserted outcome (gate verdict, produced fact, or refusal).
4. **Proven** — the eval passes in CI. A lesson with no passing eval is surfaced as **"unproven"** (knowledge captured but not yet guaranteed).

Design implications:
- The eval framework must be **surface-agnostic** (today it covers `plan_gate` only) — a shared case schema (`given context → expected verdict/artifact`) so any surface can register cases.
- This is the *proof layer* on top of D12's *memory layer*: memory makes the lesson retrievable; the eval makes "won't happen again" falsifiable and continuously checked.
- Ties to the factory's existing eval discipline rather than inventing a parallel system.

---

## 4. De-hardcoding (D1 enabler, mostly mechanical)
- Extract project identity (slug + repo path) to `.factory/project.json`; **purge `team-app` / `prd-team-app` / the absolute path** from `CONSTITUTION.md` and `README.md` (see system-map references for exact lines).
- Add `meta.kind` vocabulary + `source="map-<project>"` / `category="structure"`.
- Praxis itself needs **zero** code changes.

---

## 5. Risks (adversarial on our own design — implementation session must address)
1. **Stack-generality vs. tooling dependence.** Mutation testing / AST maps / codemods are stack-specific, some slow (30+ min) or absent. The **degradation ladder + recorded oracle confidence** is the mitigation and must be designed in, not bolted on.
2. **Blast-radius scoping is the actual hard problem.** Under-scope → missed regression; over-scope → cost explosion. Dependency-graph expansion + a relevance budget are load-bearing and unsolved.
3. **Coupled green-spine erodes the factory's parallelism advantage** — a tightly coupled refactor may be near-serial. Acceptable, or invest more in decouple-first?
4. **Staged cutover needs production infra/traffic the factory doesn't control.** D7 (author-not-execute) is the deliberate boundary; the *author-verifiable terminal stage* must be defined crisply per project.
5. **Near-zero-test repos** push all oracle weight onto agent-generated characterization tests — partly circular trust; mutation-scoring mitigates but does not eliminate.
6. **Claim-shaping current-state facts (D9):** if facts aren't written subject/attribute/value, contradictions won't fire and reconciliation silently produces no deltas — a correctness trap to test explicitly.

---

## 6. Sequenced build plan (hand-off)
- **P0 — De-hardcode + `meta.kind`:** project config, purge literals, `build_target` partitions on kind. *(Unblocks all; small, mechanical.)*
- **P1 — `factory-understand` + `understand_gate`:** blast-radius repo-map/dep-graph → claim-shaped current-state facts with `file:line`; degradation ladder (AST→black-box); seam/dep diagram artifact.
- **P2 — Characterization + `oracle_gate`:** synthesize golden-master → `preserve` requirements; mutation-score gate + recorded confidence + accept-with-reason; mystery-behavior quarantine.
- **P3 — `factory-intake[brownfield]`:** feed current-state + goal to Praxis; contradictions → deltas; classify `meta.kind`. **plan/audit/review reused.**
- **P4 — `factory-audit` extension:** add the mandatory brownfield decision classes (§3.5). **← end of P4 = the "EXHAUSTIVE PLAN BLESSED" milestone (D10).**
- **P5 — `factory-execute[refactor]`:** dependency-ordered green spine + anchored pitches + BBA seam injection + per-slice preserve verify + codemod path + `keep_green_gate`.
- **P6 — cutover/migration:** auto-expand `migrate|cutover` into the staged ladder + paired exercised rollback + reconciliation ledger; generalize `deploy` hard-gate; define the author-verifiable terminal stage.
- **P7 — closed-loop lesson capture (D12):** `lesson_gate` + the failure→fix → lesson-fact → `general-pool` promotion path; wire lesson retrieval into hermetic-context/understand. *(Cross-cutting; benefits greenfield too — can land early.)*
- **P8 — lessons → evals (D13):** make the eval framework surface-agnostic (shared `given context → expected verdict/artifact` schema; extend beyond `plan_gate`); author the eval-from-lesson lifecycle; CI surfaces "unproven" lessons.
- **P9 — compounding + generality:** promote seam learnings to `general-pool`; cutover-recipe library; **validate against sotos AND `../team-app` (D11).**

---

## 7. Provenance
- HumanLayer RPI/CRISPY (research→plan→implement; file:line research doc; approve before code; vertical slices; sub-agents as context forks).
- Feathers *Working Effectively with Legacy Code* (characterization tests, seams, cover-and-modify); mutation testing to trust the oracle.
- Fowler: Strangler Fig, Branch-by-Abstraction, Parallel Change / Expand-Contract; feature flags as deployment boundary.
- Dual-write/dual-read staged cutover; double-entry reconciliation; aviation MEL; mountaineering anchored pitches; CRISPR off-target framing.
- System maps of `agent_factory` and `../praxis` produced this session (free-form category/source/meta confirmed; completeness = outcome-grounded never-built/regressed/stale).
