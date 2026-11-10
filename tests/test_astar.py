"""A* planner and admissible-heuristic tests (Pair C)."""

from __future__ import annotations

import itertools
import math
import random

from backend.astar import AStarConfig, composite, credit_bound, critical_path, solve
from backend.models import NOT_TAKEN, Problem, assignment_is_valid

CORE = "Discipline Core"
ELECTIVE = "Discipline Elective"


def _course(credits, category=CORE, parity=None, formula=None):
    return {
        "credits": credits,
        "category": category,
        "parity": parity,
        "formula": formula,
    }


def _pre(code):
    return {"kind": "leaf", "course": code, "relation": "PRE"}


def _co(code):
    return {"kind": "leaf", "course": code, "relation": "CO"}


def _chain_problem():
    """A -> B -> C, one course per term because each is 4 credits and the cap is 4."""
    return Problem(
        courses={
            "CS F211": _course(4),
            "CS F212": _course(4, formula=_pre("CS F211")),
            "CS F213": _course(4, formula=_pre("CS F212")),
        },
        current_semester=0,
        target_semester=6,
        max_credits=4,
    )


def _locally_valid(problem: Problem, assignment: dict) -> bool:
    """Independent of ``assignment_is_valid``. Used to cross-check the model."""
    if set(assignment) != set(problem.variables):
        return False
    for code, value in assignment.items():
        info = problem.courses[code]
        elective = info["category"] == ELECTIVE or (
            "elective" in info["category"].lower()
            and info["category"] not in {CORE, "University Core (First Year)"}
        )
        if value == NOT_TAKEN:
            if not elective:
                return False
            continue
        if not isinstance(value, int):
            return False
        if not (problem.current_semester < value <= problem.target_semester):
            return False
        parity = info.get("parity")
        if parity == "odd" and value % 2 != 1:
            return False
        if parity == "even" and value % 2 != 0:
            return False
        if not _formula_ok(problem, info.get("formula"), value, assignment):
            return False
    graduation_semester = max(
        (val for val in assignment.values() if isinstance(val, int)),
        default=problem.current_semester,
    )
    for semester in range(problem.current_semester + 1, problem.target_semester + 1):
        load = sum(
            problem.courses[code]["credits"]
            for code, value in assignment.items()
            if value == semester
        )
        if load > problem.max_credits:
            return False
        if semester <= graduation_semester:
            if problem.min_credits > 0 and load < problem.min_credits:
                return False
    for category, minimum in problem.category_minimums.items():
        earned = 0
        for code, info in problem.courses.items():
            if info.get("category") != category:
                continue
            taken = code in problem.completed or (
                code in assignment and assignment[code] != NOT_TAKEN
            )
            if taken:
                earned += info["credits"]
        if earned < minimum:
            return False
    return True


def _formula_ok(problem, formula, semester, assignment) -> bool:
    if formula is None:
        return True
    kind = formula.get("kind")
    if kind == "leaf":
        target = formula["course"]
        if target in problem.completed:
            return True
        if target in assignment:
            value = assignment[target]
            if value == NOT_TAKEN:
                return False
            if formula.get("relation") == "CO":
                return value <= semester
            return value < semester
        if target not in problem.courses:
            return problem.assume_out_of_scope_satisfied
        return False
    if kind == "and":
        return all(
            _formula_ok(problem, child, semester, assignment)
            for child in formula.get("items", [])
        )
    if kind == "or":
        return any(
            _formula_ok(problem, child, semester, assignment)
            for child in formula.get("items", [])
        )
    return False


def _term_cost(problem: Problem, assignment: dict) -> int:
    semesters = [value for value in assignment.values() if isinstance(value, int)]
    if not semesters:
        return 0
    return max(semesters) - problem.current_semester


def _brute_optimal(problem: Problem):
    domains = problem.initial_domains()
    variables = problem.variables
    best = None
    for combo in itertools.product(*(domains[code] for code in variables)):
        assignment = dict(zip(variables, combo))
        local = _locally_valid(problem, assignment)
        shared = assignment_is_valid(problem, assignment)
        assert local == shared, assignment
        if not local:
            continue
        cost = _term_cost(problem, assignment)
        if best is None or cost < best:
            best = cost
    return best


def _tiny_problem(seed: int) -> Problem:
    rng = random.Random(seed)
    codes = ["CS F211", "CS F212", "CS F213"]
    courses = {}
    for index, code in enumerate(codes):
        category = rng.choice([CORE, ELECTIVE])
        parity = rng.choice(["odd", "even", None])
        formula = None
        earlier = codes[:index]
        if earlier and rng.random() < 0.7:
            formula = _pre(rng.choice(earlier))
        courses[code] = _course(rng.choice([3, 4]), category, parity, formula)
    return Problem(
        courses=courses,
        current_semester=0,
        target_semester=4,
        max_credits=8,
        category_minimums={},
    )


def test_credit_bound_packs_independent_cores():
    problem = Problem(
        courses={
            "CS F211": _course(4),
            "CS F212": _course(4),
            "CS F213": _course(4),
        },
        current_semester=0,
        target_semester=6,
        max_credits=4,
    )
    assert credit_bound(problem, {}, 1) == 3
    assert critical_path(problem, {}, 1) == 1
    assert composite(problem, {}, 1) == 3


def test_critical_path_counts_prerequisite_chain():
    problem = _chain_problem()
    assert critical_path(problem, {}, 1) == 3
    assert credit_bound(problem, {}, 1) == 3
    assert composite(problem, {}, 1) == max(
        credit_bound(problem, {}, 1), critical_path(problem, {}, 1)
    )


def test_critical_path_adds_a_wait_when_the_next_term_has_the_wrong_parity():
    problem = Problem(
        courses={"CS F211": _course(3, parity="even")},
        current_semester=0,
        target_semester=4,
        max_credits=20,
    )
    # Next open term is 1 (odd). The course itself is one term, plus one wait.
    assert critical_path(problem, {}, 1) == 2
    assert credit_bound(problem, {}, 1) == 1
    assert composite(problem, {}, 1) == 2


def test_optional_elective_does_not_inflate_the_bound():
    problem = Problem(
        courses={
            "CS F211": _course(4, ELECTIVE),
            "CS F212": _course(4, ELECTIVE, formula=_pre("CS F211")),
            "CS F213": _course(4, ELECTIVE, formula=_pre("CS F212")),
        },
        current_semester=0,
        target_semester=6,
        max_credits=4,
        category_minimums={},
    )
    assert credit_bound(problem, {}, 1) == 0
    assert critical_path(problem, {}, 1) == 0
    assert composite(problem, {}, 1) == 0


def test_category_floor_forces_elective_credits_into_the_credit_bound():
    problem = Problem(
        courses={"CS F311": _course(4, ELECTIVE)},
        current_semester=0,
        target_semester=4,
        max_credits=20,
        category_minimums={ELECTIVE: 4},
    )
    assert credit_bound(problem, {}, 1) == 1
    assert critical_path(problem, {}, 1) == 0
    assert composite(problem, {}, 1) == 1


def test_impossible_horizon_makes_the_heuristic_infinite():
    problem = _chain_problem()
    problem.target_semester = 2
    assert math.isinf(composite(problem, {}, 1))


def test_astar_returns_the_shortest_chain():
    problem = _chain_problem()
    result = solve(problem)
    assert result.status == "SAT"
    assert result.stats["terms_used"] == 3
    plan = result.to_study_plan()
    assert plan is not None
    by_term = plan.courses_by_term()
    assert by_term[1] == ["CS F211"]
    assert by_term[2] == ["CS F212"]
    assert by_term[3] == ["CS F213"]
    assert _locally_valid(problem, result.assignment)


def test_astar_reports_unsat_when_the_horizon_is_too_short():
    problem = _chain_problem()
    problem.target_semester = 2
    result = solve(problem)
    assert result.status == "UNSAT"
    assert result.assignment is None


def test_astar_leaves_unneeded_electives_untaken():
    problem = Problem(
        courses={
            "CS F211": _course(4),
            "CS F311": _course(3, ELECTIVE),
        },
        current_semester=0,
        target_semester=4,
        max_credits=20,
    )
    result = solve(problem)
    assert result.status == "SAT"
    assert result.stats["terms_used"] == 1
    assert result.assignment["CS F211"] == 1
    assert result.assignment["CS F311"] == NOT_TAKEN


def test_astar_schedules_an_elective_when_the_category_floor_requires_it():
    problem = Problem(
        courses={"CS F311": _course(4, ELECTIVE, parity="odd")},
        current_semester=0,
        target_semester=4,
        max_credits=20,
        category_minimums={ELECTIVE: 4},
    )
    result = solve(problem)
    assert result.status == "SAT"
    assert result.assignment["CS F311"] == 1
    assert result.stats["terms_used"] == 1


def test_corequisites_share_a_term():
    problem = Problem(
        courses={
            "CS F301": _course(3, formula=_co("CS F302")),
            "CS F302": _course(3, formula=_co("CS F301")),
        },
        current_semester=0,
        target_semester=3,
        max_credits=6,
    )
    result = solve(problem)
    assert result.status == "SAT"
    assert result.assignment["CS F301"] == result.assignment["CS F302"] == 1
    assert result.stats["terms_used"] == 1


def test_corequisites_are_unsat_when_they_cannot_fit_together():
    problem = Problem(
        courses={
            "CS F301": _course(4, formula=_co("CS F302")),
            "CS F302": _course(4, formula=_co("CS F301")),
        },
        current_semester=0,
        target_semester=4,
        max_credits=4,
    )
    result = solve(problem)
    assert result.status == "UNSAT"


def test_bundle_limit_can_miss_a_feasible_plan():
    """A tight bundle cap is incomplete. Optimality runs leave the cap off."""
    courses = {
        "CS F101": _course(1, ELECTIVE),
        "CS F102": _course(1, ELECTIVE),
        "CS F301": _course(1, formula=_co("CS F302")),
        "CS F302": _course(1, formula=_co("CS F301")),
    }
    problem = Problem(
        courses=courses,
        current_semester=0,
        target_semester=1,
        max_credits=2,
    )
    capped = solve(problem, AStarConfig(bundle_breadth_limit=1, timeout_seconds=5))
    complete = solve(problem, AStarConfig(bundle_breadth_limit=None, timeout_seconds=5))
    assert capped.status == "UNSAT"
    assert complete.status == "SAT"
    assert complete.assignment["CS F301"] == 1
    assert complete.assignment["CS F302"] == 1
    assert complete.assignment["CS F101"] == NOT_TAKEN
    assert complete.stats["complete_search"] is True
    assert capped.stats["complete_search"] is False


def test_heuristics_never_exceed_optimal_and_astar_matches_it():
    for seed in range(12):
        problem = _tiny_problem(seed)
        optimal = _brute_optimal(problem)
        root = problem.current_semester + 1
        estimate = composite(problem, {}, root)
        result = solve(problem, AStarConfig(timeout_seconds=5))
        if optimal is None:
            assert result.status == "UNSAT", seed
            continue
        assert estimate <= optimal, (seed, estimate, optimal)
        assert result.status == "SAT", (seed, result.status, result.stats)
        assert result.stats["terms_used"] == optimal, (seed, result.stats, optimal)
        assert _locally_valid(problem, result.assignment)


def test_each_admissible_heuristic_is_optimal_on_the_chain():
    problem = _chain_problem()
    for name in ("credit_bound", "critical_path", "composite"):
        result = solve(problem, AStarConfig(heuristic=name))
        assert result.status == "SAT"
        assert result.stats["terms_used"] == 3
        assert result.stats["heuristic"] == name


def test_min_credits_does_not_apply_after_graduation():
    """Target semester is a planning horizon deadline, not a requirement to stay enrolled.
    
    A course completed in term 1 satisfies a min_credits=3 requirement even if
    the target semester is 3, because the student has graduated after term 1.
    """
    problem = Problem(
        courses={"CS F211": _course(3)},
        completed=set(),
        current_semester=0,
        target_semester=3,
        max_credits=10,
        min_credits=3,
    )
    result = solve(problem)
    assert result.status == "SAT"
    assert result.stats["terms_used"] == 1
    assert result.assignment["CS F211"] == 1
