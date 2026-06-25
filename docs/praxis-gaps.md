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
→ *Plan:* folded into the H4 proposal as **Part 2**
([`../../praxis/docs/proposals/2026-06-25-episodic-memory-h4.md`](../../praxis/docs/proposals/2026-06-25-episodic-memory-h4.md))
— an additive `exclude_categories` predicate on `search`/`_where` (`category <> ALL`), `/context`
default-excluding `"episodic"`, with an `include_episodic` override. Red-spec eval:
`praxis/.../matt/context_excludes_episodic`.

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
→ *Plan:* [`../../praxis/docs/proposals/2026-06-25-episodic-memory-h4.md`](../../praxis/docs/proposals/2026-06-25-episodic-memory-h4.md)
— convention (not a new type): an episode = a fact tagged `category="episodic"` + `meta.episode`
{decided_at, alternatives, outcome} + `derived_from` edges (H5). Harness-emitted; kept out of
semantic recall by H2's exclude. Red-spec eval: `praxis/.../matt/episodic_excluded_from_semantic`.
**Edge case to design for:** episodes must be **exempt from the semantic write pipeline** —
no atomization/distillation (store the decision+rationale whole), no dedup/merge, no
contradiction/supersession (an episodic log is append-only/immutable) — and excluded from
write-time recall for semantic writes. A "normal fact" gets all of those transforms, which are
fatal to a decision log (see review).

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
→ *Eval:* `praxis/.../matt/augment_no_merge_distinct_rules` — the **prose analog** of loss-point B,
found live (the admission-rule vs. done-gate-rule planning facts were silently over-merged on seed).
Distinct rules that merely share vocabulary must not be collapsed.

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
is never in the KG"). Tightened in Praxis; the pair now coexists with no contradiction. Eval cases
`praxis/.../matt/semantic_no_conflict_storage_target` **and**
`praxis/.../matt/semantic_no_conflict_distinct_actors` (different-actors variant, found live in
the roles cluster — captain-approval vs. coach-immediate) pin it. *Note:* the conflict-checked
write runs an inline semantic-judge LLM call and can **time out client-side after the write
succeeds** — consumers must read back rather than blind-retry (handled in `factory-memory`); the
latency/timeout itself is tracked in **H13**.

### H11. No "dismiss / keep-both" contradiction resolution — **HOLE (found live 2026-06-25)**
When a surfaced contradiction is a **false positive** (the engine flagged two facts that both
actually hold — e.g. the captain-approval vs. coach-immediate pair, different actors), there is no
non-lossy way to clear it. `resolve_contradiction` offers only `keepId` (supersedes one — loses a
true fact) or `customText` (replaces both with one — forces a lossy merge of two distinct facts).
Neither preserves two distinct, compatible facts.
→ *Praxis improvement:* a `dismiss`/keep-both resolution — `POST /contradictions/{id}/resolve
{"dismiss": true}` — that drops the pending edge and leaves **both** facts `active` (the one
intentional override of FR-005's ≤1-active-contradictor rule, on explicit human judgement).
→ *Test:* pytest red-spec `test_resolve_dismiss_keeps_both_active_and_clears_pending` (belongs in
`knowledge/serve/tests/test_server.py`; needs the local `client` fixture). The precision fix for the
false-positive *class* is H10; H11 is the escape hatch for the residue precision can't eliminate.
→ *Meanwhile (local workaround):* resolve via `customText` that accurately combines the two facts,
or `keepId` one + re-add the other — both lossy; `factory-memory` notes this until H11 lands.

### H12. Write-time metadata not persisted/honored — **HOLE (verified live 2026-06-25)** · keystone prereq
`add_insight` accepts `source`/`scope`/`category` but **does not honor them** (a `/context` hit
comes back with `source: null` after `add_insight(..., source="prd-team-app")`), and there is **no
`meta` arg** at all. Per the docs, `scope`/`category` are "derived during ingestion," not settable
by the writer. This blocks three things at once:
- **Provenance citation** (the factory must cite which fact grounded a decision — needs `source`).
- **H2** (exclude by `category`) and **H4** (tag episodes `category="episodic"` + `meta.episode`)
  both *assume* the writer can set `category`/`meta` — they are **blocked on H12**.
**To build (no schema change — `facts` already has `source`/`scope`/`category`/`meta` columns):**
1. **Persist writer-supplied `source`/`scope`/`category`** on the write paths (`POST /insights`,
   `POST /ingest`, MCP `praxis_add_insight`/`praxis_ingest`) into the existing columns, and
   **return them** on `/context` hits and `/candidates` (today they come back null).
2. **Accept a `meta` (jsonb) arg** on the same paths → persist to the `meta` column → return it
   (on `/candidates` at minimum; see open question on `/context`).
3. **Precedence:** writer-set value **wins**; ingestion-derived `scope`/`category` fill in **only
   when the writer left the field unset** (never clobber an explicit tag — H4's `"episodic"` tag
   depends on this).
4. **Round-trip contract (the whole point):** a value written is the value read back, unchanged.

**Blocks:** H2 (filter by `category`) and H4 (episode tag `category="episodic"` + `meta.episode`)
both assume settable `category`/`meta`; both are **blocked until H12 lands**. Do this first.
→ *Eval:* pytest red-spec `test_insight_persists_writer_metadata` in
`knowledge/serve/tests/test_server.py` (`case.yaml`'s `direct_to_graph` is plain strings — can't
set per-fact metadata, so this must be a write-path round-trip test):
```python
def test_insight_persists_writer_metadata(client):
    r = client.post("/insights", json={
        "insight": "The team day resets at 03:00 local time.",
        "source": "prd-team-app", "scope": "prd-team-app",
        "category": "requirement", "meta": {"requirement_id": "R4"}})
    assert r.status_code == 200, r.text
    hit = next(h for h in client.get("/context", params={"query": "team day reset"}).json()["hits"]
               if "03:00" in h["text"])
    assert hit["source"] == "prd-team-app"          # RED today: null
    assert hit["scope"] == "prd-team-app"
    assert hit["category"] == "requirement"
    cand = next(c for c in client.get("/candidates").json() if "03:00" in c["content"])
    assert cand.get("meta", {}).get("requirement_id") == "R4"
```
→ *Open questions:* (a) return `meta` on every `/context` hit or only `/candidates`? (lean:
`source`/`scope`/`category` on hits as today's keys, `meta` on `/candidates` to keep `/context`
lean). (b) writer-vs-derived `category` precedence (lean: writer always wins, derived fills unset).

### H13. Write-path reliability under load — **HOLE (hit repeatedly 2026-06-25)**
Three operational failures hit live during the dry-run, all on the conflict-checked write path:
1. **Client-side timeouts:** a write that triggers the inline semantic-judge LLM call routinely
   times out at the MCP client *after the write has already committed server-side* — a false
   negative that invites duplicate retries.
2. **Write-burst fragility:** ~3–8 concurrent `add_insight` calls drove the backend to 500 on all
   writes (then reads), needing a restart.
3. **Org-membership not durable across restart:** after a backend restart / token refresh,
   membership in a created org vanished (`whoami` showed none), forcing org re-creation.
**To build (each independent):**
1. **Timeout** — raise the MCP write-path HTTP-client timeout to cover the inline semantic-judge
   round-trip (≥60–120s, matching the `/ingest` guidance), ideally **per-call** (long for
   writes/ingest, short for reads). *Stretch:* make conflict-checking async so writes return fast
   and the pending contradiction surfaces shortly after — bigger change; defer unless the bump is
   insufficient.
2. **Concurrency** — the conflict-checked write path must tolerate concurrent writers without
   cascading 500s; investigate connection-pool exhaustion / a transaction left open under load.
   Minimum bar: a failing write fails *cleanly*, not poisoning the backend for unrelated requests.
3. **Membership durability** — org membership must survive a backend restart / token refresh
   (persisted, not in-memory). Re-creating the org on every restart is untenable for a factory
   that depends on durable snapshots (`planning-knowledge`, `prd-*`) living in that org.
→ *Not eval-able as `case.yaml`* (infra/latency/concurrency/persistence, not a graph-state
   assertion) — these want a concurrency stress test (1,2) and a restart-survival integration test (3).
→ *Priority:* **H13.1 (timeout)** next after H12 — most disruptive day-to-day. **H13.3
   (membership)** before we rely on durable snapshots (M2). **H13.2 (concurrency)** lowest — the
   local interim below mitigates it.
→ *Meanwhile (local, in control):* `factory-memory` mandates **serial** conflict-checked writes
   (never parallel bursts) + **read-back-and-re-add on timeout** (a timeout ≠ failure; the write
   usually committed — read back and only re-add if absent, never blind-retry).

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
- **Smoke testing (2026-06-25) surfaced a write-path cluster:** **H9** (surface-mode conflicts) and
  **H10** (semantic-contradiction precision) are **RESOLVED + verified**. Still **to build**:
  **H12** (writer metadata — the *keystone*; H2 and H4 are blocked on it, so do it first),
  **H11** (dismiss/keep-both resolution), and **H13** (write-path reliability: timeout, concurrency,
  membership durability). H11–H13 are detailed enough to code from in-place above; H12/H13 have no
  separate proposal by design.

Step 2's research team should pressure-test each HOLE/PARTIAL against the actual `../praxis`
source and decide, per item: *improve Praxis* vs. *shim locally* vs. *accept the limitation*.
