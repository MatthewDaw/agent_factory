---
name: factory-audit
description: >
  The separate cold-eyes judgment audit that runs AFTER factory-plan admits requirements and
  BEFORE the plan is blessed (save_snapshot). It adversarially challenges every admitted
  requirement, detects and routes underspecification, checks cross-requirement gaps, AND forces
  every end-to-end technical-architecture decision (auth, data store, stack, deploy, secrets, ...)
  to be made explicitly — the
  pushback that mechanical gates can't do. Use as the last step of plan-hardening (intake →
  plan → audit → snapshot). A Stop-hook gate blocks the snapshot until the audit is satisfied.
---

# Factory Audit (judgment skeptic + underspecification)

The mechanical checks (binary-acceptance, no-vague-term, no-dangling-reference via `plan_gate`,
and contradiction surfacing via Praxis `on_conflict="surface"`) happen **inline during ingestion**
in `factory-plan`. They catch what's *nameable*. This skill is the **separate step** for what needs
judgment: *is this requirement underspecified? what case does it not handle? what gap sits between
two requirements?* It runs over the admitted-but-not-yet-snapshotted set so the `prd-<project>`
live graph is the staging area and **nothing is blessed until the audit passes**.

## Why separate (not inline)

- **Independence.** A skeptic firing in the same breath that drafted a requirement is self-review —
  the weak kind (`factory-verify`: a model judging its own output inflates its pass rate). So run
  the challenge with **cold eyes**: dispatch the **read-only retrieval sub-agent** (`factory-execute`
  §1a) as the skeptic — it reads the admitted facts (`praxis_list_graph` / `get_context` on the live
  graph) plus the PRD prose and wireframe, and tries to **break** each requirement. It didn't write
  them, so it challenges harder.
- **Whole-set view.** Cross-requirement gaps (a missing interaction, an unhandled handoff) are
  invisible per-requirement; the audit sees the full set.
- **Enforceable.** A separate gated artifact is the forcing function — the same lesson as the
  wireframe coverage gate. Inline good intentions get skipped under context pressure; a gate doesn't.

## Step 1 — Adversarial challenge (cold eyes, every requirement)

For each admitted requirement, the skeptic files **≥1 falsifiable challenge** drawn from: missing
actor, unbounded condition, unhandled empty / error / boundary case, hidden dependency, idempotency,
race/ordering, and **cross-requirement gap** (the case that falls between two requirements). In
**rigorous** mode, each gap-lens must explicitly **fire-or-pass** per requirement: `failure-modes`,
`security`, `data-lifecycle`, `rollback`, `who-pays`.

A challenge isn't done until it's **closed** — one of:
- **resolved** — the plan changed (edit/add a requirement via factory-plan; record the resolution),
- **dismissed** — the challenge doesn't hold (record *why* — a non-empty reason),
- **deferred** — a genuine owned-decision that can't be settled now (record it as a deferred fact;
  it's explicit, not silent).

### Step 1a — Near-duplicate / overlap challenges WRITE BACK to the graph (not just annotate)

A specific, load-bearing class of challenge is the **near-duplicate / overlap** pair: two admitted
facts that say the same thing, or where one restates a clause of the other. The cold-eyes pass is the
**only** dedup/reconcile step for any plan admitted via the `raw=True` bulk fast-lane (factory-plan
Step 1 item 4) — `raw` deliberately **skips Praxis dedup**, so no earlier stage collapses these. That
makes reconciliation **the audit's job**: leaving the graph clean is the outcome, not a free-text
note about it. A near-dup resolution is therefore **not "closed" until the graph itself reflects it** —
an annotation in `plan-audit.json` alone does NOT close it. Reason about the pair, then take the
matching graph action:

- **redundant / subsumed** (one fact fully covers the other) → keep the canonical fact and
  **`praxis_reject_fact`** the loser. Rejection drops it from active queries and fires the **stale
  cascade** (`praxis_get_stale_derivations` / `praxis_dependents` flag anything that was built on it).
  Record *why* and a **cross-link** to the canonical fact so the reason lives in the graph, then
  **re-save the `prd-<project>` snapshot**.
- **distinct-but-overlapping** (different primary intents, but one restates a clause of the other) →
  **`praxis_edit_fact`** the overlapping fact to **NARROW** it — strip the duplicated clause so it
  **defers to / references** the canonical fact rather than re-stating it (`edit_fact` requires BOTH
  `title` and `content`). Persist the relationship as a **cross-link in the GRAPH** — a
  `praxis_record_derivation` edge (or a `references` entry in `meta`) — not just in prose, then
  **re-save the snapshot**.
- **genuinely distinct / complementary** (e.g. two real layers of one path, like a re-tap vs an
  offline-sync idempotency rule) → **no graph change**; record the cross-link rationale so a future
  reader knows the overlap was considered and the two were *deliberately* kept.

This is fully consistent with the incremental path's `on_conflict="surface"` (factory-plan Step 2d):
surface keeps both facts pending for the human; here the audit is the cold-eyes actor that *acts on*
the overlap. After any `reject_fact` or `edit_fact`, the `prd-<project>` snapshot must be re-saved or
the durable plan still carries the redundancy.

## Step 2 — Route underspecification (research / default / ask / defer)

When a challenge exposes that a requirement can't carry a *correct, complete* binary acceptance
condition, use `factory-plan`'s underspecification trigger (§2a) — do not paper over it:
1. **Research-resolvable** → dispatch the read-only research sub-agent to find the answer (PRD,
   wireframe, mounted `prd-*`/`constitution`, prior art), then tighten the acceptance condition.
2. **Convention-resolvable** → low-regret default + `praxis_record_episode`, surfaced for override.
3. **Genuine fork** → **ask the human** (batch all such questions — see mode below).
4. **Unknowable now** → deferred owned-decision.

The **anti-masking guard** is the whole point of this step: a plausible-but-shallow acceptance
condition that hides a gap is exactly what mechanical `plan_gate` will wave through. The audit is
where that gets caught — an underspecified area must visibly become research, a question, or a
flagged deferral, never a quiet guess.

## Step 3 — Technical architecture sweep (end-to-end)

Behavioral requirements describe *what* the product does; they routinely leave the *how* — the
cross-cutting technical architecture — unspecified, and a PRD almost never nails it end to end. This
sweep forces every project-wide technical decision to be made explicitly (or consciously deferred),
so the build never quietly invents an architecture nobody chose. (This is the dimension a
requirement-by-requirement audit misses entirely — these are project-level, not per-requirement.)

**Derive the decisions dynamically — there is NO fixed list.** Enumerate the technical decisions
*this* system needs to be buildable, reasoning from the PRD, the admitted requirements, and the
*kind* of software it is. What a web app needs differs from a CLI, an ML/data pipeline, a game, an
embedded device, or a library — never work from a canned checklist.

*Illustrative only* (a typical web app): auth + authz, data store + migrations, backend stack + API
style, frontend framework + styling + build tooling, hosting/deploy + CI + environments,
secrets/config, external services (email/push/storage), testing + the verify oracle, observability,
data-privacy (PII/retention/consent/encryption). **These are prompts, not the list** — an ML service
also needs model hosting/versioning/eval data; a CLI needs packaging/distribution/config; a library
needs its public API surface + semver + release process. Derive the real set for *this* build.

Resolve each like an underspecified requirement (PRD → mounted conventions → low-regret default +
`record_episode` → ask the human → defer) and record it in `techDecisions` with status `resolved`,
`deferred` (owned-decision + reason), or `na` (genuinely not applicable + reason). None may be
silently skipped, and a default may never paper over a genuine owner fork (anti-masking).

### Step 3a — Test strategy is mandatory (derive the layers for THIS system)

A PRD almost never says *how* the product is tested — yet a plan with no test strategy (or one that
skips a layer this platform lives or dies on) is exactly the silent gap mechanical gates wave
through. So an explicit, **platform-appropriate, automated test strategy + CI is a MANDATORY outcome
of every audit**: no project can be blessed on an untested or under-tested plan. Treat it like the
tech sweep — **derive the right set of test LAYERS for THIS system from the PRD, the requirements,
and the *kind* of software it is; there is NO fixed checklist.** A static "unit + integration + e2e"
list is the wrong altitude — the *real* set depends on where this product's risk actually lives.

*Illustrative only* (the layers differ per project kind — derive, don't copy):
- a **library** → unit + public-API/contract tests + semver-aware release CI;
- a **web app** → unit + integration + e2e on the critical flows + CI/CD that gates merges;
- a **MOBILE app** → unit + integration + UI/e2e on a real device or simulator + CI that builds/signs
  the app (the device/simulator layer is the one a generic plan silently omits — and it's load-bearing);
- a **CLI** → unit + integration + a packaging/install smoke test;
- a **data/ML pipeline** → unit + data-contract/schema tests + pipeline integration + eval gates on
  model quality.
These are **prompts, not the list.** Derive the real set for *this* build — the layers, the harness,
and where each runs (local, CI, device farm, simulator).

Record **each chosen layer AND the CI/CD setup** — in `techDecisions` (dimension `testing` / `ci`)
or as first-class requirements — and **every one must carry a BINARY acceptance condition**, the same
bar as any requirement. Examples of the shape (not the content):
- "CI runs the unit+integration suite on every push and **blocks merge on red**";
- "the e2e suite covers the critical user flows on a simulator **in CI** and blocks release on
  failure";
- "the packaging smoke test installs the built artifact in a clean environment in CI."
This strategy is **what factory-verify gates the build on** — factory-verify is the oracle, and the
test strategy is the contract that says *which* automated suites, at *which* layers, must be green
before anything is considered done. A layer with no binary, CI-enforced condition is not a strategy;
it's a hope, and the gate treats it as missing.

**Then run the completeness critic — this is the dynamic pushback you asked for.** Dispatch an
*independent* cold-eyes sub-agent (`factory-execute` §1a) whose only job is: *"to actually build
this system, what technical decisions are still unmade?"* It reads the PRD + requirements + the
current `techDecisions` and names what's missing for **this** product. Add what it surfaces, resolve
those too, and **loop until it returns nothing new** (loop-until-dry). Record the result in
`techDecisionsCritic` `{ran, missingFound, passes}`. This is how the system *finds* the missing
decisions for whatever is being built — rather than checking a static list — and the gate will not
pass until the critic has signed off with nothing missing.

The critic must **explicitly interrogate the test strategy**, not just the build decisions: *"is the
test strategy COMPLETE and APPROPRIATE for THIS platform?"* It derives the layers this kind of
software actually demands and flags any that are absent or unenforced — e.g. a **mobile app with no
device/simulator UI/e2e layer**, a library with no public-API/contract tests, a data pipeline with no
data-contract or eval gates, or **any project with no CI** or with a layer that has no binary,
merge-/release-blocking acceptance condition. Each gap it raises is added and resolved like the
others, and the same **loop-until-dry** applies — the critic does not sign off while a platform-
appropriate layer or the CI gate is missing or unenforced.

## Step 4 — Emit the audit artifact (the gated forcing function)

Write `<project>/.factory/plan-audit.json` — this is what the **Stop-hook gate**
(`hooks/plan_audit_gate.py`) reads and enforces. While `status:"open"`, the gate **blocks the turn
from ending** (so you can't `save_snapshot` and call it hardened) until ALL hold:
- `plan_gate` passes — **the hook re-runs `agent_factory.plan_gate.evaluate_plan` itself**, so the
  acceptance/vague/dangling checks can't be self-graded;
- `contradictionsEmpty: true` — you ran `praxis_get_contradictions` and resolved every pending pair
  (NOTE: if the plan was admitted via the `raw=True` bulk fast-lane, that queue is empty *by
  construction* — detection was skipped — so it is THIS audit's cold-eyes conflict challenges, not the
  empty queue, that are the real contradiction net; say `raw` was used in the artifact);
- every requirement has ≥1 challenge and **no open challenge** (all resolved/dismissed/deferred with
  a recorded resolution); a **near-duplicate / overlap** challenge is only closed once the graph
  reflects it — the loser `reject_fact`ed, or the overlapping fact `edit_fact`-narrowed + cross-linked,
  or explicitly kept-as-distinct with a recorded rationale — and the `prd-<project>` snapshot re-saved
  (a free-text annotation alone does NOT close it);
- rigorous mode: every gap-lens logged for every requirement;
- the **technical decisions** are complete for this system: `techDecisions` is non-empty and every
  entry is closed (resolved / deferred-with-reason / na-with-reason), AND the independent
  `techDecisionsCritic` ran and signed off with nothing missing (`passes: true`, `missingFound: []`);
- the **test strategy** is present and platform-appropriate: a non-empty `testStrategy` whose derived
  layers + the CI/CD setup each carry a **binary, CI-enforced acceptance condition**, and the critic
  confirmed it is complete and appropriate for this kind of software (no missing platform-required
  layer — e.g. a mobile build with no device/simulator e2e — and no project without CI). A plan with
  no test strategy, or with a layer lacking a binary gate, is **under-tested and cannot be blessed**.

```json
{
  "status": "open", "attempts": 0, "max_attempts": 8,
  "project": "prd-team-app", "mode": "rigorous",
  "contradictionsEmpty": false, "out_of_scope": ["..."],
  "requirements": [
    {
      "id": "R1", "text": "...", "acceptance": "...", "source": "prd-team-app",
      "defines": ["completion"], "references": ["daily rep", "ratings"],
      "challenges": [
        {"type": "unhandled-empty-case", "statement": "what if zero ratings submitted?",
         "resolution": "added R1b: a missing rating yields incomplete", "status": "resolved"}
      ],
      "gap_lenses": {"failure-modes": "fired", "security": "pass",
                     "data-lifecycle": "pass", "rollback": "pass", "who-pays": "pass"}
    }
  ],
  "techDecisions": [
    {"dimension": "auth", "decision": "session cookie + email magic-link; roles athlete/captain/coach", "source": "PRD §5 + default", "status": "resolved"},
    {"dimension": "data-store", "decision": "Postgres + standard migrations", "source": "default (PRD silent)", "status": "resolved"}
    // ... however many THIS system needs — dynamically derived, not a fixed list
  ],
  "testStrategy": {
    // layers DERIVED for this system (a web app here) — not a fixed checklist
    "layers": [
      {"layer": "unit", "acceptance": "unit suite runs on every push in CI and blocks merge on red", "status": "resolved"},
      {"layer": "integration", "acceptance": "integration suite (db + api) runs in CI and blocks merge on red", "status": "resolved"},
      {"layer": "e2e", "acceptance": "e2e suite covers the critical user flows and blocks merge on red", "status": "resolved"}
    ],
    "ci": {"decision": "GitHub Actions: build + unit+integration+e2e gate every PR; deploy on green main", "acceptance": "merge is blocked unless all suites are green", "status": "resolved"}
    // a MOBILE build would instead derive a device/simulator UI/e2e layer + a build/sign CI step
  },
  "techDecisionsCritic": {"ran": true, "missingFound": [], "testStrategyComplete": true, "passes": true}
}
```

Keep the manifest current as you work; the gate flips it to `passed` when clean and lets the turn
end. Do not hand-edit `status` to `passed` — let the gate decide.

## Step 5 — Mode-aware human moment, then bless

- **Attended:** present the audit's open challenges, routed-underspecs, and questions as **one
  batched review** (this is the concentrated human moment the review-leverage rule wants — better
  than one-question-per-turn interruptions during drafting). On resolution, the gate passes →
  `save_snapshot("prd-<project>")`.
- **Unattended (Constitution / owner asleep):** don't ask — route forks to deferred owned-decisions,
  `praxis_record_episode` each, drop the audit artifact + the open list in the ledger for morning
  review, and proceed only on what cleared.

## Step 6 — Plan-review (auto, the finalization gate)

Once the plan is **FINALIZED** (the audit gate above passed AND `save_snapshot("prd-<project>")`
landed), **auto-run `factory-review` in PLAN mode** over the finalized `prd-<project>` — the whole
admitted requirement set + `techDecisions`. This is the review-leverage rule's payoff: the highest-
value cold-eyes pass sits on the plan, where one bad requirement is cheapest to catch. The
`review_gate` (`hooks/review_gate.py`, armed by `.factory/review-status.json`) then **blocks
'planning complete' from ending** until the review is either **done with no open findings** or
**skipped-with-reason** — never silently.

Mode-aware, like the rest of this skill:
- **Attended:** run the review as the panel and present its findings as **one batched review**
  (folded into / following Step 5's human moment, not a second round of interruptions). Resolve or
  consciously dismiss each finding before the gate clears.
- **Unattended (owner asleep):** **auto-skip-if-small** — if the plan is below the review heuristic's
  size/risk floor, skip with a recorded reason + `praxis_record_episode` and let the gate pass.
  Otherwise **run** it, and **defer** any open findings as owned-decisions (episode each, drop them
  in the ledger for morning review) rather than blocking — the gate clears on done-or-skipped, but
  every deferral is explicit.

## Never
- Never `save_snapshot` (bless the plan) with the audit `status:"open"` or any open challenge.
- Never let the agent that drafted a requirement be its *only* skeptic — use the cold-eyes sub-agent.
- Never dismiss a challenge without a recorded reason, or default over a genuine product fork.
- Never "close" a near-duplicate / overlap challenge with a free-text note alone — write it back to the
  graph (`reject_fact` the subsumed loser, or `edit_fact`-narrow + cross-link the overlapping fact, or
  keep-as-distinct with a recorded rationale) and **re-save the `prd-<project>` snapshot**. On the
  `raw=True` fast-lane this write-back is the ONLY dedup step — leaving redundant facts active is a leak.
- Never bless a plan with no automated test strategy, a platform-required layer missing (e.g. a
  mobile build with no device/simulator e2e), or any test layer / CI gate lacking a binary condition.
- Never hand-edit the manifest to `passed` — the gate (with its independent `plan_gate` re-run) decides.
