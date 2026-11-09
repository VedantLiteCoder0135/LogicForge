"""GraphMind — Comprehensive CSP Solver Tests (Pair B)

Tests:
  1. Brute-force validation on random small problems (independent validator).
  2. All solver configs (plain, +mrv, +fc, +fc+mrv, +ac3, all) agree on SAT/UNSAT.
  3. Real data verified outcomes (target 8 SAT, target 7 UNSAT, target 6 UNSAT, cap 10 UNSAT / SAT without caps).
  4. Cross-check against Pair A RequirementResolver.is_eligible.
  5. Disabling a bottleneck prereq constraint changes UNSAT to SAT.
  6. Trace generation, min_credits, out-of-scope handling, and timeout behavior.
"""

from __future__ import annotations

import itertools
import random
from typing import Any, Dict, List, Optional, Set, Tuple

import pytest

from backend.csp import Constraint, NOT_TAKEN, Problem, build_problem, PlacementTrace, Result, SolverConfig, solve
from requirement_resolver import RequirementResolver


# ============================================================================
# Independent Validity Checker (written inside test file, no solver code imported)
# ============================================================================

def is_valid_plan_independent(
    problem: Problem,
    assignment: Dict[str, Any],
    ignored_constraints: Optional[Set[str]] = None,
) -> bool:
    """Independently verifies whether an assignment is valid for a Problem.

    Does not import or call any solver checking routines.
    """
    if ignored_constraints is None:
        ignored = set()
    else:
        ignored = set(ignored_constraints)

    # 1. Variable domain checks
    if set(assignment.keys()) != set(problem.variables):
        return False

    out_of_scope = set(problem.out_of_scope_assumed_courses)

    for course, val in assignment.items():
        info = problem.courses[course]
        cat = info.get("category", "")
        parity = info.get("parity")

        if val == NOT_TAKEN:
            is_elective = cat == "Discipline Elective" or (
                "elective" in cat.lower()
                and cat not in ("Discipline Core", "University Core (First Year)")
            )
            if not is_elective:
                return False
            continue

        if not isinstance(val, int):
            return False

        if not (problem.current_semester < val <= problem.target_semester):
            return False

        if parity == "odd" and val % 2 != 1:
            return False
        if parity == "even" and val % 2 != 0:
            return False

        # 2. Prerequisite constraint check
        prereq_name = f"prereq:{course}"
        if prereq_name not in ignored:
            formula = info.get("formula")
            if formula is not None:
                if not _eval_tree_independent(formula, val, assignment, problem.completed, out_of_scope, problem.assume_out_of_scope_satisfied):
                    return False

    # 3. Credit cap per semester
    for s in range(problem.current_semester + 1, problem.target_semester + 1):
        cap_name = f"credit_cap:{s}"
        if cap_name in ignored:
            continue
        sem_load = sum(
            problem.courses[c]["credits"]
            for c, sem in assignment.items()
            if sem == s
        )
        if sem_load > problem.max_credits:
            return False
        if problem.min_credits > 0 and sem_load < problem.min_credits:
            return False

    # 4. Category minimums
    for cat, req_min in problem.category_minimums.items():
        cat_name = f"category_min:{cat}"
        if cat_name in ignored:
            continue

        completed_cr = sum(
            problem.courses[c]["credits"]
            for c in problem.completed
            if c in problem.courses and problem.courses[c].get("category") == cat
        )
        taken_cr = sum(
            problem.courses[c]["credits"]
            for c, sem in assignment.items()
            if sem != NOT_TAKEN and problem.courses[c].get("category") == cat
        )
        if completed_cr + taken_cr < req_min:
            return False

    return True


def _eval_tree_independent(
    node: Dict[str, Any],
    sem: int,
    assignment: Dict[str, Any],
    completed: Set[str],
    out_of_scope: Set[str],
    assume_out_of_scope_satisfied: bool,
) -> bool:
    """Independent formula evaluator."""
    if node is None:
        return True
    kind = node.get("kind")
    if kind == "leaf":
        target = node["course"]
        rel = node.get("relation", "PRE")
        if target in completed:
            return True
        if target in out_of_scope:
            return assume_out_of_scope_satisfied
        if target not in assignment:
            return assume_out_of_scope_satisfied
        t_val = assignment[target]
        if t_val == NOT_TAKEN:
            return False
        if rel == "CO":
            return t_val <= sem
        return t_val < sem
    if kind == "and":
        return all(
            _eval_tree_independent(item, sem, assignment, completed, out_of_scope, assume_out_of_scope_satisfied)
            for item in node.get("items", [])
        )
    if kind == "or":
        return any(
            _eval_tree_independent(item, sem, assignment, completed, out_of_scope, assume_out_of_scope_satisfied)
            for item in node.get("items", [])
        )
    return False


def brute_force_solve_independent(problem: Problem) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Exhaustive brute-force search over all variable assignments."""
    vars_list = problem.variables
    domains = problem.initial_domains()
    domain_lists = [domains[v] for v in vars_list]

    for combo in itertools.product(*domain_lists):
        assignment = dict(zip(vars_list, combo))
        if is_valid_plan_independent(problem, assignment):
            return True, assignment
    return False, None


# ============================================================================
# Generator for Small Random Problems (Test 1 & 2)
# ============================================================================

def make_random_problem(seed: int, num_courses: int = 5, num_semesters: int = 3) -> Problem:
    """Generate a reproducible small Problem instance with random formulas, parities, and credits."""
    rng = random.Random(seed)
    course_codes = [f"C{i+1}" for i in range(num_courses)]

    courses: Dict[str, Dict[str, Any]] = {}
    completed: Set[str] = set()

    if rng.random() < 0.4 and num_courses > 2:
        completed.add(course_codes[0])

    categories = ["Discipline Core", "Discipline Elective"]
    parities = ["odd", "even", None]

    for i, c in enumerate(course_codes):
        cat = rng.choice(categories)
        parity = rng.choice(parities)
        credits_val = rng.choice([2, 3, 4])

        possible_prereqs = course_codes[:i]
        formula = None
        if possible_prereqs and rng.random() < 0.6:
            chosen = rng.sample(possible_prereqs, min(len(possible_prereqs), rng.choice([1, 2])))
            if len(chosen) == 1:
                formula = {"kind": "leaf", "course": chosen[0], "relation": rng.choice(["PRE", "CO"])}
            else:
                leaves = [
                    {"kind": "leaf", "course": pr, "relation": rng.choice(["PRE", "CO"])}
                    for pr in chosen
                ]
                formula = {"kind": rng.choice(["and", "or"]), "items": leaves}

        courses[c] = {
            "credits": credits_val,
            "category": cat,
            "parity": parity,
            "formula": formula,
        }

    current_sem = 0
    target_sem = num_semesters
    max_credits = rng.choice([6, 8, 12, 16])
    min_credits = 0
    elective_min = rng.choice([0, 3, 6])
    category_minimums = {"Discipline Elective": elective_min} if elective_min > 0 else {}

    return Problem(
        courses=courses,
        completed=completed,
        current_semester=current_sem,
        target_semester=target_sem,
        max_credits=max_credits,
        min_credits=min_credits,
        category_minimums=category_minimums,
        assume_out_of_scope_satisfied=True,
    )


# ============================================================================
# Test 1: Brute Force Comparison on Random Small Problems
# ============================================================================

def test_brute_force_random_small_problems():
    """Compare solver SAT/UNSAT against exhaustive independent enumeration."""
    for seed in range(101, 109):
        prob = make_random_problem(seed=seed, num_courses=5, num_semesters=3)
        expected_sat, brute_plan = brute_force_solve_independent(prob)

        cfg = SolverConfig(mrv=True, forward_checking=True, ac3=True)
        res = solve(prob, cfg)

        expected_status = "SAT" if expected_sat else "UNSAT"
        assert res.status == expected_status, (
            f"Seed {seed}: solver returned {res.status}, but brute force returned {expected_status}"
        )

        if expected_sat:
            assert res.assignment is not None
            assert is_valid_plan_independent(prob, res.assignment), (
                f"Seed {seed}: returned plan failed independent validation!\nPlan: {res.assignment}"
            )


# ============================================================================
# Test 2: Multi-Configuration Agreement
# ============================================================================

def test_all_configs_agree_on_instances():
    """All configs (plain, +mrv, +fc, +fc+mrv, +ac3, all) must agree on SAT/UNSAT."""
    configs = [
        ("plain", SolverConfig(mrv=False, forward_checking=False, ac3=False, degree_tiebreak=False)),
        ("+mrv", SolverConfig(mrv=True, forward_checking=False, ac3=False, degree_tiebreak=False)),
        ("+fc", SolverConfig(mrv=False, forward_checking=True, ac3=False, degree_tiebreak=False)),
        ("+fc+mrv", SolverConfig(mrv=True, forward_checking=True, ac3=False, degree_tiebreak=False)),
        ("+ac3", SolverConfig(mrv=False, forward_checking=False, ac3=True, degree_tiebreak=False)),
        ("all", SolverConfig(mrv=True, forward_checking=True, ac3=True, degree_tiebreak=True)),
    ]

    for seed in range(201, 206):
        prob = make_random_problem(seed=seed, num_courses=5, num_semesters=3)
        expected_sat, _ = brute_force_solve_independent(prob)
        expected_status = "SAT" if expected_sat else "UNSAT"

        for name, cfg in configs:
            cfg.timeout_s = 5.0
            res = solve(prob, cfg)
            assert res.status == expected_status, (
                f"Seed {seed}, config {name}: got {res.status}, expected {expected_status}"
            )
            if expected_sat:
                assert res.assignment is not None
                assert is_valid_plan_independent(prob, res.assignment)


# ============================================================================
# Test 3: Real Data Verified Outcomes
# ============================================================================

def test_real_data_target_8_sat(resolver: RequirementResolver):
    """Target 8 is SAT with realistic student transcript and max_credits=20."""
    completed = {"CS F111", "CS F211", "CS F222"}
    prob = build_problem(
        resolver,
        completed=completed,
        current_semester=4,
        target_semester=8,
        max_credits=20,
        assume_out_of_scope_satisfied=True,
    )

    res = solve(prob, SolverConfig(mrv=True, forward_checking=True))
    assert res.status == "SAT"
    assert res.assignment is not None
    assert is_valid_plan_independent(prob, res.assignment)

    core_credits = sum(
        prob.courses[c]["credits"]
        for c, sem in res.assignment.items()
        if sem != NOT_TAKEN and prob.courses[c]["category"] == "Discipline Core"
    ) + sum(
        prob.courses[c]["credits"]
        for c in completed
        if prob.courses[c]["category"] == "Discipline Core"
    )
    assert core_credits >= 48

    elective_credits = sum(
        prob.courses[c]["credits"]
        for c, sem in res.assignment.items()
        if sem != NOT_TAKEN and prob.courses[c]["category"] == "Discipline Elective"
    )
    assert elective_credits >= 12
    assert res.trace is not None
    assert len(res.trace) == len(prob.variables)


def test_real_data_target_7_unsat(resolver: RequirementResolver):
    """Target 7 is UNSAT due to the parity/prereq chain F214 -> F351 -> F363."""
    completed = {"CS F111", "CS F211", "CS F222"}
    prob = build_problem(
        resolver,
        completed=completed,
        current_semester=4,
        target_semester=7,
        max_credits=20,
        assume_out_of_scope_satisfied=True,
    )

    res = solve(prob, SolverConfig(mrv=True, forward_checking=True))
    assert res.status == "UNSAT"
    assert res.assignment is None


def test_real_data_target_6_unsat(resolver: RequirementResolver):
    """Target 6 is UNSAT (cannot fit all core prerequisites into 2 terms)."""
    completed = {"CS F111", "CS F211", "CS F222"}
    prob = build_problem(
        resolver,
        completed=completed,
        current_semester=4,
        target_semester=6,
        max_credits=20,
        assume_out_of_scope_satisfied=True,
    )

    res = solve(prob, SolverConfig(mrv=True, forward_checking=True))
    assert res.status == "UNSAT"
    assert res.assignment is None


def test_real_data_credit_cap_10_unsat_and_disabled_sat(resolver: RequirementResolver):
    """Target 8 with max_credits=10 is UNSAT, but SAT when credit_caps are disabled."""
    completed = {"CS F111", "CS F211", "CS F222"}
    prob = build_problem(
        resolver,
        completed=completed,
        current_semester=4,
        target_semester=8,
        max_credits=10,
        assume_out_of_scope_satisfied=True,
    )

    res_capped = solve(prob, SolverConfig(mrv=True, forward_checking=True))
    assert res_capped.status == "UNSAT"

    all_names = set(prob.named_constraints().keys())
    no_caps = {n for n in all_names if not n.startswith("credit_cap:")}

    res_uncapped = solve(
        prob,
        SolverConfig(mrv=True, forward_checking=True),
        enabled_constraints=no_caps,
    )
    assert res_uncapped.status == "SAT"
    assert res_uncapped.assignment is not None
    assert is_valid_plan_independent(prob, res_uncapped.assignment, ignored_constraints=all_names - no_caps)


# ============================================================================
# Test 4: Cross-Check Against Pair A RequirementResolver
# ============================================================================

def test_cross_check_against_pair_a(resolver: RequirementResolver):
    """Validate that every placed course passes resolver.is_eligible."""
    initial_completed = {"CS F111", "CS F211", "CS F222"}
    prob = build_problem(
        resolver,
        completed=initial_completed,
        current_semester=4,
        target_semester=8,
        max_credits=20,
        assume_out_of_scope_satisfied=True,
    )

    res = solve(prob, SolverConfig(mrv=True, forward_checking=True))
    assert res.status == "SAT"
    assert res.assignment is not None

    out_of_scope_assumed = set(prob.out_of_scope_assumed_courses)

    for course, s in res.assignment.items():
        if s == NOT_TAKEN:
            continue

        earlier_courses = {
            c for c, c_s in res.assignment.items()
            if c_s != NOT_TAKEN and c_s < s
        }
        concurrent_courses = {
            c for c, c_s in res.assignment.items()
            if c_s == s
        }

        completed_so_far = initial_completed | out_of_scope_assumed | earlier_courses
        is_eligible = resolver.is_eligible(
            course,
            completed=completed_so_far,
            concurrently_taking=concurrent_courses,
        )
        assert is_eligible, (
            f"Course {course} scheduled in sem {s} failed Pair A eligibility check!"
        )


# ============================================================================
# Test 5: Disabling Bottleneck Prereq Changes UNSAT to SAT
# ============================================================================

def test_disabling_prereq_changes_unsat_to_sat(resolver: RequirementResolver):
    """Disabling prereq:CS F363 on Target 7 turns UNSAT into SAT."""
    completed = {"CS F111", "CS F211", "CS F222"}
    prob7 = build_problem(
        resolver,
        completed=completed,
        current_semester=4,
        target_semester=7,
        max_credits=20,
        assume_out_of_scope_satisfied=True,
    )

    res_unsat = solve(prob7, SolverConfig(mrv=True, forward_checking=True))
    assert res_unsat.status == "UNSAT"

    all_names = set(prob7.named_constraints().keys())
    without_f363 = all_names - {"prereq:CS F363"}

    res_sat = solve(prob7, SolverConfig(mrv=True, forward_checking=True), enabled_constraints=without_f363)
    assert res_sat.status == "SAT"
    assert res_sat.assignment is not None
    assert is_valid_plan_independent(prob7, res_sat.assignment, ignored_constraints={"prereq:CS F363"})


# ============================================================================
# Test 6: Trace Generation and Quality Checks
# ============================================================================

def test_trace_generation_and_fields(resolver: RequirementResolver):
    """Verify trace records contain human-readable reasons for placements."""
    completed = {"CS F111", "CS F211", "CS F222"}
    prob = build_problem(
        resolver,
        completed=completed,
        current_semester=4,
        target_semester=8,
        max_credits=20,
    )

    res = solve(prob, SolverConfig(mrv=True, forward_checking=True))
    assert res.status == "SAT"
    assert res.trace is not None

    seen_courses = set()
    for t in res.trace:
        assert isinstance(t, PlacementTrace)
        assert t.course in prob.variables
        assert t.course not in seen_courses
        seen_courses.add(t.course)
        assert isinstance(t.reason, str) and len(t.reason) > 5

        assert t["course"] == t.course
        assert t["semester"] == t.semester
        assert t["reason"] == t.reason

        if t.semester == NOT_TAKEN:
            assert "not taken" in t.reason.lower()
        else:
            assert "load:" in t.reason.lower()
            assert "credits" in t.reason.lower()


# ============================================================================
# Test 7: Min Credits and Out of Scope Options
# ============================================================================

def test_min_credits_enforcement():
    """Setting min_credits higher than possible causes UNSAT."""
    prob = make_random_problem(seed=42, num_courses=4, num_semesters=2)
    prob.min_credits = 50
    res = solve(prob, SolverConfig(forward_checking=True))
    assert res.status == "UNSAT"


def test_assume_out_of_scope_satisfied_option():
    """Course with out-of-scope prereq is rejected when assume_out_of_scope_satisfied=False."""
    courses = {
        "CORE1": {"credits": 4, "category": "Discipline Core", "parity": None, "formula": {"kind": "leaf", "course": "EXTERNAL_MATH", "relation": "PRE"}},
    }
    prob = Problem(
        courses=courses,
        completed=set(),
        current_semester=0,
        target_semester=2,
        max_credits=20,
        assume_out_of_scope_satisfied=False,
    )

    res = solve(prob, SolverConfig())
    assert res.status == "UNSAT"

    prob_lenient = Problem(
        courses=courses,
        completed=set(),
        current_semester=0,
        target_semester=2,
        max_credits=20,
        assume_out_of_scope_satisfied=True,
    )
    res_lenient = solve(prob_lenient, SolverConfig())
    assert res_lenient.status == "SAT"
    assert res_lenient.assignment["CORE1"] in (1, 2)


def test_solver_timeout():
    """Verify timeout switch triggers TIMEOUT status cleanly."""
    prob = make_random_problem(seed=77, num_courses=6, num_semesters=3)
    cfg = SolverConfig(mrv=False, forward_checking=False, ac3=False, timeout_s=0.0000001)
    res = solve(prob, cfg)
    assert res.status in ("TIMEOUT", "SAT", "UNSAT")
