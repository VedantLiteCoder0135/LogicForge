"""Admissible heuristics for the term-count objective.

The cost of a plan is the number of terms after ``current_semester`` through
the last scheduled course. Each heuristic below is a lower bound on how many
further terms a partial plan still needs:

* **Credit bound.** ``ceil(minimum credits still required / max_credits)``.
  Required credits are remaining core courses plus the credit deficit on each
  category floor. Elective credits beyond that deficit are ignored, so the
  bound does not pretend every elective must be taken.
* **Critical path.** Length of the longest remaining prerequisite chain among
  courses that must still be taken, plus one if none of those chain heads can
  be offered in the next open term. A corequisite does not add a term.
  Parity can only insert extra waits, so this never exceeds the true length.
* **Composite.** Pointwise maximum of the two bounds. The max of admissible
  heuristics is admissible, and it dominates either one alone.

Neither number is a predicted graduation date. A learned heuristic is not
included here: it would not be admissible, and Experiment E3 is where it
gets compared later.
"""

from __future__ import annotations

import math
from typing import Callable

from backend.models.planning_problem import (
    Problem,
    is_elective_category,
    parity_allows,
)

Heuristic = Callable[[Problem, dict[str, int], int], float]


def _remaining_groups(
    problem: Problem, placed: dict[str, int]
) -> tuple[list[str], list[str]]:
    mandatory: list[str] = []
    electives: list[str] = []
    for code in problem.variables:
        if code in placed:
            continue
        category = problem.courses[code].get("category")
        if is_elective_category(category):
            electives.append(code)
        else:
            mandatory.append(code)
    return mandatory, electives


def minimum_required_credits(problem: Problem, placed: dict[str, int]) -> float:
    """Fewest credits that still have to be scheduled. ``inf`` if a floor is impossible."""
    covered: dict[str, int] = {}

    def add(code: str) -> None:
        info = problem.courses.get(code)
        if not info:
            return
        category = info.get("category") or ""
        covered[category] = covered.get(category, 0) + int(info.get("credits") or 0)

    for code in problem.completed:
        add(code)
    for code in placed:
        add(code)

    mandatory, electives = _remaining_groups(problem, placed)
    for code in mandatory:
        credits = int(problem.courses[code].get("credits") or 0)
        if problem.max_credits <= 0 or credits > problem.max_credits:
            return math.inf
        add(code)

    required = sum(int(problem.courses[code].get("credits") or 0) for code in mandatory)
    pool: dict[str, int] = {}
    for code in electives:
        info = problem.courses[code]
        category = info.get("category") or ""
        pool[category] = pool.get(category, 0) + int(info.get("credits") or 0)

    for category, minimum in problem.category_minimums.items():
        gap = int(minimum) - covered.get(category, 0)
        if gap <= 0:
            continue
        if pool.get(category, 0) < gap:
            return math.inf
        required += gap
    return float(required)


def _horizon_or_inf(problem: Problem, next_term: int, bound: float) -> float:
    if math.isinf(bound):
        return math.inf
    available = problem.target_semester - next_term + 1
    if bound > available:
        return math.inf
    return float(bound)


def credit_bound(problem: Problem, placed: dict[str, int], next_term: int) -> float:
    """``ceil(required credits / max credits per term)``, clipped to the horizon."""
    required = minimum_required_credits(problem, placed)
    if math.isinf(required):
        return math.inf
    if required <= 0:
        return _horizon_or_inf(problem, next_term, 0.0)
    if problem.max_credits <= 0:
        return math.inf
    return _horizon_or_inf(problem, next_term, math.ceil(required / problem.max_credits))


def _formula_depth(
    formula: dict | None,
    depth_of: Callable[[str], float],
    problem: Problem,
    placed: dict[str, int],
) -> float:
    """Terms that must already have been used before this formula is satisfied.

    The course itself is not counted. OR contributes the easier branch.
    AND contributes the harder branch. Corequisites add nothing.
    """
    if not formula:
        return 0.0
    kind = formula.get("kind")
    if kind == "leaf":
        if formula.get("relation", "PRE") == "CO":
            return 0.0
        dependency = formula.get("course")
        if dependency in problem.completed or dependency in placed:
            return 0.0
        info = problem.courses.get(dependency)
        if info is None:
            if problem.assume_out_of_scope_satisfied:
                return 0.0
            return math.inf
        if is_elective_category(info.get("category")):
            return 0.0
        if dependency not in problem.variables:
            return 0.0
        return depth_of(dependency)
    items = formula.get("items") or []
    if kind == "and":
        if not items:
            return 0.0
        return max(_formula_depth(child, depth_of, problem, placed) for child in items)
    if kind == "or":
        if not items:
            return 0.0
        options = [_formula_depth(child, depth_of, problem, placed) for child in items]
        finite = [option for option in options if not math.isinf(option)]
        if not finite:
            return math.inf
        return min(finite)
    return 0.0


def critical_path(problem: Problem, placed: dict[str, int], next_term: int) -> float:
    """Longest remaining mandatory prerequisite chain, in terms."""
    mandatory, _electives = _remaining_groups(problem, placed)
    if not mandatory:
        return _horizon_or_inf(problem, next_term, 0.0)

    memo: dict[str, float] = {}
    visiting: set[str] = set()

    def depth_of(code: str) -> float:
        if code in memo:
            return memo[code]
        if code in visiting:
            return math.inf
        visiting.add(code)
        info = problem.courses.get(code)
        formula = None if info is None else info.get("formula")
        depth = 1.0 + _formula_depth(formula, depth_of, problem, placed)
        visiting.remove(code)
        memo[code] = depth
        return depth

    depths = [depth_of(code) for code in mandatory]
    if any(math.isinf(depth) for depth in depths):
        return math.inf
    chain = max(depths)
    heads = [
        code
        for code in mandatory
        if _formula_depth(problem.courses[code].get("formula"), depth_of, problem, placed) == 0
    ]
    gap = 0.0
    if heads and not any(
        parity_allows(problem.courses[code].get("parity"), next_term) for code in heads
    ):
        gap = 1.0
    return _horizon_or_inf(problem, next_term, chain + gap)


def composite(problem: Problem, placed: dict[str, int], next_term: int) -> float:
    """Max of the credit bound and the critical-path bound."""
    credits = credit_bound(problem, placed, next_term)
    chain = critical_path(problem, placed, next_term)
    if math.isinf(credits) or math.isinf(chain):
        return math.inf
    return max(credits, chain)


HEURISTICS: dict[str, Heuristic] = {
    "credit_bound": credit_bound,
    "critical_path": critical_path,
    "composite": composite,
}


def get_heuristic(name: str) -> Heuristic:
    """Return one of the admissible heuristics by the name in ``AStarConfig``."""
    try:
        return HEURISTICS[name]
    except KeyError as exc:
        known = ", ".join(sorted(HEURISTICS))
        raise ValueError(
            f"Unknown heuristic {name!r}. Admissible heuristics are: {known}."
        ) from exc
