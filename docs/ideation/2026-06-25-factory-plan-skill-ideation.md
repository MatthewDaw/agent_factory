---
date: 2026-06-25
topic: factory-plan-skill
focus: how to write a good (human-controlled) plan-hardening skill
mode: repo-grounded
---

# Ideation: How to Write the `factory-plan` Skill

Ideation on the design of the `factory-plan` skill — the human-controlled plan-hardening loop
(pushback + feature-fleshing + research + KG self-consistency) defined by R15–R18 and M1a in the
build plan. Grounded in gstack, compound-engineering's `ce-plan`/`ce-brainstorm`/`ce-ideate`,
GitHub Spec Kit, AWS Kiro, BMAD, Tessl, and the requirements-engineering literature.

## Grounding Context
Borrowable prior art: compound-engineering (one-question-at-a-time; gap lenses
evidence/specificity/counterfactual/attachment; research-the-repo-first; two-stage
Stated/Inferred/Out synthesis; the COMPOUND step; 80/20 effort on planning+review). Spec Kit
(constitution-as-oracle checked at clarify time; `/clarify` with multiple-choice options;
`/analyze` cross-artifact consistency). Kiro (quick vs. rigorous modes; EARS acceptance criteria).
BMAD ("facilitator pulls ideas out of you, not for you"). Tessl (versioned dependency/spec
registry so plans don't hallucinate APIs). gstack (role-scoped context isolation — each persona
sees only what its job needs). RE research (in-context ambiguity examples raise detection ~20%;
Active Task Disambiguation = an explicit *stopping* criterion; Elenchus prover-skeptic dialectic).

## Topic Axes
1. Pushback / pressure-test
2. Feature fleshing (→ binary acceptance conditions)
3. Research integration
4. KG self-consistency loop
5. Skill structure & interaction

## The through-line
Stop treating the plan as a prose document the KG checks; treat it as a **fact-set whose
contradiction-state IS the plan**. Almost every strong idea follows from that.

## Ranked Ideas

### 1. Facts are canonical; the PRD is a rendering of the KG (FOUNDATIONAL)
**Description:** The deliverable is the Praxis fact-set + its contradiction-state, not a hand-typed
doc. The human authors by answering/triaging; each answer is ingested as a fact; the prose PRD is
rendered on demand via the H6 linearizer. No second artifact to drift; the done-gate is a graph
property. Survivors 2–4 assume this model.
**Axis:** 4 / 5 · **Basis:** `direct:` requirements-as-facts + linearizer exists + auto-resolution
off; `external:` BMAD facilitator, Spec Kit `/analyze`.
**Rationale:** Kills spec↔implementation drift at the source; makes hardening mechanically verifiable.
**Downsides:** A real UX bet — answering-into-a-graph must feel better than writing a doc.
**Confidence:** 80% · **Complexity:** Medium-High · **Status:** Unexplored

### 2. Acceptance-as-admission-gate + ambiguity→multiple-choice forge
**Description:** A requirement can't enter the graph without ≥1 binary acceptance condition — else
it's rejected and surfaced until one exists. The skill drafts candidate conditions; the human
accepts/edits/rejects. Vague words are caught at the keystroke and turned into multiple-choice
disambiguations that mint the testable fact.
**Axis:** 2 · **Basis:** `direct:` done-gate + reject-pile; `external:` Spec Kit `/clarify` options,
RE in-context ambiguity examples (~20% lift), Hoare/TDD red-first.
**Rationale:** Shifts the cost of vagueness to where it's cheapest; the gate never accumulates fuzzy items.
**Downsides:** Needs an "owned decision, not-yet-testable" escape for exploratory requirements.
**Confidence:** 82% · **Complexity:** Medium · **Status:** Unexplored

### 3. KG self-consistency: surface (auto-resolution OFF) + reuse the engine as an oracle
**Description:** Ingest with auto-resolution OFF so conflicts surface as a paired-diff review queue
(never silently rejected); always audit the rejected pile. Reuse the same contradiction engine for
external grounding: mount a `constitution` snapshot (invariants), a versioned dependency/spec
registry, and research-evidence facts — so violating an invariant, assuming a non-existent API, or
contradicting evidence fires like an internal conflict.
**Axis:** 4 / 3 · **Basis:** `direct:` auto-resolution off, rejected-pile, mounts, provenance;
`external:` Spec Kit constitution-as-oracle & `/analyze`, Tessl registry.
**Rationale:** One mechanism does intra-spec consistency, invariant compliance, and reality-grounding.
**Downsides:** Contradiction-engine false positives (one seen live) mean the human reviews the queue.
**Confidence:** 80% · **Complexity:** Medium · **Status:** Unexplored

### 4. Adversarial by construction: a skeptic must challenge every requirement
**Description:** A skeptic persona must file ≥1 falsifiable challenge per requirement, routed into
the contradiction channel so an unanswered challenge blocks the gate. A fixed roster of gap-lenses
(failure-modes, security, data-lifecycle, rollback, who-pays-the-tradeoff) must each fire-or-pass,
logged. Optional inversion: assert falsifiable default claims the human vetoes.
**Axis:** 1 · **Basis:** `external:` Elenchus prover-skeptic, cross-examination, CE gap-lenses;
`direct:` auto-resolution off surfaces challenges as conflicts.
**Rationale:** Plans fail on gaps nobody questioned; a structural skeptic finds them, and coverage
becomes provable from the log.
**Downsides:** An over-zealous skeptic generates noise — challenges need a relevance bar.
**Confidence:** 76% · **Complexity:** Medium · **Status:** Unexplored

### 5. Know when to stop (and how hard to push): the gate is the off-switch
**Description:** Commit to an explicit stop and then stop. Gate = every requirement bound + zero
unresolved contradictions + every can't-miss failure class (data loss, auth bypass, irreversible
action, silent partial failure) addressed-or-excluded with logged rationale. Stop by
information-gain, not just zero-contradictions (empty plans have none). Quick vs. rigorous modes
that stamp which checks were skipped. Role-scoped sub-skills (the Clarifier is blind to the
contradiction list so it can't dodge hard questions). Save-before-clear guardrail; snapshot
lineage as diffable plan history.
**Axis:** 5 / 1 · **Basis:** `external:` Active Task Disambiguation stopping, Kiro modes,
differential-diagnosis can't-miss list, gstack role isolation; `direct:` done-gate, save-before-clear.
**Rationale:** Open-ended Socratic loops train people to quit; a skill that closes gets used.
**Downsides:** Info-gain stopping is fuzzy; starts as a heuristic.
**Confidence:** 74% · **Complexity:** Medium-High · **Status:** Unexplored

### 6. The skill compounds: a closing step that improves the tool itself
**Description:** End every run with a compound step: grow the ambiguity-example library, promote
genuinely-new invariants into the `constitution` snapshot, write decision + derivation records to
the event log (local fill for Praxis H4/H5), and reserve an outcome slot per requirement ID so
post-execution verification folds back a trust score (H1). Research enters as provenance facts.
**Axis:** 3 / 5 · **Basis:** `direct:` event log as H1/H4/H5 source, fold-in, provenance;
`external:` CE compound step, ambiguity examples as a reusable asset.
**Rationale:** Meta-leverage — each use upgrades the tool, not just produces one PRD.
**Downsides:** The H1 outcome loop only closes once execution (M1b+) feeds back; partial until then.
**Confidence:** 72% · **Complexity:** Medium (incremental) · **Status:** Unexplored

## Rejection Summary

| Idea | Reason |
|---|---|
| Save-before-clear guardrail; snapshot-as-VCS lineage | Folded into #5 |
| Single-bullet / time-box / hostile-respondent constraint flips | Analysis devices; yield (info-gain ranking, graceful degradation, decline-as-default) folded into #4/#5 |
| Repo-first dossier | Folded into #1 (answer only what artifacts can't) + #3 (research-as-facts) |
| "Human is editor, not author" | Folded into #1 (triage UI) |

## Note
#1 is load-bearing and the riskiest (UX bet). Worth validating on a small real PRD slice before
committing the whole skill to "facts canonical, prose rendered."
