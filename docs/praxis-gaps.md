# Knowledge-Graph Side: What Praxis Owns, and the Holes to Improve

> First-pass partition. This document covers **only the "knowing" system** — the
> capabilities from [`agent-coding-factory-reference.md`](./agent-coding-factory-reference.md)
> that should live in the knowledge graph because they are about durable, cross-session
> knowledge, retrieval, and truth-maintenance. For each, it marks whether Praxis already
> **covers** it, **partially** covers it, or has a **hole** we'd want to improve on the
> Praxis side. The companion doc [`factory-local-components.md`](./factory-local-components.md)
> covers everything we build locally instead.
>
> Status is graded against the current Praxis doc, not a fresh source audit — step 2's
> research team should confirm the HOLE/PARTIAL calls against `../praxis` before we commit.

---

## The boundary rule

A capability belongs on the **Praxis side** when it is about *knowledge that must outlive a
single session and be reasoned over* — stored facts, how they're retrieved, how they're
deduped/merged, how conflicts are resolved, how they age. It belongs on the **local side**
when it is about *running code, the agent loop, or ephemeral task state*. Code itself is
never KG data (it lives in git); only judgments, decisions, and learnings *about* the code do.

---

## What Praxis already covers well (lean on these, don't rebuild)

| Reference capability | Praxis mechanism | Status |
|---|---|---|
| Persistent cross-session knowledge store | Atomic facts under `(org_id, user_id)` tenancy | ✅ Covers |
| Hybrid retrieval (semantic + exact/keyword) | pgvector + BM25 fused via RRF in `/context` | ✅ Covers |
| Dedup + additive merge of facts | distillation → dedup → Mem0-style merge/augment | ✅ Covers |
| Contradiction detection + resolution | two-stage (structural slot + semantic) engine | ✅ Covers |
| **Gated writes** (don't let contradictions corrupt memory) | invalidate-and-keep + opt-in auto-resolution | ✅ Covers — this is a standout strength |
| Temporal validity / point-in-time recall | bitemporal `valid_at`/`invalid_at` + `as_of` | ✅ Covers |
| Read-time knowledge composition without contamination | mountable read-only snapshot overlays | ✅ Covers |
| Knowledge checkpoint / rollback | snapshots (`save` / `load`) | ✅ Covers |
| Coarse namespace scoping (global vs project) | `shared` flag + per-project principal + mounts | ✅ Covers |
| Per-fact provenance (source/score) | returned on every `/context` hit | ✅ Covers |

This is most of the *knowing* system. The reference model's hardest, least-solved subsystem
(gated memory writes with contradiction detection — the thing commercial products mostly
*don't* ship) is exactly where Praxis is strongest.

---

## The holes — knowledge-side capabilities the reference wants that Praxis lacks or only partially does

These are candidate improvements to **Praxis itself** (or, where noted, things we may have to
shim locally if Praxis can't take them on).

### H1. Outcome / trust feedback on facts — **HOLE**
The reference wants verification outcomes to feed back into fact trust: down-weight or retire
a fact whose suggested action repeatedly *failed*, so retrieval sharpens on what demonstrably
worked (the actual compounding mechanism). Praxis has `state`, `invalid_at`, and
auto-resolution confidence, but no notion of a fact's **outcome/utility score** updated by
downstream success/failure. Without it, the pool grows by volume, not accuracy.
→ *Praxis improvement:* a mutable per-fact trust/utility signal that retrieval can weight on,
updatable via the API.

### H2. Query-time scope/namespace filtering — **PARTIAL / likely HOLE**
Reference: scope retrieval so service A's auth never surfaces service B's payments. Praxis
hits *carry* `scope`/`category`, and mounts/tenancy give coarse partitioning, but it's unclear
`/context` can **constrain** a query to a scope/category server-side (the documented params are
`query`, `top_k`, `as_of`). If not, we over-retrieve and filter client-side.
→ *Praxis improvement:* `scope`/`category` filters on `/context`.

### H3. Automatic temporal decay / staleness expiry — **HOLE**
Memory-safety best practice expires stale entries (Weibull-style decay) to shrink the
poisoning/stale-recall surface. Praxis invalidates facts only via contradiction or explicit
edit — there's no time-based decay or "this learning hasn't been confirmed in N runs, lower
its weight."
→ *Praxis improvement:* optional decay/aging policy on facts.

### H4. Episodic vs. semantic vs. procedural memory types — **PARTIAL**
The reference distinguishes *semantic* (durable facts), *episodic* (a timestamped decision +
its rationale + what happened), and *procedural* (reusable workflow templates). Praxis stores
flat atomic facts; the three types can be faked with `scope`/`category`, but there's no
first-class episodic record ("at plan-time we chose X because Y; it later failed"). `as_of`
helps reconstruct *what was believed*, not *why it was decided*.
→ *Praxis improvement (or local shim):* a first-class episodic/decision record type, or a
documented convention for encoding one in facts + edges.

### H5. Richer typed edges / derivation links — **PARTIAL**
Praxis has `contradiction`, `contradicted_by`, `supersedes`. The reference's compounding loop
wants **derivation provenance**: "learning L was derived from facts F1, F2 + PRD slice S," so
when F1 flips you can find every downstream learning that's now suspect. Current edges don't
express `derived_from` / `fix_resolves_error` / `depends_on`.
→ *Praxis improvement:* arbitrary/typed relation edges between facts, with traversal in the API.

### H6. Ingestion integrity on tabular/templated input — **KNOWN PARTIAL**
The merge path cut the old silent-near-duplicate drop, but tabular input still leaks at **two**
independent points — and our first PRD is tabular-heavy. This is the one hole we already know
bites us. (Full design: [`../../praxis/docs/proposals/2026-06-24-tabular-ingestion-integrity.md`](../../praxis/docs/proposals/2026-06-24-tabular-ingestion-integrity.md).)
- **A — distillation under-emits:** the splitter collapses rows sharing a sentence shape; the
  offline path can't parse tables at all.
- **B — the deduper over-merges siblings:** the `MergeJudge` folds distinct-but-similar rows into
  one fact. Note `/insights` skips A but still hits B.
→ *Praxis improvement:* (1) deterministic table-linearizer; (2) a **dedup slot-guard** keyed on
the full functional `(subject, attribute)` slot from the `claims` table — **not** subject alone
(subject-only fails the same-subject/different-attribute shape, e.g. a role×permission table,
which our PRD has). The guard is a three-way decision: distinct slot → block merge; same slot +
different value → route to contradiction engine; same slot + same value → merge (idempotency).
Missing/empty claim ⇒ demote to `proposed` (fail toward distinct). #1 and #2 must ship together —
#1 alone only makes tables *look* fixed.
→ *Meanwhile* shim locally (table-linearization + rejected-pile audit — see local doc); the
slot-guard (B) **cannot** be shimmed and must land in Praxis.

### H7. Retrieval budget / tier controls — **PARTIAL**
The reference wants per-tier token budgets and the ability to bias semantic-vs-keyword weight
per query type (concept vs symbol). Praxis token-bounds results (~8KB) and fuses via RRF, but
exposes no knobs to tune the fusion or budget per call.
→ *Praxis improvement (nice-to-have):* optional retrieval-tuning params; otherwise we live
with the defaults.

### H8. Bulk write throughput / synchronous read-your-writes — **PARTIAL**
`/ingest` is slow/async (minutes); a just-written learning isn't immediately retrievable.
`/insights` is synchronous and lower-loss, which mitigates this for shaped facts. Not a
correctness hole, but a latency constraint the local loop must design around.
→ *Praxis improvement (nice-to-have):* faster/confirmable writes; *meanwhile* local staging.

### H9. Detect-without-auto-resolve write mode — **RESOLVED (Praxis fix verified 2026-06-25)**
The plan-hardening loop needs contradictions **surfaced for a human**, not silently settled.
Originally `add_insight` auto-resolved every conflict (newest wins, loser → `rejected`, nothing in
`get_contradictions`). **Fixed in Praxis:** `add_insight`/`ingest` now take
`on_conflict="surface" | "auto_resolve"` (default `auto_resolve`). With `surface`, a conflict keeps
both facts (incumbent `active`, newcomer `proposed`, neither rejected) and raises a **pending pair
in `get_contradictions`** settled by `resolve_contradiction`.
- *Verified live:* `retry count is 3` then `...7` with `on_conflict="surface"` → both kept (3 active,
  7 proposed), one pending pair, neither rejected; `resolve_contradiction(keep_id=7)` superseded 3.
- *Consequence:* the earlier rejected-pile workaround is **retired**; `factory-plan`/`factory-memory`
  now use `on_conflict="surface"` + `get_contradictions` as the surface.

### H10. Semantic-contradiction precision — **IMPROVED (Praxis fix verified 2026-06-25)**
The semantic detector over-flagged compatible facts (e.g. "knowledge is stored in the KG" vs "code
is never in the KG"). Tightened in Praxis; the pair now coexists with no contradiction. Eval case
`praxis/.../matt/semantic_no_conflict_storage_target` pins it. *Note:* the conflict-checked write
runs an inline semantic-judge LLM call and can **time out client-side after the write succeeds** —
consumers must read back rather than blind-retry (handled in `factory-memory`).

---

## Summary

- **Praxis covers the core of the knowing system** — and is strongest exactly where the
  reference model says factories are weakest (gated, contradiction-aware writes + temporal
  truth-maintenance).
- **The compounding loop is the main gap cluster:** H1 (outcome→trust), H4 (episodic records),
  and H5 (derivation edges) together are what turn "a store of facts" into "memory that gets
  *more accurate*, not just bigger." If we improve Praxis anywhere, here first.
- **H6 (tabular ingestion) is the one hole that blocks us immediately** and must be shimmed
  locally regardless of whether Praxis improves.
- **H2, H3, H7, H8** are sharpening/ergonomics holes — real, but workable around in the short term.

Step 2's research team should pressure-test each HOLE/PARTIAL against the actual `../praxis`
source and decide, per item: *improve Praxis* vs. *shim locally* vs. *accept the limitation*.
