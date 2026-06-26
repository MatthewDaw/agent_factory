---
name: factory-wireframe
description: >
  Turn a PRD into complete, clickable HTML wireframe(s) in one shot. Use when the human says
  "build a wireframe for this PRD", "wireframe this", or points at a spec/PRD and wants to see
  the screens. The skill reads EVERY source doc, extracts every requirement AND the implied app
  states, splits distinct user personas into separate apps, generates navigable inert HTML, and
  SELF-AUDITS coverage against the PRD before reporting — so the human does not have to say
  "did you check the PRD?" or hand back missing features.
---

# Factory Wireframe

Produce a **feature-complete, clickable, inert** wireframe from a PRD with a single instruction.
The human should never have to repeat "review the PRD" or list missing features — completeness
is the skill's job, enforced by a mandatory self-audit (Step 4). Sessions where the human had to
make corrections like "you missed X", "that's two apps", "check the PRD again" are the failures
this skill exists to prevent.

## Operating rules (non-negotiable)

- **Read EVERY source, in full — never from memory or one file.** A PRD is usually several docs
  (e.g. a requirements list + a developer spec + a flow sketch). Discover them all
  (`ls`/glob the PRD folder), read each completely. The most detailed doc (acceptance criteria,
  data model, API) is authoritative; reconcile the others against it.
- **Clickable but inert.** Screens navigate like a real app (links/tabs/back), but every action
  button is a no-op (a tiny "(prototype)" toast) — no fetch, no backend, no commands.
- **Self-contained.** Each wireframe is one standalone `.html` (embedded CSS+JS), openable via
  `file://` with no build step.
- **Low-fidelity but real.** Wireframe aesthetic (greys, dashed inputs, requirement tags), not
  final visual design — but real layout and real navigation.

## Step 1 — Ingest the whole PRD

1. Locate the PRD: the path the human named, else search `docs/inspiration/`, `docs/`,
   `docs/brainstorms/` for spec/requirements/PRD files. **List the directory** and read **every**
   matching doc in full. Do not stop at the first file.
2. Note the authoritative doc (the one with acceptance criteria / data model / endpoints).

## Step 2 — Build the requirement inventory (exhaustive)

Extract a checklist of EVERY discrete thing the wireframe must show. Always sweep these
categories — most "you missed X" misses come from skipping one:

- **Personas / roles** — and **split distinct personas into separate apps.** If two user types
  have fundamentally different jobs (e.g. a player vs a coach/admin), they are **two apps sharing
  an entry point**, not one app with toggles. Decide this explicitly.
- **Per-persona screens** — one row per screen each role needs.
- **Every functional block / section** the PRD names (each becomes UI).
- **Auth & onboarding** — sign-up, **log in (returning user)**, **invite/redeem + invalid-code
  error**, **consent (minors)**, **disclaimers** ("not therapy", terms/privacy) — these are
  easy to forget and often "non-negotiable" in the PRD's privacy section.
- **Data-model entities** — for each, which screen surfaces or edits it (incl. options/config
  like `options_json`, thresholds, timezones).
- **Admin / config / scheduling** — content editors AND a **scheduler** if the PRD mentions
  scheduling ("schedule prompts/messages for dates"); settings/toggles from the data model.
- **Notifications** — each reminder type + a settings screen to configure them.
- **Metrics / dashboards** — every named metric, plus trend/distribution/per-entity views.
- **Implied app states** (the PRD implies these even if it doesn't draw them — include them):
  **empty, loading, error, offline/queued-sync, success/completed/locked, "not set" fallback,
  validation/"what's missing"**. Acceptance criteria like "shows existing submission state" or
  "returns error listing missing components" are implied states — wireframe them.
- **Privacy/safety** — what each role may/may not see; audit trails; moderation.
- **Post-MVP** — only when the human asks for it; if included, badge it clearly as `post-MVP`.

Write the inventory down (a list/table). It is the contract Step 4 audits against.

## Step 3 — Generate the wireframe(s)

- **One file per app/persona.** A persona whose PRD context is mobile (athlete/player) gets a
  **mobile-responsive** layout (full-screen on a phone via `100dvh` + safe-area, framed mockup
  only on desktop, bottom tab bar). A desktop/console persona (coach/admin) gets a sidebar
  layout. Shared entry point concept, separate files.
- Navigation: tabs / sidebar / back-links wired with a tiny show-hide router; non-nav detail
  screens (e.g. a message thread) reachable from their list and guarded so they don't break nav.
- Mark each implied state and each post-MVP item with a visible tag.

## Step 4 — SELF-AUDIT coverage (mandatory — do NOT skip, do NOT claim done without it)

This is the step whose absence caused the repeated "check the PRD again." Before reporting:

1. **Re-read the PRD docs once more** against the inventory — add anything you missed.
2. **Mechanically verify** each inventory item appears in a wireframe: grep the file(s) for a
   marker per item; confirm every navigation target resolves to a real screen (no dead links).
   Iterate — fix gaps — until **every** inventory item is present and reachable.
3. Produce a **coverage table** mapping each PRD requirement (cite its id/section) → the
   screen(s) it appears on, including the implied states. If anything is intentionally out
   (e.g. post-MVP not requested, or pure backend mechanics with no screen), say so explicitly
   with the reason — never silently drop it.
4. Only after the audit passes do you report. The report leads with the coverage result, not a
   claim of completeness — show the mapping that proves it.

## Step 5 — Handoff

- Save the file(s) in the project (e.g. the app repo root); offer a `file://` link.
- Report: the apps produced, the coverage table, any genuine open product questions (ask the
  human only about real forks — not things the PRD already answers), and what's out-of-scope
  with reasons.

## Anti-patterns (the exact failures to never repeat)

- Building from memory or a single PRD file → **read them all**.
- One app with role toggles when the roles are really separate products → **split into apps**.
- Drawing only the happy path → **include empty/error/offline/completed/fallback states**.
- Approval/queue UI for an actor that doesn't propose anything → model the **actual** workflow
  the PRD describes (e.g. coach schedules/posts; approval only where the PRD says approval).
- Buttons that run real logic → **inert prototype only**.
- Saying "this covers everything" without the Step-4 audit → **prove it with the coverage
  table**; let the audit, not optimism, decide done.

## Compounding

When a human correction reveals a class of miss (a forgotten state, a persona split, a whole
section), add it to the relevant Step-2 category here (and record a `factory-memory` learning)
so the next wireframe starts from a stricter checklist.
