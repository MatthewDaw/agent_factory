# Autonomous Progress Ledger

Single source of resume truth for the overnight run. Governed by `../CONSTITUTION.md`.
**Read this first, reconcile against the live Praxis graph + git log, then continue.**
Update at the end of every pass. Newest entries at the bottom of each section.

---

## NEXT (the resume pointer)

1. **Build the role/permission + visibility slices** — R6 (athlete sees only team-aggregate
   participation/streak, never per-teammate completion) and R7 (coach can query per-athlete
   completion; athlete/captain cannot). Add a `team_app/roles.py` (role enum + a
   `can_view_individual_completion(role)` / visibility helper) + a `team_app/views.py` or
   aggregate-vs-individual view selector, with tests. This is the first slice needing a
   role/permission concept — keep it a pure function over (role, data), no web layer yet.
2. Then captain message (R9), weekly theme (R11) / daily prompt (R12), notifications (R13),
   captain message (R9), weekly theme (R11) / daily prompt (R12), notifications (R13), and a thin
   runnable local entry point. Follow build order in CONSTITUTION §6.
4. Continue passes until DoD (CONSTITUTION §1).

**Graph is clean as of the last pass** (R5/R8 repaired, R14 strays removed, snapshot re-saved at
15 nodes). R10 (leaderboard) correctly stays `rejected`. R14 (data model) is intentionally NOT a
standalone Praxis requirement — realized in code (episode `df98fd8b`).

---

## Product build status (team-app: C:/Users/mattd/Documents/gauntlet/team-app)

**Git:** repo initialized this session; baseline (R1–R3, 14 green) committed on branch
**`feat/team-app-build`** (off `main`). Commit each slice here; do not push.


| Req | Feature | Code | Status |
|-----|---------|------|--------|
| R1  | Daily completion | `team_app/completion.py` | ✅ built, green |
| R2  | Participation %  | `team_app/participation.py` | ✅ built, green |
| R3  | Active roster    | `team_app/roster.py` | ✅ built, green |
| R4  | Team streak (≥70%) | `team_app/streak.py` | ✅ built, green |
| R5  | Team-day boundary (3AM) | `team_app/day_boundary.py` | ✅ built, green |
| R6  | Athlete visibility (aggregate only) | — | ⛔ todo |
| R7  | Coach visibility (per-athlete) | — | ⛔ todo |
| R8  | Submission idempotency | `team_app/submissions.py` | ✅ built, green |
| R9  | Captain message + approval | — | ⛔ todo |
| R11 | Weekly theme | — | ⛔ todo |
| R12 | Daily prompt | — | ⛔ todo |
| R13 | Notifications | — | ⛔ todo |
| R14 | Data model wiring | — | ⛔ todo |
| —   | Auth + roles | — | ⛔ todo (PRD §1) |
| —   | Local runnable entry point | — | ⛔ todo |

Test suite: **33 passing** (completion 4 + participation 4 + roster 6 + streak 6 + day_boundary 6
+ submissions 7) as of last build.

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

- **2026-06-26 Pass 3:** Built **R8 submission idempotency** (`team_app/submissions.py`:
  `SubmissionStore` upsert per (user_id, team_day); 7 tests incl. an R8→R2 integration proving a
  retry stays at 50%). Suite 33 green. Episode `4dde8215` + `record_outcome(R8)`. Commit `7967d51`.
  No bug. Next: R6/R7 visibility + roles.
- **2026-06-26 Pass 2:** Built **R5 team-day boundary** (`team_app/day_boundary.py`:
  `team_day(local_dt, reset_hour=3)`; 6 tests incl. midnight rollback + month boundary). Suite 26
  green. Episode `c57ff10e` + `record_outcome(R5)`. Commit `994ecfb`. No bug.
- **2026-06-26 Pass 1 (first loop pass):** Cleaned the polluted graph (repaired R5 + R8 via
  `edit_fact`; rejected+deleted the 3 stray R14 field-facts; re-saved snapshot @15 nodes). R14
  hit the known Augmenter merge into R8 → repaired R8, recorded decision to keep R14 in code
  only (episode `df98fd8b`). Built **R4 team streak** (`team_app/streak.py`, 6 tests, suite 20
  green); recorded impl episode `9b715f1e` + `record_outcome(R4, succeeded)`. Committed team-app
  `458aa4d`. No new bug (the R14 merge is already covered by `tabular_field_not_merged_into_incumbent`).
  Next: R5.
- **2026-06-26 (session prior to loop):** Established constitution + ledger. Ran the planning
  loop over the team-app PRD; found and captured 3 new Praxis edge cases as RED evals
  (fragmentation, contradiction-merge, tabular-merge); verified recall/episodes/snapshot/
  mount/contradiction-surface+resolve/bulk-write/H1 all healthy. R1–R3 already built+green from
  earlier. Left at the NEXT pointer above.
