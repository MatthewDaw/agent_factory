# Plan-reproduction eval — feature coverage (no holes)

A **new eval lane**, separate from the deterministic `evals/cases/<component>/case.yaml`
suite. The deterministic suite feeds a fixed `input` to a registered `Gate.evaluate()`
and asserts on the `Verdict`; its loader (`case_def.py`) *rejects* any non-deterministic
input. This eval is a different kind — it runs an **LLM planning process** over a PRD and
judges the result with a **fuzzy coverage judge** — so it cannot live in that suite and
gets its own lane here.

## What it proves
Given the raw product docs in `docs/inspiration/`, the factory's planning process must
produce a plan whose **feature set has no holes** versus the hand-refined golden plan that
already lives in the Praxis `prd-team-app` graph. The archetypal hole: the raw spec lists
signup/login/logout but **no password-reset** — the refined plan has one. A reproduced plan
that omits it (or the consent gate, the minor-consent flow, the loading/empty states, …)
**fails**.

Its real job: be the **regression net** for generalizing the planning gate — when the
hard-coded `GAP_LENSES` / planning checks move into a Praxis `planning` snapshot and the
gate reads its checklist from there, this eval proves the generalized planner stays as
hole-free as the hand-refined one.

## Scoring (coverage / no-holes)
- **Target:** `team-app/golden-features.yaml` — the canonical feature list extracted from
  the `prd-team-app` graph (the result of the real refinement passes).
- **Candidate:** the requirement/feature set a planning run produces from `docs/inspiration/`.
- **Match:** each golden feature must be **covered by ≥1 candidate feature**, judged
  **semantically** — *variant wording is fine*; this is "is this feature represented at
  all," not text-equivalence. Matching is a fuzzy judge (LLM or human), not string equality.
- **PASS:** zero holes — every golden feature is covered. **Especially** zero missed
  `derived: true` features (the ones the raw PRD never stated; a naive planner misses these,
  so they are the eval's teeth).
- **Report:** per golden feature → `covered | missing | variant`, with the matched candidate
  text. Extra candidate features (not in golden) are reported but do **not** fail the eval
  (over-coverage is allowed; holes are not).

## Two halves
1. **Coverage checker** *(buildable now)* — given a candidate feature list + the golden,
   produce the per-feature coverage report and the pass/fail. The fuzzy match is the judge.
   This half can score a *supplied/recorded* candidate plan today.
2. **Plan-production run** *(built — `planner.py` + `run_eval.py`)* — a controllable
   *planner-under-test* generates the candidate from `docs/inspiration/`, with the planning
   checklist as a knob (baseline vs. treatment). This isolates one variable (the checklist)
   rather than running the full gated `factory-intake`/`factory-plan` machinery, which would
   mutate Praxis and isn't repeatable. The baseline-vs-treatment derived-hole delta is the
   meta-proof that the checklist closes holes. Needs a model backend to run.

## Inputs
- `docs/inspiration/Developer-Ready Spec_ Team Mental Performance App (MVP).txt`
- `docs/inspiration/Team Version Requirements.txt`
- `docs/inspiration/Team Version — One-Screen Daily Flow.txt`

## Files
- `team-app/golden-features.yaml` — the coverage target (78 features).
- `coverage.py` — the shared coverage engine (per-part sweep, evidence-required + targeted
  adversarial, zero-holes pass/fail) with injected `related_query` / `item_evaluator` / `refuter`
  seams and deterministic lexical baselines. Tested in `tests/test_coverage_engine.py`.
- `llm_evaluator.py` — LLM-backed `item_evaluator` + `refuter` (and a `tiered` fast-path) built
  from an injected `Complete = (prompt) -> text`; Anthropic backend via `make_anthropic_complete`.
  Tested in `tests/test_llm_evaluator.py`.
- `planner.py` — the planner-under-test: PRD (+ optional `DEFAULT_PLANNING_CHECKLIST`) -> candidate
  feature list, via an injected `Complete`. The checklist knob A/Bs baseline vs. treatment. A
  controllable proxy for the production gated planner, not a replacement. Tested in
  `tests/test_planner.py`.
- `run_eval.py` — end-to-end CLI: plan from `docs/inspiration/` -> save candidate -> score vs the
  golden with the LLM judge + refuter. Needs a model backend (Anthropic SDK + key).
- `team-app/candidate-*.yaml` — recorded candidate plans (written by `run_eval.py`; re-scorable
  deterministically without re-planning).

## Regenerating the golden
`golden-features.yaml` was extracted from the live `prd-team-app` graph
(`praxis_list_graph` / `praxis_incomplete_requirements`) on 2026-06-26 (123-node snapshot,
~78 `category=requirement` facts). When the golden plan changes, re-extract and diff.
