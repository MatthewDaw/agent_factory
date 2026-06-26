---
name: factory-audit
description: >
  The separate cold-eyes judgment audit that runs AFTER factory-plan admits requirements and
  BEFORE the plan is blessed (save_snapshot). It adversarially challenges every admitted
  requirement, detects and routes underspecification, and checks cross-requirement gaps — the
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

## Step 3 — Emit the audit artifact (the gated forcing function)

Write `<project>/.factory/plan-audit.json` — this is what the **Stop-hook gate**
(`hooks/plan_audit_gate.py`) reads and enforces. While `status:"open"`, the gate **blocks the turn
from ending** (so you can't `save_snapshot` and call it hardened) until ALL hold:
- `plan_gate` passes — **the hook re-runs `agent_factory.plan_gate.evaluate_plan` itself**, so the
  acceptance/vague/dangling checks can't be self-graded;
- `contradictionsEmpty: true` — you ran `praxis_get_contradictions` and resolved every pending pair;
- every requirement has ≥1 challenge and **no open challenge** (all resolved/dismissed/deferred with
  a recorded resolution);
- rigorous mode: every gap-lens logged for every requirement.

```json
{
  "status": "open", "attempts": 0, "max_attempts": 8,
  "project": "prd-team-app", "mode": "rigorous",
  "contradictionsEmpty": false, "out_of_scope": ["..."],
  "requirements": [
    {
      "id": "R1", "text": "...", "acceptance": "...",
      "defines": ["completion"], "references": ["daily rep", "ratings"],
      "challenges": [
        {"type": "unhandled-empty-case", "statement": "what if zero ratings submitted?",
         "resolution": "added R1b: a missing rating yields incomplete", "status": "resolved"}
      ],
      "gap_lenses": {"failure-modes": "fired", "security": "pass",
                     "data-lifecycle": "pass", "rollback": "pass", "who-pays": "pass"}
    }
  ]
}
```

Keep the manifest current as you work; the gate flips it to `passed` when clean and lets the turn
end. Do not hand-edit `status` to `passed` — let the gate decide.

## Step 4 — Mode-aware human moment, then bless

- **Attended:** present the audit's open challenges, routed-underspecs, and questions as **one
  batched review** (this is the concentrated human moment the review-leverage rule wants — better
  than one-question-per-turn interruptions during drafting). On resolution, the gate passes →
  `save_snapshot("prd-<project>")`.
- **Unattended (Constitution / owner asleep):** don't ask — route forks to deferred owned-decisions,
  `praxis_record_episode` each, drop the audit artifact + the open list in the ledger for morning
  review, and proceed only on what cleared.

## Never
- Never `save_snapshot` (bless the plan) with the audit `status:"open"` or any open challenge.
- Never let the agent that drafted a requirement be its *only* skeptic — use the cold-eyes sub-agent.
- Never dismiss a challenge without a recorded reason, or default over a genuine product fork.
- Never hand-edit the manifest to `passed` — the gate (with its independent `plan_gate` re-run) decides.
