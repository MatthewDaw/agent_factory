# Autonomous Progress Ledger

Single source of resume truth for the overnight run. Governed by `../CONSTITUTION.md`.
**Read this first, reconcile against the live Praxis graph + git log, then continue.**
Update at the end of every pass. Newest entries at the bottom of each section.

---

## NEXT (the resume pointer)

1. **Clean up polluted live graph** (from this session's probing) before building further:
   - R5 (`45d9c110…`) was polluted by the `team_day` tabular merge — `edit_fact` it back to the
     clean "Team day boundary (R5): … attributed to team-day D when T >= 03:00, otherwise to
     team-day D-1." (title + content both required).
   - R14 table left stray field-facts (`user_id`/`completion_status`/`ratings_json`) and a
     merged `team_day`. Decide: keep them as data-model facts (fine) or reject the partial set
     and re-admit R14 cleanly as one atomic fact. Best-choice default: reject the 3 stray field
     facts + re-admit R14 as a single semicolon-joined data-model requirement.
   - R10 (leaderboard) correctly stays `rejected` (lost to R6 privacy). Leave it.
   - Re-`save_snapshot("prd-team-app")` after cleanup.
2. **Build R4 (team streak)** in `team-app` — next buildable pure-logic slice (threshold 70%,
   resets on a sub-70% day, N=0 day no-ops). Then **R5 (team-day boundary)**, then **R8
   (idempotency)**. Follow build order in CONSTITUTION §6.
3. Continue passes until DoD (CONSTITUTION §1).

---

## Product build status (team-app: C:/Users/mattd/Documents/gauntlet/team-app)

**Git:** repo initialized this session; baseline (R1–R3, 14 green) committed on branch
**`feat/team-app-build`** (off `main`). Commit each slice here; do not push.


| Req | Feature | Code | Status |
|-----|---------|------|--------|
| R1  | Daily completion | `team_app/completion.py` | ✅ built, green |
| R2  | Participation %  | `team_app/participation.py` | ✅ built, green |
| R3  | Active roster    | `team_app/roster.py` | ✅ built, green |
| R4  | Team streak (≥70%) | — | ⛔ next |
| R5  | Team-day boundary (3AM) | — | ⛔ todo |
| R6  | Athlete visibility (aggregate only) | — | ⛔ todo |
| R7  | Coach visibility (per-athlete) | — | ⛔ todo |
| R8  | Submission idempotency | — | ⛔ todo |
| R9  | Captain message + approval | — | ⛔ todo |
| R11 | Weekly theme | — | ⛔ todo |
| R12 | Daily prompt | — | ⛔ todo |
| R13 | Notifications | — | ⛔ todo |
| R14 | Data model wiring | — | ⛔ todo |
| —   | Auth + roles | — | ⛔ todo (PRD §1) |
| —   | Local runnable entry point | — | ⛔ todo |

Test suite: 14 passing (completion 4 + participation 4 + roster 6) as of last build.

## Plan status (Praxis `agent-factory` org / `prd-team-app` snapshot)

Requirements admitted live: R1–R9, R11–R13 (bulk), R14 (partial/merged). R10 rejected
(leaderboard, lost to R6). R4-threshold decision recorded as an episode. `general-pool` mounted
read-only. `prd-team-app` snapshot last saved at 10 nodes **before** R11–R14 + cleanup — it is
**stale**; re-save after the cleanup in NEXT.

---

## Tooling: evals captured / fixed

| Eval (praxis `coding_factory/`) | Captures | Status |
|---|---|---|
| `requirement_not_fragmented_by_distillation` | multi-sentence req splits per sentence | 🔴 RED, committed |
| `contradicting_requirement_not_merged` | Augmenter merges a contradicting req (defeats `surface`) | 🔴 RED, committed |
| `tabular_field_not_merged_into_incumbent` | tabular fact merges into overlapping incumbent | 🔴 RED, committed |
| `derived_learning_not_merged_into_source` | derived learning merges into source | 🔴 RED (prior) |

**All four share one root cause: the Mem0-style Augmenter over-merges.** Highest-value Praxis
fix. A Praxis agent was actively implementing the **Augmenter / atomic-ingest fix** in the
praxis main working tree (staged: `augmenter.py`, `prompt_injestor.py`, `parent_injestor.py`,
`postgres_vector_graph.py`, `app.py`). **Before fixing any of these yourself, `git status` the
praxis repo** — if that work has landed, verify the evals against it (some should flip GREEN)
rather than writing a duplicate fix.

---

## Verified mechanics (use these; don't rediscover)

- **Praxis eval check — fast, no side effects (validated 3x this session):** call the check
  directly with the case params:
  `praxis/.venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'.'); from dotenv import load_dotenv; load_dotenv('.env'); from knowledge.evals.deterministic_checks.graph import <check> as c; print(c(None, **params).passed)"`
  (run from the praxis repo). Reproduces against the real write policy via the live `.env`
  (Postgres :5433 + OpenRouter); does NOT write cassettes. Prefer this for RED/GREEN confirmation.
- The full harness runner (CONSTITUTION §11, `python -m knowledge.evals.run <id> --openrouter`)
  also works but **write-throughs cassette fixtures** into the praxis tree — extra index noise
  while another agent is active there; use only when you need the harness's grading/SKIP logic.
- **team-app tests:** `cd team-app && python -m pytest -q` (baseline 14 green).
- **Praxis backend health:** `curl 127.0.0.1:8000/health` → 200 (PID was 5764; restart per §13
  after any praxis code fix — the MCP just proxies to :8000).

## Decisions log (owned, low-regret; owner may override)

- Streak threshold = **≥70%** of active roster (PRD §3 worked example). Episode recorded
  (`64456c97…`). Alternatives: 50% / 80% / 100%.
- Checklist is **optional** for completion (PRD-recommended; does not gate completion).
- N=0 participation = **None / "no active roster"**, never 0 (conventional default; PRD silent).
- Privacy (R6) **wins** over an athlete-visible completion leaderboard (R10) — PRD §5 privacy is
  non-negotiable; R10 rejected via `resolve_contradiction`.

## Open issues / watch-outs

- **Index hygiene (CONSTITUTION §9):** praxis repo has concurrent agent WIP + the owner's
  tax-return work staged. Commit eval/fix files with explicit pathspec only. One contaminated
  commit already happened this session and was corrected — do not repeat.
- Known-bug workarounds in effect (single-sentence requirements, etc.) — CONSTITUTION §8.

---

## Pass history

- **2026-06-26 (session prior to loop):** Established constitution + ledger. Ran the planning
  loop over the team-app PRD; found and captured 3 new Praxis edge cases as RED evals
  (fragmentation, contradiction-merge, tabular-merge); verified recall/episodes/snapshot/
  mount/contradiction-surface+resolve/bulk-write/H1 all healthy. R1–R3 already built+green from
  earlier. Left at the NEXT pointer above.
