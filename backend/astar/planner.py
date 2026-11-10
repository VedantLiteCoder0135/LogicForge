"""A* planner over semester bundles.

A state is the next open term plus the courses already given a semester.
An action fills that term with a credit-feasible set of courses whose
prerequisites are already satisfied (corequisites may sit in the same set),
or leaves the term empty when the credit floor allows it. Empty terms matter:
an even-only course cannot be taken in an odd term, so the search has to
be allowed to wait.

Path cost is the number of terms consumed. With an admissible heuristic and
``bundle_breadth_limit is None``, the first goal A* pops is a minimum-term
plan. A finite bundle limit keeps the branching factor down and can miss
that plan; Experiment E1 should leave the limit off.
"""

from __future__ import annotations

import heapq
import math
import time
from dataclasses import dataclass, field
from typing import Any

from backend.models.planning_problem import (
    NOT_TAKEN,
    Problem,
    assignment_is_valid,
    formula_satisfied,
    is_elective_category,
    parity_allows,
)
from backend.models.study_plan import StudyPlan

from .heuristics import get_heuristic


class _SearchTimeout(Exception):
    """Raised inside bundle enumeration when the time limit is hit."""


@dataclass
class AStarConfig:
    """Switches for one A* run.

    ``heuristic`` is ``credit_bound``, ``critical_path``, or ``composite``.
    ``bundle_breadth_limit`` caps how many feasible bundles are generated
    for a term. ``None`` enumerates every feasible bundle, which is what
    optimality needs. ``config.settings.ASTAR.bundle_breadth_limit`` is the
    approximate setting and is not applied unless you pass it here.
    """

    heuristic: str = "composite"
    bundle_breadth_limit: int | None = None
    timeout_seconds: float | None = 30.0
    max_nodes: int = 100_000


@dataclass
class PlacementTrace:
    """Why one course ended up in a term or was left untaken."""

    course: str
    semester: Any
    reason: str

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


@dataclass
class Result:
    """Outcome of one A* run. ``status`` is SAT, UNSAT, or TIMEOUT."""

    status: str
    assignment: dict[str, Any] | None
    trace: list[PlacementTrace] | None
    stats: dict[str, Any] = field(default_factory=dict)

    def to_study_plan(self) -> StudyPlan | None:
        if self.assignment is None:
            return None
        return StudyPlan(
            assignment=dict(self.assignment),
            terms_used=int(self.stats.get("terms_used", 0)),
            trace=list(self.trace or []),
        )


def _credits(problem: Problem, code: str) -> int:
    return int(problem.courses[code].get("credits") or 0)


def _complete_assignment(problem: Problem, placed: dict[str, int]) -> dict[str, Any] | None:
    """Fill untaken electives with ``NOT_TAKEN``. Cores still outstanding block a goal."""
    assignment: dict[str, Any] = {}
    for code in problem.variables:
        if code in placed:
            assignment[code] = placed[code]
        elif is_elective_category(problem.courses[code].get("category")):
            assignment[code] = NOT_TAKEN
        else:
            return None
    return assignment


def _eligible(problem: Problem, placed: dict[str, int], term: int) -> list[str]:
    """Courses that could possibly be taken in ``term`` given ``placed``."""
    pool: list[str] = []
    for code in problem.variables:
        if code in placed:
            continue
        if not parity_allows(problem.courses[code].get("parity"), term):
            continue
        pool.append(code)
    optimistic = dict(placed)
    for code in pool:
        optimistic[code] = term
    eligible: list[str] = []
    for code in pool:
        formula = problem.courses[code].get("formula")
        if formula_satisfied(problem, formula, term, optimistic):
            eligible.append(code)
    return eligible


def _enumerate_bundles(
    problem: Problem,
    placed: dict[str, int],
    term: int,
    limit: int | None,
    timed_out,
) -> list[tuple[str, ...]]:
    eligible = _eligible(problem, placed, term)
    if limit is None:
        ordered = sorted(eligible)
    else:
        ordered = sorted(eligible, key=lambda code: (-_credits(problem, code), code))

    found: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()

    def bundle_ok(chosen: tuple[str, ...]) -> bool:
        hypothetical = dict(placed)
        for code in chosen:
            hypothetical[code] = term
        for code in chosen:
            formula = problem.courses[code].get("formula")
            if not formula_satisfied(problem, formula, term, hypothetical):
                return False
        load = sum(_credits(problem, code) for code in chosen)
        if load > problem.max_credits:
            return False
        if problem.min_credits > 0 and load < problem.min_credits:
            return False
        return True

    def save(chosen: list[str]) -> None:
        key = tuple(sorted(chosen))
        if key in seen or not bundle_ok(key):
            return
        seen.add(key)
        found.append(key)

    def dfs(index: int, chosen: list[str], load: int) -> None:
        if timed_out():
            raise _SearchTimeout()
        if limit is not None and len(found) >= limit:
            return
        if index == len(ordered):
            save(chosen)
            return
        code = ordered[index]
        weight = _credits(problem, code)
        if load + weight <= problem.max_credits:
            chosen.append(code)
            dfs(index + 1, chosen, load + weight)
            chosen.pop()
        dfs(index + 1, chosen, load)

    dfs(0, [], 0)
    if problem.min_credits <= 0 and tuple() not in seen:
        found.append(tuple())
    return found


def _trace_for(
    problem: Problem,
    assignment: dict[str, Any],
    heuristic_name: str,
) -> list[PlacementTrace]:
    rows: list[PlacementTrace] = []
    for code in problem.variables:
        semester = assignment[code]
        if semester == NOT_TAKEN:
            reason = "left untaken; elective is not required for a minimum-term plan"
        else:
            reason = f"scheduled in semester {semester} by A* ({heuristic_name})"
        rows.append(PlacementTrace(code, semester, reason))
    return rows


def _result(
    status: str,
    problem: Problem,
    assignment: dict[str, Any] | None,
    terms_used: int,
    heuristic_name: str,
    nodes: int,
    bundles: int,
    started: float,
    root_h: float,
    limit: int | None,
) -> Result:
    trace = None if assignment is None else _trace_for(problem, assignment, heuristic_name)
    return Result(
        status=status,
        assignment=assignment,
        trace=trace,
        stats={
            "nodes": nodes,
            "bundles": bundles,
            "time_s": time.perf_counter() - started,
            "terms_used": terms_used,
            "heuristic": heuristic_name,
            "root_h": None if math.isinf(root_h) else root_h,
            "bundle_breadth_limit": limit,
            "complete_search": limit is None,
        },
    )


def solve(problem: Problem, config: AStarConfig | None = None) -> Result:
    """Search for a minimum-term plan. See ``AStarConfig`` for the switches."""
    cfg = config or AStarConfig()
    heuristic = get_heuristic(cfg.heuristic)
    started = time.perf_counter()
    nodes = 0
    bundles_seen = 0

    def timed_out() -> bool:
        if cfg.timeout_seconds is None:
            return False
        return (time.perf_counter() - started) >= cfg.timeout_seconds

    root_placed: dict[str, int] = {}
    root_term = problem.current_semester + 1
    root_h = heuristic(problem, root_placed, root_term)
    finished = _complete_assignment(problem, root_placed)
    if finished is not None and assignment_is_valid(problem, finished):
        return _result(
            "SAT", problem, finished, 0, cfg.heuristic, 1, 0, started, root_h, cfg.bundle_breadth_limit
        )
    if math.isinf(root_h):
        return _result(
            "UNSAT", problem, None, 0, cfg.heuristic, 1, 0, started, root_h, cfg.bundle_breadth_limit
        )

    counter = 0
    start_state = (root_term, tuple())
    best_g: dict[tuple, int] = {start_state: 0}
    # Priority tuple: (f_score, g_cost, elective_count, counter, state)
    # Breaking ties with elective_count ensures that for the same term count,
    # plans that don't take unneeded electives are preferred.
    heap: list[tuple] = [(root_h, 0, 0, counter, start_state)]

    while heap:
        if timed_out() or nodes >= cfg.max_nodes:
            return _result(
                "TIMEOUT", problem, None, 0, cfg.heuristic, nodes, bundles_seen,
                started, root_h, cfg.bundle_breadth_limit,
            )
        _score, g_cost, _elec, _tie, state = heapq.heappop(heap)
        if g_cost != best_g.get(state):
            continue
        nodes += 1
        next_term, placed_items = state
        placed = dict(placed_items)
        assignment = _complete_assignment(problem, placed)
        if assignment is not None and assignment_is_valid(problem, assignment):
            return _result(
                "SAT", problem, assignment, g_cost, cfg.heuristic, nodes, bundles_seen,
                started, root_h, cfg.bundle_breadth_limit,
            )
        if next_term > problem.target_semester:
            continue
        try:
            bundles = _enumerate_bundles(
                problem, placed, next_term, cfg.bundle_breadth_limit, timed_out
            )
        except _SearchTimeout:
            return _result(
                "TIMEOUT", problem, None, 0, cfg.heuristic, nodes, bundles_seen,
                started, root_h, cfg.bundle_breadth_limit,
            )
        for bundle in bundles:
            bundles_seen += 1
            updated = dict(placed)
            for code in bundle:
                updated[code] = next_term
            successor = (next_term + 1, tuple(sorted(updated.items())))
            new_g = g_cost + 1
            estimate = heuristic(problem, updated, next_term + 1)
            if math.isinf(estimate):
                continue
            if new_g < best_g.get(successor, math.inf):
                best_g[successor] = new_g
                counter += 1
                elec_count = sum(
                    1 for c in updated
                    if is_elective_category(problem.courses[c].get("category"))
                )
                heapq.heappush(
                    heap, (new_g + estimate, new_g, elec_count, counter, successor)
                )

    return _result(
        "UNSAT", problem, None, 0, cfg.heuristic, nodes, bundles_seen,
        started, root_h, cfg.bundle_breadth_limit,
    )
