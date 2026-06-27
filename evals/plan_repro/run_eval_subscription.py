"""Run the plan-reproduction eval on the logged-in Claude SUBSCRIPTION (no API key).

Same wiring as run_eval._main but with the `claude` CLI backend (claude_cli.make_claude_cli_complete)
for BOTH the planner-under-test and the coverage judge/refuter. Loads the repo .env so the eval's
Praxis space lifecycle (praxis_source) authenticates with PRAXIS_BASE_URL/PRAXIS_API_KEY.

If a previously-planned candidate (team-app/candidate-subscription.yaml) exists, it is SCORED
directly (no re-provision / no re-plan). Delete that file to force a fresh plan.

    python -m evals.plan_repro.run_eval_subscription
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _load_dotenv(root: Path) -> None:
    env = root / ".env"
    if not env.is_file():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def main() -> int:
    # Force UTF-8 stdout/stderr so feature text with chars like U+2265 ('≥') never crashes a
    # Windows cp1252 console.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass

    root = Path(__file__).resolve().parents[2]  # agent_factory/
    _load_dotenv(root)
    praxis_repo = root.parent / "praxis"
    if praxis_repo.is_dir():
        sys.path.insert(0, str(praxis_repo))

    from evals.plan_repro.claude_cli import make_claude_cli_complete
    from evals.plan_repro.coverage import (
        lexical_related_query, load_candidate, load_golden, run_coverage,
    )
    from evals.plan_repro.llm_evaluator import make_llm_evaluator, make_llm_refuter
    from evals.plan_repro.planner import DEFAULT_GOLDEN, load_prd, produce_candidate, save_candidate

    here = Path(__file__).resolve().parent
    out_path = here / "team-app" / "candidate-subscription.yaml"
    complete = make_claude_cli_complete()  # subscription-backed Complete
    print("backend: claude CLI (subscription)", flush=True)

    if out_path.is_file():
        candidate = load_candidate(str(out_path))
        print(f"SCORING existing candidate ({len(candidate)} features) -> {out_path}", flush=True)
    else:
        from evals.plan_repro.praxis_source import (
            provision_and_load_checklist, teardown_eval_space,
        )
        provisioned = False
        try:
            checklist = provision_and_load_checklist()
            provisioned = True
            print(f"provisioned eval space + loaded {len(checklist)} planning check(s)", flush=True)
            candidate = produce_candidate(complete, load_prd(), checklist=checklist)
            save_candidate(candidate, str(out_path), project="team-app")
            print(f"PLANNED {len(candidate)} features -> {out_path}", flush=True)
        finally:
            if provisioned:
                teardown_eval_space()
                print("torn down eval space", flush=True)

    for i, feat in enumerate(candidate, 1):
        t = getattr(feat, "text", None) or (feat.get("title") if isinstance(feat, dict) else str(feat))
        sev = getattr(feat, "severity", "")
        print(f"  [{i:02d}] {t}", flush=True)

    golden = load_golden(str(DEFAULT_GOLDEN))
    print(f"\nscoring {len(candidate)} candidate vs {len(golden)} golden features ...", flush=True)
    report = run_coverage(
        golden, candidate, lexical_related_query,
        make_llm_evaluator(complete), refuter=make_llm_refuter(complete),
    )
    print(report.format(), flush=True)
    print(f"\nPASSED: {report.passed}", flush=True)
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
