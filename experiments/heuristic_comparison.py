"""Experiment E3 — ablation of the admissible heuristics.

Runs A* with the credit bound, the critical-path bound, and their
pointwise maximum. Reports nodes expanded and the term-count gap against
the composite run. On these instances the composite heuristic is admissible,
so a gap of zero means that heuristic also found a minimum-term plan.

The learned heuristic is intentionally absent. It is not a lower bound, and
it is a later Pair C slice.
"""

from __future__ import annotations

import csv
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.astar import AStarConfig, solve  # noqa: E402
from experiments.solver_comparison import instances  # noqa: E402

HEURISTICS = ("credit_bound", "critical_path", "composite")


def run() -> list[dict]:
    rows: list[dict] = []
    baselines: dict[str, int | None] = {}
    for name, problem in instances():
        composite = solve(problem, AStarConfig(heuristic="composite", timeout_seconds=10))
        baselines[name] = composite.stats.get("terms_used") if composite.status == "SAT" else None
    for name, problem in instances():
        for heuristic in HEURISTICS:
            result = solve(problem, AStarConfig(heuristic=heuristic, timeout_seconds=10))
            terms = result.stats.get("terms_used") if result.status == "SAT" else None
            baseline = baselines[name]
            if terms is None or baseline is None:
                gap = ""
            else:
                gap = terms - baseline
            rows.append(
                {
                    "instance": name,
                    "heuristic": heuristic,
                    "status": result.status,
                    "terms": "" if terms is None else terms,
                    "nodes": result.stats.get("nodes"),
                    "time_s": round(result.stats.get("time_s", 0.0), 6),
                    "gap_vs_composite": gap,
                }
            )
    return rows


def main() -> None:
    rows = run()
    out_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "heuristic_comparison.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(
            f"{row['instance']} [{row['heuristic']}]: {row['status']} "
            f"terms={row['terms']} nodes={row['nodes']} gap={row['gap_vs_composite']}"
        )
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
