---
name: factory-redo-plan-add-check
description: >
  Insert a planning check into Praxis AND re-open an existing plan to apply it — re-arms factory-audit
  for prd-<project> so the new lens is enforced against the already-admitted requirements. The
  planning-side analog of factory-redo-ticket-add-validation. Use when a "we should have considered X"
  rule must be applied to a plan that's already hardened.
---

# Factory Redo-Plan / Add Planning Check — declare a lens AND re-audit the plan

Same write as `factory-add-planning-check` (the lens goes into Praxis, never a file), plus it
**re-opens the plan** so the audit must address the new lens for the existing requirements — the
planning analog of regressing a ticket.

## Steps
1. **Insert the planning check into Praxis** — exactly as `factory-add-planning-check`
   (`source="planning-checklist"`, `category="check"`, `scope="planning"`, `meta.check_id/angle/
   applies_when`; idempotent on `check_id`).
2. **Re-open the plan-audit** for `prd-<project>`. Re-arm the `factory-audit` Stop-hook: write
   `<project>/.factory/plan-audit.json` with `status="open"`, the current `requirements`
   (re-pulled from the `prd-<project>` snapshot), `mode`, and the **Praxis-sourced `checks[]`** (the
   planning checklist, including the new lens). The gate then **blocks finalization until every check
   — including the new one — is closed-with-evidence** for the plan (`hooks/plan_audit_gate.py` via
   `checklist_gate`).
3. **Report**: the check written + that `prd-<project>`'s plan-audit is re-armed for re-hardening, and
   that a plan run (`factory-audit`) must now close the new lens.

## Never
- **Never write a file holding the check itself** — the lens lives in Praxis; only
  `.factory/plan-audit.json` is touched, to re-arm the gate.
- **Never silently bless** — the re-armed audit must actually close the new lens (resolve it for each
  applicable requirement, or dismiss-with-reason), not annotate it away.
- Never touch a different project's plan, and never build/execute.
