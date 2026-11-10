"""Experiment E1 — A* against the CSP solver on the same Problem objects.

Pair B's solver lives on ``pairB/csp-solver`` and is not on this branch yet.
When ``backend.csp.solve`` cannot be imported, the script still runs A* and
records the CSP columns as unavailable. Both sides are meant to read the
same ``Problem``; that is the comparison ``docs/experiments.md`` asks for.
"""

from __future__ import annotations

import csv
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.astar import AStarConfig, solve  # noqa: E402
from backend.models import Problem  # noqa: E402
from backend.models.planning_problem import assignment_is_valid  # noqa: E402

CORE = "Discipline Core"


def _course(credits, formula=None, parity=None):
    return {
        "credits": credits,
        "category": CORE,
        "parity": parity,
        "formula": formula,
    }


def _pre(code):
    return {"kind": "leaf", "course": code, "relation": "PRE"}


def instances() -> list[tuple[str, Problem]]:
    chain = Problem(
        courses={
            "CS F211": _course(4),
            "CS F212": _course(4, formula=_pre("CS F211")),
            "CS F213": _course(4, formula=_pre("CS F212")),
        },
        current_semester=0,
        target_semester=6,
        max_credits=4,
    )
    short = Problem(
        courses=chain.courses,
        current_semester=0,
        target_semester=2,
        max_credits=4,
    )
    packed = Problem(
        courses={
            "CS F211": _course(4),
            "CS F212": _course(4),
            "CS F213": _course(4),
        },
        current_semester=0,
        target_semester=6,
        max_credits=4,
    )
    parity = Problem(
        courses={"CS F211": _course(3, parity="even")},
        current_semester=0,
        target_semester=4,
        max_credits=20,
    )
    return [
        ("chain3_cap4", chain),
        ("chain3_horizon2", short),
        ("three_independent_cap4", packed),
        ("even_course_from_odd_term", parity),
    ]


def _csp_solve():
    try:
        from backend.csp import solve as csp_solve
        from backend.csp import SolverConfig
    except ImportError:
        return None
    return csp_solve, SolverConfig


def run() -> list[dict]:
    csp = _csp_solve()
    rows: list[dict] = []
    for name, problem in instances():
        astar = solve(problem, AStarConfig(heuristic="composite", timeout_seconds=10))
        valid = bool(astar.assignment) and assignment_is_valid(problem, astar.assignment)
        row = {
            "instance": name,
            "astar_status": astar.status,
            "astar_terms": astar.stats.get("terms_used"),
            "astar_nodes": astar.stats.get("nodes"),
            "astar_time_s": round(astar.stats.get("time_s", 0.0), 6),
            "astar_valid": valid if astar.status == "SAT" else "",
            "csp_status": "unavailable",
            "csp_nodes": "",
            "csp_time_s": "",
        }
        if csp is not None and astar.status != "TIMEOUT":
            csp_solve, solver_config = csp
            csp_result = csp_solve(problem, solver_config())
            row["csp_status"] = csp_result.status
            row["csp_nodes"] = csp_result.stats.get("nodes", "")
            row["csp_time_s"] = round(csp_result.stats.get("time_s", 0.0), 6)
        rows.append(row)
    return rows


def main() -> None:
    rows = run()
    out_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "solver_comparison.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(
            f"{row['instance']}: A* {row['astar_status']} "
            f"terms={row['astar_terms']} nodes={row['astar_nodes']} "
            f"csp={row['csp_status']}"
        )
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
