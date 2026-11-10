"""GraphMind — CSP Problem Model and Adapter

Defines the Problem dataclass, Constraint class, NOT_TAKEN sentinel,
and build_problem adapter from Pair A's RequirementResolver.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

# Sentinel value representing that an elective course is not taken in the plan
NOT_TAKEN = "NOT_TAKEN"


def extract_formula_courses(formula: Optional[Dict[str, Any]]) -> Set[str]:
    """Recursively extract all course codes referenced in a prerequisite formula tree."""
    if not formula:
        return set()
    kind = formula.get("kind")
    if kind == "leaf":
        course = formula.get("course")
        return {course} if course else set()
    if kind in ("and", "or"):
        courses: Set[str] = set()
        for child in formula.get("items", []):
            courses.update(extract_formula_courses(child))
        return courses
    return set()


@dataclass(frozen=True)
class Constraint:
    """Named constraint object with an explicit variable scope.

    Naming convention:
      - 'prereq:<COURSE>'
      - 'credit_cap:<SEM>'
      - 'category_min:<CATEGORY>'
    """
    name: str
    scope: List[str]

    def __repr__(self) -> str:
        return f"Constraint({self.name!r}, scope={self.scope})"


@dataclass
class Problem:
    """Pure-data CSP problem representation.

    Can be constructed directly without RequirementResolver (e.g. for unit
    tests and synthetic benchmarks) or populated via build_problem().
    """
    courses: Dict[str, Dict[str, Any]]
    completed: Set[str]
    current_semester: int
    target_semester: int
    max_credits: int = 20
    min_credits: int = 0
    category_minimums: Dict[str, int] = field(default_factory=dict)
    assume_out_of_scope_satisfied: bool = True
    out_of_scope_assumed_courses: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Ensure completed is a set
        if not isinstance(self.completed, set):
            self.completed = set(self.completed)

        # Detect out-of-scope courses if not already explicitly populated
        if not self.out_of_scope_assumed_courses:
            in_universe = set(self.courses.keys()) | self.completed
            out_of_scope: Set[str] = set()
            for info in self.courses.values():
                formula = info.get("formula")
                referenced = extract_formula_courses(formula)
                out_of_scope.update(referenced - in_universe)
            self.out_of_scope_assumed_courses = sorted(out_of_scope)

    @property
    def variables(self) -> List[str]:
        """All courses requiring assignment: in-scope courses minus completed."""
        return sorted([code for code in self.courses if code not in self.completed])

    def initial_domains(self) -> Dict[str, List[Any]]:
        """Construct the initial domain for every variable.

        Domains consist of valid semester integers in [current_semester + 1, target_semester]
        filtered by parity, followed by NOT_TAKEN if allowed for the course's category.
        """
        domains: Dict[str, List[Any]] = {}
        for code in self.variables:
            info = self.courses[code]
            parity = info.get("parity")
            category = info.get("category", "")

            valid_semesters: List[int] = []
            for s in range(self.current_semester + 1, self.target_semester + 1):
                if parity == "odd" and s % 2 != 1:
                    continue
                if parity == "even" and s % 2 != 0:
                    continue
                valid_semesters.append(s)

            domain: List[Any] = list(valid_semesters)

            # NOT_TAKEN is allowed ONLY for Discipline Electives (and elective categories).
            # Discipline Core and University Core (First Year) MUST be taken.
            is_elective = category == "Discipline Elective" or (
                "elective" in category.lower()
                and category not in ("Discipline Core", "University Core (First Year)")
            )
            if is_elective:
                domain.append(NOT_TAKEN)

            domains[code] = domain

        return domains

    def named_constraints(self) -> Dict[str, Constraint]:
        """Generate all named constraints for Person 7 and the solver."""
        constraints: Dict[str, Constraint] = {}

        # 1. prereq:<COURSE> for each variable with a formula
        for code in self.variables:
            formula = self.courses[code].get("formula")
            if formula is not None:
                deps = extract_formula_courses(formula)
                scope = [code] + sorted([d for d in deps if d in self.variables and d != code])
                c_name = f"prereq:{code}"
                constraints[c_name] = Constraint(name=c_name, scope=scope)

        # 2. credit_cap:<SEM> for each semester in range
        for s in range(self.current_semester + 1, self.target_semester + 1):
            c_name = f"credit_cap:{s}"
            scope = [
                code for code in self.variables
                if self._can_be_assigned_to_semester(code, s)
            ]
            constraints[c_name] = Constraint(name=c_name, scope=scope)

        # 3. category_min:<CATEGORY> for each category with a minimum floor
        for cat in self.category_minimums:
            c_name = f"category_min:{cat}"
            scope = [
                code for code in self.variables
                if self.courses[code].get("category") == cat
            ]
            constraints[c_name] = Constraint(name=c_name, scope=scope)

        return constraints

    def _can_be_assigned_to_semester(self, code: str, sem: int) -> bool:
        """Check if semester matches parity rules for a course."""
        parity = self.courses[code].get("parity")
        if parity == "odd" and sem % 2 != 1:
            return False
        if parity == "even" and sem % 2 != 0:
            return False
        return True


def build_problem(
    resolver: Any,
    completed: Set[str],
    current_semester: int,
    target_semester: int,
    *,
    scope_path: Optional[str] = None,
    parity_by_code: Optional[Dict[str, Optional[str]]] = None,
    max_credits: int = 20,
    min_credits: int = 0,
    category_minimums: Optional[Dict[str, int]] = None,
    assume_out_of_scope_satisfied: bool = True,
    **kw: Any,
) -> Problem:
    """Build a Problem dataclass instance from a RequirementResolver.

    Variables are all courses in resolver.courses_in_scope() minus completed.
    Course metadata (credits, category, parity, formula) is extracted from
    the resolver and the curriculum scope specification.
    """
    # Load parity_by_code if not provided
    if parity_by_code is None:
        parity_by_code = {}
        # Try finding curriculum_scope.json
        candidate_paths = []
        if scope_path:
            candidate_paths.append(scope_path)
        base_dir = os.path.dirname(__file__)
        candidate_paths.append(os.path.join(base_dir, "..", "PairA_CurriculumKB", "curriculum_scope.json"))
        candidate_paths.append("curriculum_scope.json")

        for cp in candidate_paths:
            if os.path.exists(cp):
                try:
                    with open(cp, encoding="utf-8") as f:
                        scope_data = json.load(f)
                    for entry in scope_data.get("courses", []):
                        parity_by_code[entry["code"]] = entry.get("term_parity")
                    break
                except Exception:
                    pass

    # Extract all in-scope courses
    in_scope_codes = resolver.courses_in_scope()

    courses: Dict[str, Dict[str, Any]] = {}
    for code in in_scope_codes:
        credits_val = resolver.credits_by_code.get(code, 0)
        category = resolver.category_by_code.get(code, "Unknown")
        parity = parity_by_code.get(code)
        try:
            formula = resolver.formula_for(code)
        except (KeyError, AttributeError):
            formula = None

        courses[code] = {
            "credits": credits_val,
            "category": category,
            "parity": parity,
            "formula": formula,
        }

    # Also capture completed courses metadata if available in resolver for category tracking
    for code in completed:
        if code not in courses:
            courses[code] = {
                "credits": resolver.credits_by_code.get(code, 0),
                "category": resolver.category_by_code.get(code, "Unknown"),
                "parity": parity_by_code.get(code),
                "formula": None,
            }

    if category_minimums is None:
        category_minimums = dict(resolver.category_minimums)

    return Problem(
        courses=courses,
        completed=set(completed),
        current_semester=current_semester,
        target_semester=target_semester,
        max_credits=max_credits,
        min_credits=min_credits,
        category_minimums=category_minimums,
        assume_out_of_scope_satisfied=assume_out_of_scope_satisfied,
    )
