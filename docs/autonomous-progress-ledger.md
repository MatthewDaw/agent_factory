# Autonomous Progress Ledger

Single source of resume truth for the overnight run. Governed by `../CONSTITUTION.md`.
**Read this first, reconcile against the live Praxis graph + git log, then continue.**
Update at the end of every pass. Newest entries at the bottom of each section.

---

## NEXT (the resume pointer)

1. **Build R13 (notifications)** — per athlete per team-day, at most one daily reminder + at most
   one streak-save reminder fire, and no reminder names or implies a specific non-completing
   athlete (PRD §7). Add `team_app/notifications.py` (a scheduler that, given a team-day's state,
   returns the ≤2 reminders to send, each with safe non-shaming copy) + tests.
2. Then **auth + roles wiring** (PRD §1) and a **thin runnable local entry point** (e.g. a single
   `team_app/app.py` that assembles a team-day view from the stores) so the app "runs locally."
3. Continue passes until DoD (CONSTITUTION §1). Build order: CONSTITUTION §6.

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
| R6  | Athlete visibility (aggregate only) | `team_app/roles.py`+`views.py` | ✅ built, green |
| R7  | Coach visibility (per-athlete) | `team_app/roles.py`+`views.py` | ✅ built, green |
| R8  | Submission idempotency | `team_app/submissions.py` | ✅ built, green |
| R9  | Captain message + approval | `team_app/messages.py` | ✅ built, green |
| R11 | Weekly theme | `team_app/content.py` | ✅ built, green |
| R12 | Daily prompt | `team_app/content.py` | ✅ built, green |
| R13 | Notifications | — | ⛔ next |
| R14 | Data model wiring | — | ⛔ todo |
| —   | Auth + roles | — | ⛔ todo (PRD §1) |
| —   | Local runnable entry point | — | ⛔ todo |

Test suite: **55 passing** (completion 4 + participation 4 + roster 6 + streak 6 + day_boundary 6
+ submissions 7 + views/roles 5 + messages 8 + content 9) as of last build.

## Plan status (Praxis `agent-factory` org / `prd-team-app` snapshot)

Requirements admitted live: R1–R9, R11–R13 (12 requirements, each one atomic fact). R10 rejected
(leaderboard, lost to R6). R14 intentionally not a standalone fact (in code; episode `df98fd8b`).
Decisions recorded as episodes. `general-pool` mounted read-only. `prd-team-app` snapshot current
at **15 nodes** (re-saved Pass 1).

---

## Tooling: evals captured / fixed

| Eval (praxis `coding_factory/`) | Captures | Status |
|---|---|---|
| `requirement_not_fragmented_by_distillation` | multi-sentence req splits per sentence | ✅ **GREEN** (atomic insights, #97) |
| `contradicting_requirement_not_merged` | Augmenter merges a contradicting req (defeats `surface`) | ✅ **GREEN** (Augmenter contradiction guard, #97) |
| `tabular_field_not_merged_into_incumbent` | tabular fact merges into overlapping incumbent | ✅ **GREEN** (Augmenter guard, #97) |
| `derived_learning_not_merged_into_source` | derived learning merges into source | ✅ **GREEN** (feat/derived-no-merge, `c0da203`) |

**ALL FOUR captured bugs are FIXED and verified GREEN** (2026-06-26 Pass 4) — the parallel
Praxis agent's fixes landed in praxis `main` (`f381109` Augmenter contradiction guard + atomic
insights #97; `c0da203` derived-no-merge; `ee76f75` update_fact category). Verified via the
direct-check method against current code; **48/48 write-policy unit tests pass (no regression)**;
`:8000` restarted so the live factory path runs the fix.

**Praxis HEAD at last verify: `5370659`.** Tooling-health gate (CONSTITUTION §1b): each pass, if
praxis HEAD ≠ this, re-verify the eval suite + write-policy tests and harden any RED to GREEN
before building; then update this line.

**Known OPEN (not ours to fix): `matt_tax_return_ruleset_distillation`** — a real compound-rule
distillation loss in the tax domain; a `SPLIT_PROMPT` fix regressed 9 recall checks and was
reverted (§12). Tax domain — leave alone per owner constraint.

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

- **2026-06-26 Pass 7:** §1b gate: praxis HEAD unchanged (`5370659`) → tooling green, skipped.
  Built **R11 weekly theme + R12 daily prompt** (`team_app/content.py`: WeeklyThemeStore +
  DailyPromptStore, one-per-key upsert, response_type validation; 9 tests). Suite 55 green.
  Episode `efcd8d4c` + `record_outcome(R11, R12)`. Commit `d087778`. No bug. Next: R13.
- **2026-06-26 Pass 6:** §1b gate: praxis HEAD unchanged (`5370659`) → tooling still green,
  skipped re-verify. Built **R9 captain/coach message + optional approval** (`team_app/messages.py`:
  role-gated post, coach-only approve, team-scoped visibility, single-active-captain supersede,
  expiry; 8 tests). Suite 46 green. Episode `5282659b` + `record_outcome(R9)`. Commit `a10d465`.
  No bug. Next: R11/R12/R13.
- **2026-06-26 Pass 5:** Switched loop cadence to **every 15 min** (cron `797c0c14`; old
  `1defb1e0` deleted; cron prompt now runs the §1b gate first). Built **R6/R7 role-aware
  visibility** (`team_app/roles.py` + `views.py`; `SubmissionStore.for_day_by_user`; 5 tests —
  athlete/captain aggregate-only, coach per-athlete, deny-by-default, store integration). Suite
  38 green. Episode `942cc8d9` + `record_outcome(R6, R7)`. Commit `5714947`. No bug. Next: R9.
- **2026-06-26 Pass 4 (HARDEN — tooling to 100%):** Owner flagged the loop wasn't closing evals.
  Checked praxis git: the parallel agent's fixes had **landed** (`f381109` Augmenter contradiction
  guard + atomic insights #97; `c0da203` derived-no-merge; `ee76f75` update_fact category; HEAD
  `5370659`). Re-verified **all 4 captured evals → GREEN** (direct-check); **48/48 write-policy
  unit tests pass** (no regression); **restarted `:8000`** (stale PID 5764 → 16792) so the live
  path runs the fix. Added the **§1b tooling-health gate** to the constitution (re-verify evals
  whenever praxis HEAD changes; harden RED→GREEN before building). No team-app build this pass —
  tooling-first per owner. Next: resume build at R6/R7 with tooling confirmed green.
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
