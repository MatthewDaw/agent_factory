# Autonomous Iteration Constitution

**Status:** active operating contract for unattended (overnight) runs.
**Owner is ASLEEP and UNAVAILABLE.** No human will answer questions during this run. Every
decision is yours to make. Do not block, do not wait, do not ask. When a choice is required,
make the best low-regret choice, **record it as a Praxis episode** (with the alternatives you
did not take), and proceed. The owner will review recorded decisions in the morning and
override anything they dislike — your job is forward progress, not perfect certainty.

This file governs **process**, not product design. Read it, read the ledger
(`docs/autonomous-progress-ledger.md`), then act.

---

## 1. North Star (Definition of Done)

Keep iterating until ALL of the following hold:

1. **The product is built and working locally.** Every requirement in the PRD
   (`docs/inspiration/`) is implemented in the team-app repo
   (`C:/Users/mattd/Documents/gauntlet/team-app`) and the full test suite passes
   (`python -m pytest -q` green), with a runnable local entry point.
2. **The plan is hardened in Praxis.** Every PRD requirement is an atomic fact in the
   `prd-team-app` snapshot, each with a binary acceptance condition and zero unresolved
   contradictions.
3. **The tooling is hardened.** Every Praxis/factory edge case found is captured as an eval
   AND fixed to GREEN (or, if a fix is genuinely too risky to make unattended, left RED with a
   documented workaround so the build still proceeds).
4. **Learnings are compounded** back into Praxis.

If all four hold, write a final handoff in the ledger and stop. Otherwise, there is always a
next pass — keep going.

---

## 2. The Two Interleaved Loops

**A. Build loop (the product).** Drive the PRD into the team-app via plan → execute → verify,
using Praxis as compounding memory.

**B. Harden loop (the tooling).** The moment a Praxis or factory failure surfaces during the
build, switch to: reproduce → capture as a RED eval → **fix in Praxis** → confirm GREEN →
repair any polluted state → resume the build.

Build is the default. Harden is an interrupt you service, then return.

---

## 3. Autonomy Doctrine (because the owner is asleep)

- **Never ask a blocking question.** There is no one to answer. The `AskUserQuestion` tool is
  off-limits this run.
- **Resolve-before-decide order** (from `factory-plan`): (1) the PRD text — if it answers,
  use it; (2) mounted knowledge (`general-pool`, `constitution`, prior `prd-*`); (3) a clear
  conventional, low-regret default; (4) only then your own best judgment. At step 3 or 4,
  **record a `praxis_record_episode`** stating the decision + "owner asleep → best-choice
  default" + the alternatives, then proceed.
- **Bias to reversible, low-regret moves.** Prefer the smallest choice that unblocks progress.
- **Never take a high-regret irreversible action.** No `git push`, no force-push, no deleting
  the owner's data, no touching other Praxis orgs or the tax-return work, no destructive ops
  without a saved snapshot first. If the only way forward is high-regret and unguessable,
  park that one item (note it in the ledger) and find other forward progress.
- **Timebox hard problems.** If a Praxis fix resists ~2–3 honest attempts, stop fixing it:
  leave the eval RED, write the workaround, note it in the ledger for the owner, and keep
  building. Do not burn the whole night on one stubborn fix.

---

## 4. The Iteration Pass (the repeatable unit)

Each pass is one slice of forward progress. Run this checklist top to bottom:

1. **Orient.** Read the ledger (§7). Confirm Praxis tenancy: `praxis_whoami` → active org must
   be `agent-factory` (re-`select_org` if not). Confirm `general-pool` is mounted
   (`praxis_list_mounts`; re-mount read-only if missing).
1b. **Tooling-health gate (MANDATORY — tooling stays 100% before building).** Check whether
   praxis `HEAD` changed since the ledger's last-recorded praxis commit (`git -C
   C:/Users/mattd/Documents/gauntlet/praxis log --oneline -1`). **If it changed** (a fix or any
   commit landed): re-verify the whole captured-eval suite with the fast direct-check method
   (ledger "Verified mechanics") + the 48 write-policy unit tests (§12). Record the new praxis
   HEAD in the ledger. **Any eval that is RED — whether newly-captured or regressed by a praxis
   change — is hardened to GREEN (§5) BEFORE any further team-app building this pass.** Burning
   down / keeping-green the RED-eval backlog is first-class work, not only a reaction to a
   build-time failure. If praxis HEAD is unchanged and the eval suite was green last pass, skip
   the re-run (cheap-by-default). After a praxis code change verified green, **restart `:8000`
   (§13)** so the live path is current.
2. **Pick the next slice.** From the ledger's "Next" pointer / the PRD build order (§6).
3. **Plan the slice** (factory-plan discipline):
   - Admit each requirement via `praxis_add_insight(..., category="requirement",
     meta={"requirement_id": "R<n>"}, on_conflict="surface")`.
   - **Workaround (until the atomic-ingest fix lands):** phrase each requirement as ONE
     semicolon-joined sentence so the sentence-splitter does not fragment it.
   - Give every requirement a **binary acceptance condition**. Replace vague terms with
     measurable thresholds (take the PRD's value, or a conventional default + episode).
   - After a batch, `praxis_get_contradictions`; resolve genuine clashes
     (`resolve_contradiction`, keep the PRD-aligned side; `keep="all"` for false positives).
4. **Execute.** Build the code in `team-app`, following existing patterns
   (`team_app/*.py`, `tests/test_*.py`). Prefer test-first for behavior-bearing logic.
5. **Verify.** Run `python -m pytest -q` in `team-app`. Red→green. Corrections fire only on a
   real failing signal.
6. **Compound.** Write back the implementation learning to Praxis with
   `derived_from=[requirement_id]` (mind the known Augmenter merge bug — see §8). Call
   `praxis_record_outcome(requirement_fact_id, "succeeded")` once verified.
7. **Harden if needed.** If any Praxis/factory failure surfaced during 3–6, run §5 before
   continuing.
8. **Checkpoint.** Update the ledger (§7), commit the team-app slice (one focused commit),
   re-`save_snapshot("prd-team-app")` when the plan changed.
9. **Loop.** Go to step 2. Keep going until §1 is satisfied.

---

## 5. The Harden Sub-Loop (find → capture → FIX → confirm → resume)

When a Praxis or factory failure appears:

1. **Stop the build** at the failure point.
2. **Characterize precisely:** what was sent, what landed, the root cause, and the **fix home**
   (Praxis vs the coding factory). State it plainly in the ledger.
3. **Reproduce deterministically.** First a hermetic probe in the scratchpad; then the real
   path using the Praxis venv + env:
   `C:/Users/mattd/Documents/gauntlet/praxis/.venv/Scripts/python.exe` with
   `load_dotenv("C:/Users/mattd/Documents/gauntlet/praxis/.env")`. Drive the REAL write policy
   (`default_write_policy`, `build_trio(graph, llm=None)`) in a fresh isolated tenant; clean up
   the tenant rows in a `finally`.
4. **Capture as a RED eval** under
   `praxis/knowledge/evals/cases/coding_factory/<name>/case.yaml` + a deterministic check
   appended to `praxis/knowledge/evals/deterministic_checks/graph.py`. Mirror the existing
   coding_factory cases (`derived_learning_not_merged_into_source`,
   `contradicting_requirement_not_merged`, `tabular_field_not_merged_into_incumbent`). The
   case docstring must record the live observation + the desired GREEN behavior. **Run the
   check and confirm it reports RED** before moving on (see **§11** for exactly how to run a
   case). (Set `augment_model` when the Augmenter judge is involved; the check `SKIP`s without a
   DSN/key but must reproduce when they exist.)
5. **FIX it in Praxis** (this is the new part — the owner is asleep, so you close the loop):
   - First check whether the bug is **already being fixed** in the Praxis working tree
     (`git status` — another agent may have staged exactly this area, e.g. the Augmenter /
     atomic-ingest work). If so, prefer to verify your eval against their in-progress code
     rather than writing a duplicate, conflicting fix.
   - Otherwise make the **minimal** fix in the relevant Praxis module. Do not regress the
     positive-merge / additive cases (`matt/augment_additive_merge` etc.).
   - **Strongly prefer a STRUCTURAL fix over a PROMPT edit — this is the default stance.** A
     structural change is deterministic, local, and testable: a guard or precondition, a
     slot/flag check, a write-policy ordering rule, a typed exemption (e.g. "a write carrying
     `derived_from` never merges"; "never merge across distinct `category`"; "a flagged
     contradiction is never additively merged"), an explicit code branch, or a new parameter.
     Reach for those first, and second, and third. **Editing a judge/distill PROMPT**
     (`SPLIT_PROMPT`, the augment / conflict / merge / aspect judges, etc.) **is a last resort**,
     justified only for a genuinely narrow edge case that has no structural handle. Two reasons
     it's costly: (1) the prompt text is part of the cassette key, so any edit invalidates
     fixtures en masse and forces a broad re-record; (2) its blast radius is wide and hard to
     predict — a single `SPLIT_PROMPT` tweak in this codebase already regressed 9 unrelated
     recall checks (42→35) and had to be reverted (§12). Prompt-tuning trades a visible local
     win for invisible distributed losses; structural fixes don't. If a prompt edit truly seems
     unavoidable: scope it as tightly as possible, re-verify the FULL sibling + recall set
     (§12) before committing, and if it regresses anything at all, **revert it and leave the
     eval RED with a note** rather than shipping a net-negative change. When unsure whether a
     clean structural fix exists, prefer leaving the eval RED + a workaround (§3 timebox) over a
     speculative prompt change.
   - Re-run the new eval's check → it must flip **RED→GREEN**. Then run the broader
     `coding_factory/` + `matt/` checks you can run offline to confirm no regression
     (**§12** lists the exact sibling cases + unit tests, and how to tell a real failure from a
     cassette flake). **Restart the Praxis server (§13)** so the factory/MCP path picks up your
     fix — a stale server validates against pre-fix code.
6. **Commit carefully — INDEX HYGIENE IS MANDATORY.** The Praxis repo has concurrent activity
   (another agent's staged WIP) and the owner's tax-return work. **Never `git add .`. Never
   commit the index blind.** Always `git status` first, then commit ONLY your explicit files
   with an explicit pathspec: `git commit -m "..." -- <file1> <file2>`. If your files and the
   in-flight agent's work overlap, commit only the non-overlapping eval files and note the
   overlap in the ledger. Never commit the tax-return files or another agent's WIP.
7. **Repair polluted live state.** If the probe/bug corrupted the live `agent-factory` graph
   (e.g. a merged/blended requirement), repair it: `edit_fact` (requires BOTH `title` and
   `content`) to restore the clean fact; `reject_fact` then `delete_fact` to remove strays.
   Re-`save_snapshot("prd-team-app")`.
8. **Resume the build loop** (§4) from where it stopped.

---

## 6. Build Order (the product spine)

Follow the PRD's own build order (`Team Version Requirements.txt` §10), adapted to a
locally-testable Python application (logic-first, with a thin runnable entry point and tests as
the oracle):

1. Auth + roles (athlete / captain / coach permissions)
2. Team + roster (active/inactive membership — **R3 done**)
3. Weekly theme + daily prompt
4. Daily submission + validation (completion — **R1 done**; idempotency R8)
5. Participation aggregation (**R2 done**) + team streak (R4) + team-day boundary (R5)
6. Message posting + moderation (captain message R9)
7. Coach admin dashboard / visibility (R6 athlete, R7 coach)
8. Notifications (R13)
9. Data model wiring (R14) + analytics

Each numbered item is one or more passes. Scope pragmatically: "working locally" means the
application runs and its acceptance tests pass — not a production deployment. Build a thin
backend (e.g. a single-process app with an in-memory or SQLite store) only as far as the PRD's
behavior and its tests require. Decide architecture per-slice; keep it simple.

---

## 7. Progress Tracking (so any loop invocation can resume)

The **single source of resume truth** is `docs/autonomous-progress-ledger.md`. Update it at the
end of every pass (and after every harden sub-loop). It must always answer: where are we, what
did the last pass do, what decision did I make and why, what is next. Keep it append-friendly
and timestamped.

Supporting durable state (do not rely on memory):
- **Praxis `prd-team-app` snapshot** — the canonical hardened plan; re-save when it changes.
- **Praxis episodes** — every owned decision (`record_episode`), so the owner can review.
- **Praxis outcomes** — `record_outcome` per verified requirement (H1 trust).
- **Git commits** — one focused commit per team-app slice; eval commits in Praxis (pathspec
  only). Commit messages are part of the trail.
- **Event log** — `team-app`/factory runs may append to `runs/<id>/events.jsonl`.

Every new loop invocation: **read the ledger first**, reconcile it against the live Praxis
graph + git log, then continue. The ledger is the plan; the graph/commits are the proof.

---

## 8. Praxis Operating Rules & Known-Bug Workarounds

Carry the `factory-memory` policy. Specifics that matter tonight:

- **Confirm org after any reconnect** (`whoami`). Writes to the wrong org are silent data loss.
- **Planning writes use `on_conflict="surface"`** so contradictions surface, never auto-resolve.
- **Known Praxis bugs (each has a RED eval; fix when you reach them, else work around):**
  - *Sentence fragmentation* — a multi-sentence `add_insight` splits per sentence. Workaround:
    single semicolon-joined sentences. Eval: `requirement_not_fragmented_by_distillation`.
  - *Augmenter merges contradictions* — a contradicting same-subject write merges into the
    incumbent instead of surfacing. Eval: `contradicting_requirement_not_merged`.
  - *Augmenter merges derived learnings* — a `derived_from` learning merges into its source.
    Eval: `derived_learning_not_merged_into_source`. Until fixed, write-back learnings with a
    distinct subject, or accept the merge and note it.
  - *Augmenter merges a tabular fact into an overlapping incumbent* despite the slot-guard.
    Eval: `tabular_field_not_merged_into_incumbent`.
- **Manual graph repair:** `edit_fact` needs BOTH `title` and `content`; `delete_fact` needs a
  prior `reject_fact`. `insert_fact` bypasses contradiction detection — do NOT use it for
  requirements (you'd lose surfacing).
- **Save before clear/load.** Never `clear_graph`/`load_snapshot(replace)` without a current
  snapshot.

---

## 9. Git & Safety Discipline (hard rules)

- **team-app:** work on a feature branch; commit per slice; **do not push.**
- **praxis:** commit ONLY your eval/fix files via explicit pathspec after `git status`. Never
  `git add .`. Never commit another agent's staged WIP or the tax-return work. (This session
  already had one contaminated commit — do not repeat it.)
- **agent_factory:** commit the constitution/ledger/factory changes on a branch; do not push.
- Touch only the `agent-factory` Praxis org. Leave `tax-harness` / `praxis` orgs alone.
- Prefer additive changes. Keep existing tests/evals green.

---

## 10. Loop Mechanics

Each invocation is one or more passes and is fully resumable:
**read ledger → orient → run pass(es) → update ledger → commit → continue.**
There is no "are we done?" question to ask — §1 is the objective test. While it is unmet and a
safe next action exists, keep going. Make your best choice, record it, and move forward.

---

## 11. Running Evals (the HOW — offline mechanics)

All commands run from the Praxis repo (`C:/Users/mattd/Documents/gauntlet/praxis`). Use the
Praxis venv python (`.venv/Scripts/python.exe`) or `uv run --no-sync python`.

**One-time setup per machine/session:**
1. **Postgres.** The eval cases that drive the write policy need a local Postgres+pgvector.
   The owner's dev DB is already up as the container `praxis-db-kg` on **host port 5433**
   (this is what the running server uses). Eval cases isolate to **ephemeral random tenants**,
   so running them against 5433 will not touch the `agent-factory` org — but if you want zero
   risk, start a throwaway:
   `docker run -d --name praxis-eval-pg -e POSTGRES_USER=praxis -e POSTGRES_PASSWORD=praxis -e POSTGRES_DB=praxis_kg -p 5439:5432 pgvector/pgvector:pg16`
   then `export PRAXIS_DB_URL="postgresql://praxis:praxis@localhost:5439/praxis_kg"` and migrate
   once: `python -m knowledge.serve.db`. (Port 5433 is already migrated; a fresh container is not.)
2. **Env.** `set -a; . ./.env; set +a` loads `OPENROUTER_API_KEY`. Always also set
   `export OTEL_SDK_DISABLED=true` — otherwise the Phoenix tracing exporter retries failed SSL
   for minutes and makes runs look hung.

**Run a case:**
`python -m knowledge.evals.run <case_id> [<case_id> ...] <backend> [--workers N]`
- **Backends:** `--openrouter` (cheap single-shot — use for `component: knowledge_graph` /
  `graph_reader` cases, i.e. all `coding_factory/*` and the recall/distillation cases);
  `--structured` (file-artifact grading, for `needs: [file_io]` cases); **default = real Claude
  Code** (the heavy agent backend for `file_io` cases — SLOW, ~1–3 min/case; avoid it for quick
  iteration, it is not needed to validate write-policy fixes).
- **`--workers N`** runs N cases concurrently (independent, I/O-bound on LLM calls). Use 4–6.
  Cassette writes are locked, so parallel recording is safe.
- A case `[SKIP]`s when it needs a capability the backend/cassette can't provide (e.g. a
  `file_io` case under `--openrouter`, or a missing cassette keyless) — a skip is not a pass.

**THE CASSETTE MODEL — internalize this, it is the #1 cause of false regressions:**
Every LLM/judge/embedding call is cassette-backed (`knowledge/evals/fixtures/...`), keyed on a
hash of the **payload + model id**.
- **With `OPENROUTER_API_KEY` set:** a hit replays for free; a **miss computes live AND writes
  the result back into the committed fixture** (write-through). So *running an eval with the key
  mutates fixture files in your working tree.* That is expected — those diffs are recorded
  cassettes, not corruption.
- **Without a key (keyless):** replay-only. A miss is a **loud error**, never a silent live call.
  This is what CI does, so it is fully deterministic.
- **Determinism check:** to know if a pass/fail is real vs a lucky live recording, re-run the
  same case **keyless** (`unset OPENROUTER_API_KEY`). Keyless replay is the source of truth. A
  case that passes with the key but flakes/fails keyless has an incomplete or unlucky cassette.
- **Changing a judge/distill PROMPT invalidates cassettes** (the prompt is in the payload key) →
  mass miss → every affected case must be re-recorded with the key. Big blast radius; treat
  prompt edits as expensive and verify they don't regress the *other* recall checks before
  committing (see §12).
- **Deliberate cassette regen:** `python -m knowledge.evals.verdict_cache --refresh` (records
  merge/conflict/aspect verdicts for cases that set `merge_model`/`conflict_model`/`tag_model`,
  and fills embedding misses). Commit the refreshed fixtures.

**Note:** CI (`pytest`) does NOT run the eval *cases* — it runs unit tests + its own cassettes.
So making an eval case GREEN is for the harden loop (§5), not for CI gating. CI is validated
separately by `pytest` (see §12).

---

## 12. Avoiding Regressions (mandatory after any Praxis fix)

A "fix" is not done until you've shown it didn't break the cases it wasn't aimed at.

1. **Unit tests (fast, deterministic, no key needed — just `PRAXIS_DB_URL`):**
   `python -m pytest -q knowledge/knowledge_graph/write_policy/tests` (48 tests; the write-policy
   guardrails). For a full keyless CI-equivalent run: `python -m pytest -q` (needs Postgres).
2. **Sibling eval cases** most likely to regress from a write-policy change — run keyless or with
   the key, `--openrouter`: `augment_no_merge_distinct_rules`, `plan_requirements_kept_distinct`,
   `semantic_no_conflict_distinct_actors`, `semantic_no_conflict_storage_target`, plus the four
   `coding_factory` cases. These cover both "should stay distinct" and "should still merge"
   directions — a guard that over-fires will redden them.
3. **Real vs flake vs loss — do not paper over:**
   - A failure that reproduces **keyless and deterministically** is real. Fix the code, not the
     test.
   - Do NOT make an eval green by doctoring its seed data, loosening an assertion to match buggy
     output, or cherry-picking a lucky cassette recording. That hides the very loss the eval
     exists to catch. (Lesson this session: `matt_tax_return_ruleset_distillation`'s rounding
     checks fail because the distiller collapses a compound "…: drop X; increase Y" sentence down
     to the summary clause — a genuine distillation loss. A `SPLIT_PROMPT` tweak to fix it
     *regressed* the other 9 recall checks (42→35) and was reverted. This is an OPEN, real bug —
     left RED with this note, per §3's timebox rule. Do not "fix" it by editing the seed.)
4. If a change's blast radius is large (prompt/policy edits), re-record **and** re-verify the
   broad set before committing; note the regen in the ledger.

---

## 13. Restarting the Praxis Server (so tests & the factory run against updated code)

The MCP server / `praxis_*` factory tools and any HTTP client talk to a **long-running**
`python -m knowledge.serve` process (loads `.env`, connects to `PRAXIS_DB_URL` on :5433, serves
`http://127.0.0.1:8000`). It is **not** started with `--reload`, so **after you edit any Praxis
module the running server keeps executing the OLD code** until you restart it. A stale server
means tests/the factory validate against pre-fix behavior — silently. So:

**After any Praxis code change that the factory/server exercises, restart it:**
```bash
# 1. find the listener on :8000
netstat -ano | grep ":8000.*LISTEN"          # note the PID in the last column
# 2. stop it (PowerShell)
powershell -NoProfile -Command "Stop-Process -Id <PID> -Force"
# 3. relaunch in the background (loads .env itself; do NOT add --reload — unsupported here)
cd C:/Users/mattd/Documents/gauntlet/praxis && uv run --no-sync python -m knowledge.serve &
# 4. health-check
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/health   # expect 200
```
- The server reads `.env` on boot, so make sure `PRAXIS_DB_URL` there still points at the live
  dev DB (`:5433` / container `praxis-db-kg`) before restarting — do not point it at an eval
  throwaway DB, or the factory loses the `agent-factory` graph.
- `/` returns 404 (no root route); use `/health` (200) and `/docs` (200) to confirm liveness.
- **Architecture (verified):** the `praxis_*` MCP server (`knowledge.mcp.server`) is a **thin
  httpx proxy to `:8000`** (`DEFAULT_API_BASE=http://localhost:8000`) — it holds NO graph logic.
  So a Praxis code fix is picked up by the **`:8000` restart above alone**; the stdio MCP process
  does NOT need restarting for code changes. **Exception:** editing `knowledge/mcp/server.py`
  itself (tool signatures, the httpx timeout, the proxy layer) only takes effect when the stdio
  MCP process reconnects — which is **harness-managed and cannot be triggered from within the
  run**. If a fix requires that, do NOT pretend it took effect: stop, note it in the ledger as a
  human-action item, and route around it.
- Unit tests (`pytest`) spin up their own app/DB fixtures and do NOT need the server running;
  only the **factory / live MCP path** needs the restart to see new code.
