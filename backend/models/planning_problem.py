"""Shared planning problem consumed by the CSP solver and the A* planner.

Uses Pair B's ``Problem`` class (``backend.csp.model``) as the single
canonical definition so that both solvers operate on the identical object —
which is what makes the E1 comparison meaningful.

This module re-exports ``Problem``, ``NOT_TAKEN``, ``Constraint``, and
``extract_formula_courses`` from ``backend.csp.model``, and adds the
A*-specific helpers (``formula_satisfied``, ``assignment_is_valid``,
``is_elective_category``, ``parity_allows``, ``problem_from_curriculum``)
that only Pair C needs.
"""

from __future__ import annotations

from typing import Any

# ── canonical model from Pair B ──────────────────────────────────────────────
from backend.csp.model import (  # noqa: F401  (re-exported for all Pair C imports)
    Constraint,
    NOT_TAKEN,
    Problem,
    extract_formula_courses,
)

from .curriculum import Curriculum


# ── helpers used by the A* planner and heuristics ────────────────────────────

def is_elective_category(category: str | None) -> bool:
    """Electives may be left untaken. Cores may not.

    Mirrors the identical rule in Pair B's ``initial_domains()``.
    """
    name = category or ""
    if name == "Discipline Elective":
        return True
    if "elective" in name.lower() and name not in {
        "Discipline Core",
        "University Core (First Year)",
    }:
        return True
    return False


def parity_allows(parity: str | None, semester: int) -> bool:
    """``odd`` / ``even`` restrict the term. ``both``, ``any``, and ``None`` do not."""
    if parity in (None, "", "both", "any"):
        return True
    if parity == "odd":
        return semester % 2 == 1
    if parity == "even":
        return semester % 2 == 0
    return True


def formula_satisfied(
    problem: Problem,
    formula: dict | None,
    semester: int,
    assignment: dict[str, Any],
) -> bool:
    """Whether ``formula`` holds if this course is taken in ``semester``.

    Prerequisites must sit in a strictly earlier term. Corequisites may sit
    in ``semester`` or earlier. Completed courses count as already done.
    A referenced code that is not in the catalogue is out of scope and follows
    ``problem.assume_out_of_scope_satisfied``. An in-scope course that is
    simply unassigned does not satisfy the leaf.
    """
    if formula is None:
        return True
    kind = formula.get("kind")
    if kind == "leaf":
        target = formula["course"]
        relation = formula.get("relation", "PRE")
        if target in problem.completed:
            return True
        if target in assignment:
            value = assignment[target]
            if value == NOT_TAKEN:
                return False
            if relation == "CO":
                return value <= semester
            return value < semester
        out_of_scope = (
            target in problem.out_of_scope_assumed_courses
            or target not in problem.courses
        )
        if out_of_scope:
            return problem.assume_out_of_scope_satisfied
        return False
    if kind == "and":
        return all(
            formula_satisfied(problem, child, semester, assignment)
            for child in formula.get("items", [])
        )
    if kind == "or":
        return any(
            formula_satisfied(problem, child, semester, assignment)
            for child in formula.get("items", [])
        )
    return False


def assignment_is_valid(problem: Problem, assignment: dict[str, Any]) -> bool:
    """Re-check a complete assignment against the problem constraints.

    The assignment must mention every variable exactly once. This is the
    goal test the A* planner uses; it does not trust the order in which
    bundles were built.
    """
    if set(assignment) != set(problem.variables):
        return False

    for code, value in assignment.items():
        info = problem.courses[code]
        if value == NOT_TAKEN:
            if not is_elective_category(info.get("category")):
                return False
            continue
        if not isinstance(value, int):
            return False
        if not (problem.current_semester < value <= problem.target_semester):
            return False
        if not parity_allows(info.get("parity"), value):
            return False
        if not formula_satisfied(problem, info.get("formula"), value, assignment):
            return False

    # Graduation semester is the last term in which a course was scheduled.
    # Semesters after graduation do not require enrolled course credits.
    graduation_semester = max(
        (val for val in assignment.values() if isinstance(val, int)),
        default=problem.current_semester,
    )

    for semester in range(problem.current_semester + 1, problem.target_semester + 1):
        load = sum(
            problem.courses[code].get("credits") or 0
            for code, value in assignment.items()
            if value == semester
        )
        if load > problem.max_credits:
            return False
        # Minimum credit requirement only applies through graduation (while enrolled)
        if semester <= graduation_semester:
            if problem.min_credits > 0 and load < problem.min_credits:
                return False

    for category, minimum in problem.category_minimums.items():
        earned = 0
        for code, info in problem.courses.items():
            if info.get("category") != category:
                continue
            if code in problem.completed or (
                code in assignment and assignment[code] != NOT_TAKEN
            ):
                earned += info.get("credits") or 0
        if earned < minimum:
            return False
    return True


def _stored_parity(term_parity: str | None) -> str | None:
    if term_parity in (None, "", "both", "any"):
        return None
    return term_parity


def problem_from_curriculum(
    curriculum: Curriculum,
    completed: set[str],
    current_semester: int,
    target_semester: int,
    *,
    max_credits: int = 20,
    min_credits: int = 0,
    assume_out_of_scope_satisfied: bool = True,
) -> Problem:
    """Build a ``Problem`` from a loaded ``Curriculum`` and a transcript."""
    courses: dict[str, dict[str, Any]] = {}
    for code, course in curriculum.courses.items():
        courses[code] = {
            "credits": course.credits,
            "category": course.category,
            "parity": _stored_parity(course.term_parity),
            "formula": course.parsed_prerequisites,
            "title": course.title,
        }
    minimums = {
        category: requirement.credit_minimum
        for category, requirement in curriculum.requirements.items()
    }
    return Problem(
        courses=courses,
        completed=set(completed),
        current_semester=current_semester,
        target_semester=target_semester,
        max_credits=max_credits,
        min_credits=min_credits,
        category_minimums=minimums,
        assume_out_of_scope_satisfied=assume_out_of_scope_satisfied,
    )
