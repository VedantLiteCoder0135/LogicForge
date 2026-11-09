"""GraphMind — Experiment E2: Propagation & Ordering Ablation Study (Pair B)

Measures backtrack count, nodes explored, constraint checks, prunings, and runtime across:
  - plain backtracking
  - +mrv
  - +forward checking
  - +forward checking + mrv
  - +ac3
  - all (MRV + Degree tiebreak + FC + AC-3)

Writes results to experiments/results/csp_ablation.csv and results.csv.
"""

from __future__ import annotations

import csv
import os
import sys
from typing import Any, Dict, List, Tuple

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from backend.csp import Problem, build_problem, Result, SolverConfig, solve
from requirement_resolver import RequirementResolver


def get_ablation_configs(timeout_s: float = 30.0) -> List[Tuple[str, SolverConfig]]:
    return [
        ("plain", SolverConfig(mrv=False, forward_checking=False, ac3=False, degree_tiebreak=False, timeout_s=timeout_s)),
        ("+mrv", SolverConfig(mrv=True, forward_checking=False, ac3=False, degree_tiebreak=False, timeout_s=timeout_s)),
        ("+fc", SolverConfig(mrv=False, forward_checking=True, ac3=False, degree_tiebreak=False, timeout_s=timeout_s)),
        ("+fc+mrv", SolverConfig(mrv=True, forward_checking=True, ac3=False, degree_tiebreak=False, timeout_s=timeout_s)),
        ("+ac3", SolverConfig(mrv=False, forward_checking=False, ac3=True, degree_tiebreak=False, timeout_s=timeout_s)),
        ("all", SolverConfig(mrv=True, forward_checking=True, ac3=True, degree_tiebreak=True, timeout_s=timeout_s)),
    ]


def get_ablation_instances(resolver: RequirementResolver) -> List[Dict[str, Any]]:
    instances = []

    # 1. Real data: baseline feasible (target semester 8)
    p1 = build_problem(resolver, completed={"CS F111", "CS F211", "CS F222"}, current_semester=4, target_semester=8, max_credits=20)
    instances.append({"name": "real_target8_cap20 (SAT)", "problem": p1, "enabled_constraints": None})

    # 2. Real data: infeasible bottleneck (target semester 7)
    p2 = build_problem(resolver, completed={"CS F111", "CS F211", "CS F222"}, current_semester=4, target_semester=7, max_credits=20)
    instances.append({"name": "real_target7_cap20 (UNSAT)", "problem": p2, "enabled_constraints": None})

    # 3. Real data: infeasible short deadline (target semester 6)
    p3 = build_problem(resolver, completed={"CS F111", "CS F211", "CS F222"}, current_semester=4, target_semester=6, max_credits=20)
    instances.append({"name": "real_target6_cap20 (UNSAT)", "problem": p3, "enabled_constraints": None})

    # 4. Real data: infeasible credit cap (max_credits = 10)
    p4 = build_problem(resolver, completed={"CS F111", "CS F211", "CS F222"}, current_semester=4, target_semester=8, max_credits=10)
    instances.append({"name": "real_target8_cap10 (UNSAT)", "problem": p4, "enabled_constraints": None})

    # 5. Real data: credit cap relaxed (enabled_constraints without credit_cap:*)
    all_names = set(p4.named_constraints().keys())
    no_caps = {n for n in all_names if not n.startswith("credit_cap:")}
    instances.append({"name": "real_target8_nocap (SAT)", "problem": p4, "enabled_constraints": no_caps})

    # 6. Variant: 2nd year student
    p6 = build_problem(resolver, completed={"CS F111"}, current_semester=2, target_semester=8, max_credits=20)
    instances.append({"name": "variant_sem2_target8 (SAT)", "problem": p6, "enabled_constraints": None})

    # 7. Variant: Senior with head start
    p7 = build_problem(resolver, completed={"CS F111", "CS F211", "CS F213", "CS F214", "CS F215", "CS F222", "CS F241"}, current_semester=4, target_semester=7, max_credits=20)
    instances.append({"name": "variant_senior_target7 (SAT)", "problem": p7, "enabled_constraints": None})

    # 8. Variant: Freshman attempting degree in 2 terms (infeasible)
    p8 = build_problem(resolver, completed=set(), current_semester=0, target_semester=2, max_credits=20)
    instances.append({"name": "variant_freshman_sem2 (UNSAT)", "problem": p8, "enabled_constraints": None})

    return instances


def run_ablation(timeout_s: float = 30.0) -> List[Dict[str, Any]]:
    print("=" * 80)
    print("GraphMind CSP Solver — Experiment E2 Ablation Study")
    print(f"Per-instance timeout: {timeout_s}s")
    print("=" * 80)

    kb_candidates = [
        os.path.join(_repo_root, "kb_courses.json"),
        os.path.join(_repo_root, "PairA_CurriculumKB", "kb_courses.json"),
    ]
    kb_path = next((p for p in kb_candidates if os.path.exists(p)), "kb_courses.json")

    scope_candidates = [
        os.path.join(_repo_root, "curriculum_scope.json"),
        os.path.join(_repo_root, "PairA_CurriculumKB", "curriculum_scope.json"),
    ]
    scope_path = next((p for p in scope_candidates if os.path.exists(p)), "curriculum_scope.json")

    resolver = RequirementResolver.load(kb_path=kb_path, scope_path=scope_path)

    configs = get_ablation_configs(timeout_s=timeout_s)
    instances = get_ablation_instances(resolver)

    records: List[Dict[str, Any]] = []

    print(f"\nRunning {len(instances)} instances across {len(configs)} configurations...\n")
    header_fmt = "{:<30} {:<10} {:<10} {:<10} {:<10} {:<10} {:<10} {:<10}"
    row_fmt = "{:<30} {:<10} {:<10} {:<10d} {:<10d} {:<10d} {:<10d} {:<10.4f}"

    print(header_fmt.format("Instance", "Config", "Status", "Nodes", "Backtracks", "Checks", "Prunings", "Time(s)"))
    print("-" * 104)

    for inst in instances:
        inst_name = inst["name"]
        prob = inst["problem"]
        enabled = inst["enabled_constraints"]

        for cfg_name, cfg in configs:
            res: Result = solve(prob, cfg, enabled_constraints=enabled)

            record = {
                "instance": inst_name,
                "config": cfg_name,
                "status": res.status,
                "nodes": res.stats["nodes"],
                "backtracks": res.stats["backtracks"],
                "checks": res.stats["constraint_checks"],
                "prunings": res.stats["prunings"],
                "time_s": round(res.stats["time_s"], 4),
            }
            records.append(record)

            print(row_fmt.format(
                inst_name[:30],
                cfg_name,
                res.status,
                res.stats["nodes"],
                res.stats["backtracks"],
                res.stats["constraint_checks"],
                res.stats["prunings"],
                res.stats["time_s"],
            ))

    # Save to experiments/results/csp_ablation.csv and root results.csv
    results_dir = os.path.join(_repo_root, "experiments", "results")
    os.makedirs(results_dir, exist_ok=True)
    out_paths = [
        os.path.join(results_dir, "csp_ablation.csv"),
        os.path.join(_repo_root, "results.csv"),
    ]

    fieldnames = ["instance", "config", "status", "nodes", "backtracks", "checks", "prunings", "time_s"]
    for out_path in out_paths:
        with open(out_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)

    print(f"\nSaved CSV results to: {out_paths[0]}\n")

    print("=" * 80)
    print("SUMMARY: MEAN NODES PER CONFIGURATION")
    print("=" * 80)
    sum_header = "{:<12} {:<14} {:<14} {:<14} {:<14} {:<10}"
    sum_row = "{:<12} {:<14.1f} {:<14.1f} {:<14.1f} {:<14.1f} {:<10.4f}"
    print(sum_header.format("Config", "Mean Nodes", "Mean Backtracks", "Mean Checks", "Mean Prunings", "Mean Time(s)"))
    print("-" * 80)

    for cfg_name, _ in configs:
        cfg_records = [r for r in records if r["config"] == cfg_name]
        mean_nodes = sum(r["nodes"] for r in cfg_records) / len(cfg_records)
        mean_bt = sum(r["backtracks"] for r in cfg_records) / len(cfg_records)
        mean_checks = sum(r["checks"] for r in cfg_records) / len(cfg_records)
        mean_prunings = sum(r["prunings"] for r in cfg_records) / len(cfg_records)
        mean_time = sum(r["time_s"] for r in cfg_records) / len(cfg_records)

        print(sum_row.format(cfg_name, mean_nodes, mean_bt, mean_checks, mean_prunings, mean_time))

    print("=" * 80)
    return records


if __name__ == "__main__":
    run_ablation()
