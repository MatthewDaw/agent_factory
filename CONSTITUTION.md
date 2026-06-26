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
   check and confirm it reports RED** before moving on. (Set `augment_model` when the Augmenter
   judge is involved; the check `SKIP`s without a DSN/key but must reproduce when they exist.)
5. **FIX it in Praxis** (this is the new part — the owner is asleep, so you close the loop):
   - First check whether the bug is **already being fixed** in the Praxis working tree
     (`git status` — another agent may have staged exactly this area, e.g. the Augmenter /
     atomic-ingest work). If so, prefer to verify your eval against their in-progress code
     rather than writing a duplicate, conflicting fix.
   - Otherwise make the **minimal** fix in the relevant Praxis module. Do not regress the
     positive-merge / additive cases (`matt/augment_additive_merge` etc.).
   - Re-run the new eval's check → it must flip **RED→GREEN**. Then run the broader
     `coding_factory/` + `matt/` checks you can run offline to confirm no regression.
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
