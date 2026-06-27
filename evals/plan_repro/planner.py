"""The planner-under-test — produces a candidate plan from the raw PRD, to score for holes.

See ``docs/coverage-spine/03-eval-agent.md`` / ``02-planner.md``. The plan-reproduction eval
needs a *controllable* planner so it can measure the hole rate and A/B the planning checklist:

- **baseline** (`checklist=None`): plan straight from the PRD prose.
- **treatment** (`checklist=` the planning checklist loaded from Praxis): apply general lenses.

The delta in `derived`-feature holes between the two is the meta-proof that the checklist
closes holes. This is a deliberately controllable proxy for the production gated planner
(`factory-intake`/`factory-plan`), not a replacement — it isolates one variable (the checklist).

The checklist is NOT hard-coded here: it is loaded from the Praxis knowledge graph at
execution time (see :mod:`evals.plan_repro.praxis_source`), so the eval relies on Praxis as the
single source of truth — never a private copy of the checks. Like :mod:`llm_evaluator`, the
model is injected as ``Complete = (prompt) -> text`` so this is testable without a network.

IMPORTANT: the Praxis checklist is **general lenses** ("apps with auth need credential
recovery"), NOT the golden feature list. It encodes reusable engineering knowledge; applying
it to *this* PRD is what should surface the password-reset / consent / empty-state features.
The golden is the answer key (for scoring only); the checklist must never be the answer key.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import yaml

from evals.plan_repro.coverage import Feature

#: Same contract as the evaluator's backend.
Complete = Callable[[str], str]

_REPO_ROOT = Path(__file__).resolve().parents[2]
#: The raw PRD set the planner reproduces from.
DEFAULT_PRD_DIR = _REPO_ROOT / "docs" / "inspiration"
DEFAULT_GOLDEN = Path(__file__).resolve().parent / "team-app" / "golden-features.yaml"

# The planning checklist is NOT defined here — it lives in Praxis and is loaded at execution
# time via evals.plan_repro.praxis_source.load_planning_checklist(). Keeping a copy in code
# would defeat the point (the eval must rely on Praxis as the single source of truth).


# --- PRD loading ---------------------------------------------------------------


def load_prd(paths: list[str | Path] | None = None) -> str:
    """Read + concatenate the PRD docs (default: every ``*.txt`` in docs/inspiration/)."""
    if paths is None:
        files = sorted(DEFAULT_PRD_DIR.glob("*.txt"))
    else:
        files = [Path(p) for p in paths]
    chunks = []
    for f in files:
        chunks.append(f"===== {f.name} =====\n{f.read_text(encoding='utf-8')}")
    return "\n\n".join(chunks)


# --- prompt --------------------------------------------------------------------


def build_planner_prompt(prd_text: str, *, checklist: list[str] | None = None) -> str:
    """Build the 'enumerate the complete feature set' prompt for the planner-under-test."""
    lens_block = ""
    if checklist:
        lenses = "\n".join(f"  - {c}" for c in checklist)
        lens_block = (
            "\n\nApply EACH of these general engineering considerations and include any "
            "feature they imply for THIS product (only if the product warrants it):\n"
            f"{lenses}\n"
        )
    return (
        "You are the planner for a software factory. From the product docs below, enumerate "
        "the COMPLETE feature set needed to ship a production-ready MVP (plus any clearly "
        "post-MVP features the docs imply).\n\n"
        "Output one atomic feature per item — a single capability or behavior, phrased like a "
        "requirement (e.g. 'a user can reset their password via an emailed link'). Be "
        "exhaustive: think past the happy path to recovery flows, permissions, states, "
        "admin tooling, and edge cases a contractor would otherwise miss."
        f"{lens_block}\n"
        "PRODUCT DOCS:\n"
        f"{prd_text}\n\n"
        'Respond with JSON only: a list of {"id":"R1","text":"<feature>","scope":"mvp|post-mvp"}.'
    )


# --- parsing -------------------------------------------------------------------


def _loads_lenient(text: str):
    """Parse the first top-level JSON value (array or object) out of model text."""
    if not text:
        return None
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s).strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    starts = [p for p in (s.find("["), s.find("{")) if p != -1]
    if not starts:
        return None
    start = min(starts)
    open_ch = s[start]
    close_ch = "]" if open_ch == "[" else "}"
    depth = 0
    for i in range(start, len(s)):
        if s[i] == open_ch:
            depth += 1
        elif s[i] == close_ch:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(s[start : i + 1])
                except Exception:
                    return None
    return None


def parse_candidate(raw: str | list | dict) -> list[Feature]:
    """Parse a planner response into candidate :class:`Feature` items (tolerant)."""
    obj = raw if isinstance(raw, (list, dict)) else _loads_lenient(raw)
    if isinstance(obj, dict):
        items = obj.get("features") or obj.get("requirements") or []
    elif isinstance(obj, list):
        items = obj
    else:
        items = []
    out: list[Feature] = []
    for i, it in enumerate(items):
        if isinstance(it, str):
            out.append(Feature(id=f"C{i}", text=it.strip()))
        elif isinstance(it, dict):
            text = str(it.get("text", it.get("feature", ""))).strip()
            meta = {k: v for k, v in it.items() if k not in ("id", "text", "feature")}
            out.append(Feature(id=str(it.get("id", f"C{i}")), text=text, meta=meta))
    return [f for f in out if f.text]


def produce_candidate(
    complete: Complete, prd_text: str, *, checklist: list[str] | None = None
) -> list[Feature]:
    """Run the planner-under-test: PRD (+ optional checklist) -> candidate feature list."""
    raw = complete(build_planner_prompt(prd_text, checklist=checklist))
    return parse_candidate(raw)


# --- persistence ---------------------------------------------------------------


def save_candidate(features: list[Feature], path: str | Path, *, project: str = "") -> None:
    """Write a candidate plan in the shape :func:`coverage.load_candidate` reads."""
    payload = {
        "project": project,
        "features": [
            {"id": f.id, "text": f.text, **({"meta": f.meta} if f.meta else {})}
            for f in features
        ],
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
