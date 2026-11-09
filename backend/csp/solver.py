"""GraphMind — CSP Solver

Implements backtracking search with optional MRV, degree tiebreaker,
Forward Checking, AC-3 (MAC), bounds checks, and trail-based undo.
"""

from __future__ import annotations

import collections
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .model import Constraint, NOT_TAKEN, Problem


@dataclass
class SolverConfig:
    """Configuration switches for the CSP solver."""
    mrv: bool = False
    forward_checking: bool = False
    ac3: bool = False
    degree_tiebreak: bool = False
    timeout_s: Optional[float] = None


@dataclass
class PlacementTrace:
    """Human-readable explanation of why a course was placed in a semester or marked NOT_TAKEN."""
    course: str
    semester: Any
    reason: str

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


@dataclass
class Result:
    """Outcome of running the CSP solver."""
    status: str  # "SAT" | "UNSAT" | "TIMEOUT"
    assignment: Optional[Dict[str, Any]]
    trace: Optional[List[PlacementTrace]]
    stats: Dict[str, Any]


def _eval_leaf_optimistic(
    leaf: Dict[str, Any],
    sem: int,
    assignment: Dict[str, Any],
    domains: Dict[str, Set[Any]],
    completed: Set[str],
    out_of_scope_codes: Set[str],
    assume_out_of_scope_satisfied: bool,
    fixed_var: Optional[str] = None,
    fixed_val: Optional[Any] = None,
) -> bool:
    """Evaluate whether a leaf formula can be satisfied given current assignments and domains."""
    target = leaf["course"]
    rel = leaf.get("relation", "PRE")

    # Completed courses count as semester 0
    if target in completed:
        return True  # 0 < sem (since sem >= 1) and 0 <= sem

    # Out of scope courses
    if target in out_of_scope_codes:
        return assume_out_of_scope_satisfied

    # Fixed variable override (used when checking hypothetical support for target)
    if fixed_var is not None and target == fixed_var:
        if fixed_val == NOT_TAKEN:
            return False
        if rel == "CO":
            return fixed_val <= sem
        return fixed_val < sem

    # If target is already assigned in partial assignment
    if target in assignment:
        val = assignment[target]
        if val == NOT_TAKEN:
            return False
        if rel == "CO":
            return val <= sem
        return val < sem

    # If target is in domains (unassigned): optimistic evaluation
    if target in domains:
        for val in domains[target]:
            if val == NOT_TAKEN:
                continue
            if rel == "CO" and val <= sem:
                return True
            if rel != "CO" and val < sem:
                return True
        return False

    # Course neither completed, nor variable, nor known out-of-scope
    return assume_out_of_scope_satisfied


def _eval_formula_optimistic(
    formula: Optional[Dict[str, Any]],
    sem: int,
    assignment: Dict[str, Any],
    domains: Dict[str, Set[Any]],
    completed: Set[str],
    out_of_scope_codes: Set[str],
    assume_out_of_scope_satisfied: bool,
    fixed_var: Optional[str] = None,
    fixed_val: Optional[Any] = None,
) -> bool:
    """Optimistic evaluation of a formula tree against current assignment and domains.

    Note on AC-3 Support Check:
    Because curriculum prerequisite formulas are monotone Boolean trees composed
    strictly of AND/OR connectives with positive leaf literals (no negation),
    a formula is satisfiable over the Cartesian product of variable domains iff
    each leaf is optimistically supported by at least one value in its variable's
    domain. Thus, evaluating the tree optimistically provides an exact, sound,
    and highly efficient support test without needing exponential enumeration.
    """
    if formula is None:
        return True

    kind = formula.get("kind")
    if kind == "leaf":
        return _eval_leaf_optimistic(
            formula, sem, assignment, domains, completed,
            out_of_scope_codes, assume_out_of_scope_satisfied,
            fixed_var, fixed_val
        )
    if kind == "and":
        return all(
            _eval_formula_optimistic(
                child, sem, assignment, domains, completed,
                out_of_scope_codes, assume_out_of_scope_satisfied,
                fixed_var, fixed_val
            )
            for child in formula.get("items", [])
        )
    if kind == "or":
        return any(
            _eval_formula_optimistic(
                child, sem, assignment, domains, completed,
                out_of_scope_codes, assume_out_of_scope_satisfied,
                fixed_var, fixed_val
            )
            for child in formula.get("items", [])
        )
    return False


def _check_prereq_support(
    course: str,
    formula: Optional[Dict[str, Any]],
    var_to_test: str,
    val_to_test: Any,
    assignment: Dict[str, Any],
    domains: Dict[str, Set[Any]],
    completed: Set[str],
    out_of_scope_codes: Set[str],
    assume_out_of_scope_satisfied: bool,
) -> bool:
    """Check whether assigning var_to_test = val_to_test has support under prereq:course."""
    # Case 1: Testing the course itself
    if var_to_test == course:
        if val_to_test == NOT_TAKEN:
            return True
        return _eval_formula_optimistic(
            formula, val_to_test, assignment, domains, completed,
            out_of_scope_codes, assume_out_of_scope_satisfied
        )

    # Case 2: Testing a prerequisite variable of course
    # If course is already assigned:
    if course in assignment:
        course_sem = assignment[course]
        if course_sem == NOT_TAKEN:
            return True
        return _eval_formula_optimistic(
            formula, course_sem, assignment, domains, completed,
            out_of_scope_codes, assume_out_of_scope_satisfied,
            fixed_var=var_to_test, fixed_val=val_to_test
        )

    # If course is unassigned:
    course_domain = domains.get(course, set())
    if NOT_TAKEN in course_domain:
        # course could be NOT_TAKEN, which trivially satisfies prereq:course
        return True

    # Check if there is at least one semester in course's domain that can be satisfied
    for s in course_domain:
        if s == NOT_TAKEN:
            return True
        if _eval_formula_optimistic(
            formula, s, assignment, domains, completed,
            out_of_scope_codes, assume_out_of_scope_satisfied,
            fixed_var=var_to_test, fixed_val=val_to_test
        ):
            return True

    return False


def solve(
    problem: Problem,
    config: SolverConfig,
    enabled_constraints: Optional[Set[str]] = None,
) -> Result:
    """Solve the CSP problem according to the supplied configuration.

    Parameters:
      - problem: Problem dataclass instance.
      - config: SolverConfig specifying search heuristics (MRV, FC, AC-3, degree_tiebreak).
      - enabled_constraints: set of constraint names to enforce (None enforces all).
    """
    start_time = time.perf_counter()

    all_constraints = problem.named_constraints()
    if enabled_constraints is None:
        active_constraints = set(all_constraints.keys())
    else:
        active_constraints = set(enabled_constraints) & set(all_constraints.keys())

    # Map variables to the active constraints touching them
    var_active_constraints: Dict[str, List[Constraint]] = {v: [] for v in problem.variables}
    for c_name in sorted(active_constraints):
        con = all_constraints[c_name]
        for v in con.scope:
            if v in var_active_constraints:
                var_active_constraints[v].append(con)

    # Precompute variable degree (number of enabled constraints touching it)
    var_degree = {v: len(var_active_constraints[v]) for v in problem.variables}

    # Initial domains: convert list to set for O(1) removals and checks
    raw_domains = problem.initial_domains()
    domains: Dict[str, Set[Any]] = {v: set(raw_domains[v]) for v in problem.variables}

    out_of_scope_codes = set(problem.out_of_scope_assumed_courses)
    completed_codes = set(problem.completed)

    stats = {
        "nodes": 0,
        "backtracks": 0,
        "constraint_checks": 0,
        "prunings": 0,
        "time_s": 0.0,
    }

    # Trail for undoing domain prunings: list of (variable, removed_value)
    trail: List[Tuple[str, Any]] = []

    def time_exceeded() -> bool:
        if config.timeout_s is not None:
            if time.perf_counter() - start_time >= config.timeout_s:
                return True
        return False

    def bounds_check(assignment: Dict[str, Any]) -> bool:
        """Check credit caps per semester and category minimums."""
        # 1. credit_cap checks
        for s in range(problem.current_semester + 1, problem.target_semester + 1):
            c_name = f"credit_cap:{s}"
            if c_name not in active_constraints:
                continue

            stats["constraint_checks"] += 1
            # Minimum credits forced into semester s
            forced_credits = 0
            possible_credits = 0
            for v in problem.variables:
                cr = problem.courses[v]["credits"]
                if v in assignment:
                    if assignment[v] == s:
                        forced_credits += cr
                        possible_credits += cr
                else:
                    d = domains[v]
                    if s in d:
                        possible_credits += cr
                        if len(d) == 1:
                            forced_credits += cr

            if forced_credits > problem.max_credits:
                return False
            if problem.min_credits > 0 and len(assignment) == len(problem.variables):
                if forced_credits < problem.min_credits:
                    return False

        # 2. category_min checks
        for cat, req_min in problem.category_minimums.items():
            c_name = f"category_min:{cat}"
            if c_name not in active_constraints:
                continue

            stats["constraint_checks"] += 1
            # Completed credits in this category
            completed_cr = sum(
                problem.courses[c]["credits"]
                for c in completed_codes
                if c in problem.courses and problem.courses[c].get("category") == cat
            )

            taken_cr = completed_cr
            still_possible_cr = 0

            for v in problem.variables:
                if problem.courses[v].get("category") != cat:
                    continue
                cr = problem.courses[v]["credits"]
                if v in assignment:
                    if assignment[v] != NOT_TAKEN:
                        taken_cr += cr
                else:
                    # Still possible if domain contains at least one integer semester
                    if any(val != NOT_TAKEN for val in domains[v]):
                        still_possible_cr += cr

            if taken_cr + still_possible_cr < req_min:
                return False

        return True

    def run_ac3(assignment: Dict[str, Any], initial_queue: List[Tuple[str, str]]) -> bool:
        """Generalized AC-3 over active prereq constraints."""
        queue: collections.deque[Tuple[str, str]] = collections.deque(initial_queue)
        in_queue = set(initial_queue)

        while queue:
            if time_exceeded():
                return False

            var, c_name = queue.popleft()
            in_queue.remove((var, c_name))

            if c_name not in active_constraints:
                continue
            if not c_name.startswith("prereq:"):
                continue

            target_course = c_name[len("prereq:"):]
            formula = problem.courses[target_course].get("formula")

            pruned_any = False
            for val in list(domains[var]):
                stats["constraint_checks"] += 1
                supported = _check_prereq_support(
                    target_course, formula, var, val,
                    assignment, domains, completed_codes,
                    out_of_scope_codes, problem.assume_out_of_scope_satisfied
                )
                if not supported:
                    domains[var].remove(val)
                    trail.append((var, val))
                    stats["prunings"] += 1
                    pruned_any = True
                    if len(domains[var]) == 0:
                        return False

            if pruned_any:
                # Re-add dependent arcs
                for con in var_active_constraints[var]:
                    if con.name.startswith("prereq:") and con.name in active_constraints:
                        for other in con.scope:
                            if other != var and other not in assignment:
                                arc = (other, con.name)
                                if arc not in in_queue:
                                    queue.append(arc)
                                    in_queue.add(arc)

        return True

    def forward_check(var: str, assigned_val: Any, assignment: Dict[str, Any]) -> bool:
        """Prune unassigned variables sharing an active prereq constraint with var."""
        for con in var_active_constraints[var]:
            c_name = con.name
            if c_name not in active_constraints or not c_name.startswith("prereq:"):
                continue

            target_course = c_name[len("prereq:"):]
            formula = problem.courses[target_course].get("formula")

            for neighbor in con.scope:
                if neighbor == var or neighbor in assignment:
                    continue

                for val in list(domains[neighbor]):
                    stats["constraint_checks"] += 1
                    supported = _check_prereq_support(
                        target_course, formula, neighbor, val,
                        assignment, domains, completed_codes,
                        out_of_scope_codes, problem.assume_out_of_scope_satisfied
                    )
                    if not supported:
                        domains[neighbor].remove(val)
                        trail.append((neighbor, val))
                        stats["prunings"] += 1
                        if len(domains[neighbor]) == 0:
                            return False

        return bounds_check(assignment)

    # Initial root propagation
    if config.ac3:
        initial_ac3_queue: List[Tuple[str, str]] = []
        for c_name in sorted(active_constraints):
            if c_name.startswith("prereq:"):
                con = all_constraints[c_name]
                for v in con.scope:
                    initial_ac3_queue.append((v, c_name))

        if not run_ac3({}, initial_ac3_queue):
            stats["time_s"] = time.perf_counter() - start_time
            return Result(status="UNSAT", assignment=None, trace=None, stats=stats)

    if not bounds_check({}):
        stats["time_s"] = time.perf_counter() - start_time
        return Result(status="UNSAT", assignment=None, trace=None, stats=stats)

    # Check for immediately empty domains at root
    for v in problem.variables:
        if len(domains[v]) == 0:
            stats["time_s"] = time.perf_counter() - start_time
            return Result(status="UNSAT", assignment=None, trace=None, stats=stats)

    assignment: Dict[str, Any] = {}

    def select_variable() -> Optional[str]:
        unassigned = [v for v in problem.variables if v not in assignment]
        if not unassigned:
            return None

        if not config.mrv:
            # Static variable ordering: sorted course code
            return min(unassigned)

        # MRV: smallest current domain; tiebreak by degree if requested, then course code
        if config.degree_tiebreak:
            return min(unassigned, key=lambda v: (len(domains[v]), -var_degree[v], v))
        return min(unassigned, key=lambda v: (len(domains[v]), v))

    def order_values(var: str) -> List[Any]:
        # Values ascending: integer semesters ascending, NOT_TAKEN at the end
        vals = list(domains[var])
        sem_vals = sorted([v for v in vals if v != NOT_TAKEN])
        if NOT_TAKEN in vals:
            sem_vals.append(NOT_TAKEN)
        return sem_vals

    def is_consistent_plain(var: str, val: Any) -> bool:
        """Check constraints for plain backtracking as soon as violated."""
        # 1. credit_cap check
        if val != NOT_TAKEN:
            c_name = f"credit_cap:{val}"
            if c_name in active_constraints:
                stats["constraint_checks"] += 1
                curr_load = val_load[val] + problem.courses[var]["credits"]
                if curr_load > problem.max_credits:
                    return False

        # 2. prereq checks
        # Prereq constraint for var itself
        prereq_var = f"prereq:{var}"
        if prereq_var in active_constraints and val != NOT_TAKEN:
            stats["constraint_checks"] += 1
            formula = problem.courses[var].get("formula")
            if not _eval_formula_optimistic(
                formula, val, assignment, domains, completed_codes,
                out_of_scope_codes, problem.assume_out_of_scope_satisfied
            ):
                return False

        # Prereqs of other assigned courses depending on var
        for con in var_active_constraints[var]:
            c_name = con.name
            if not c_name.startswith("prereq:") or c_name not in active_constraints:
                continue
            target_course = c_name[len("prereq:"):]
            if target_course in assignment and target_course != var:
                target_sem = assignment[target_course]
                if target_sem != NOT_TAKEN:
                    stats["constraint_checks"] += 1
                    formula = problem.courses[target_course].get("formula")
                    if not _eval_formula_optimistic(
                        formula, target_sem, assignment, domains, completed_codes,
                        out_of_scope_codes, problem.assume_out_of_scope_satisfied,
                        fixed_var=var, fixed_val=val,
                    ):
                        return False

        # 3. category_min check (only checked when all its variables are assigned)
        cat = problem.courses[var].get("category")
        c_name = f"category_min:{cat}"
        if c_name in active_constraints:
            cat_vars = [v for v in problem.variables if problem.courses[v].get("category") == cat]
            if all(v in assignment or v == var for v in cat_vars):
                stats["constraint_checks"] += 1
                req_min = problem.category_minimums.get(cat, 0)
                completed_cr = sum(
                    problem.courses[c]["credits"]
                    for c in completed_codes
                    if c in problem.courses and problem.courses[c].get("category") == cat
                )
                taken_cr = completed_cr
                for v in cat_vars:
                    v_val = val if v == var else assignment[v]
                    if v_val != NOT_TAKEN:
                        taken_cr += problem.courses[v]["credits"]
                if taken_cr < req_min:
                    return False

        return True

    # Track loads per semester for plain backtracking
    val_load = {s: 0 for s in range(problem.current_semester + 1, problem.target_semester + 1)}

    timed_out = False

    def backtrack() -> bool:
        nonlocal timed_out
        if time_exceeded():
            timed_out = True
            return False

        var = select_variable()
        if var is None:
            # All variables assigned; final verification of all active prereqs and bounds
            for c_name in active_constraints:
                if c_name.startswith("prereq:"):
                    target_course = c_name[len("prereq:"):]
                    c_val = assignment[target_course]
                    if c_val != NOT_TAKEN:
                        formula = problem.courses[target_course].get("formula")
                        if not _eval_formula_optimistic(
                            formula, c_val, assignment, domains, completed_codes,
                            out_of_scope_codes, problem.assume_out_of_scope_satisfied
                        ):
                            return False
            return bounds_check(assignment)

        for val in order_values(var):
            stats["nodes"] += 1

            if time_exceeded():
                timed_out = True
                return False

            # In plain backtracking, check consistency directly
            if not config.forward_checking and not config.ac3:
                if not is_consistent_plain(var, val):
                    stats["backtracks"] += 1
                    continue

            # Apply assignment
            assignment[var] = val
            if val != NOT_TAKEN:
                val_load[val] += problem.courses[var]["credits"]

            trail_mark = len(trail)

            # Restrict domain of var to {val}
            for v_rem in list(domains[var]):
                if v_rem != val:
                    domains[var].remove(v_rem)
                    trail.append((var, v_rem))
                    stats["prunings"] += 1

            success = True

            # Propagate with AC-3 or Forward Checking
            if config.ac3:
                # Add arcs from neighbors sharing prereq constraints with var
                ac3_queue: List[Tuple[str, str]] = []
                for con in var_active_constraints[var]:
                    if con.name.startswith("prereq:") and con.name in active_constraints:
                        for other in con.scope:
                            if other != var and other not in assignment:
                                ac3_queue.append((other, con.name))
                if not run_ac3(assignment, ac3_queue):
                    success = False
                elif not bounds_check(assignment):
                    success = False
            elif config.forward_checking:
                if not forward_check(var, val, assignment):
                    success = False

            if success and not timed_out:
                if backtrack():
                    return True

            # Undo assignment and prunings
            if not timed_out:
                stats["backtracks"] += 1

            while len(trail) > trail_mark:
                t_var, t_val = trail.pop()
                domains[t_var].add(t_val)

            if val != NOT_TAKEN:
                val_load[val] -= problem.courses[var]["credits"]
            del assignment[var]

            if timed_out:
                return False

        return False

    sat = backtrack()
    stats["time_s"] = time.perf_counter() - start_time

    if timed_out:
        return Result(status="TIMEOUT", assignment=None, trace=None, stats=stats)

    if not sat:
        return Result(status="UNSAT", assignment=None, trace=None, stats=stats)

    # Build human-readable trace for SAT assignment
    trace: List[PlacementTrace] = []
    for code in problem.variables:
        val = assignment[code]
        if val == NOT_TAKEN:
            cat = problem.courses[code].get("category", "Discipline Elective")
            reason = f"{cat} not taken; category requirements met by other placed courses"
        else:
            s = val
            # Prereqs explanation
            formula = problem.courses[code].get("formula")
            if formula is None:
                prereq_str = "no prerequisites required"
            else:
                leaf_deps = sorted(list(_collect_leaves_info(formula)))
                dep_reports = []
                for dep_course, dep_rel in leaf_deps:
                    cmp = "<=" if dep_rel == "CO" else "<"
                    if dep_course in completed_codes:
                        dep_reports.append(f"{dep_course} (completed prior, sem 0)")
                    elif dep_course in out_of_scope_codes:
                        dep_reports.append(f"{dep_course} (out of scope, assumed satisfied)")
                    elif dep_course in assignment:
                        dep_sem = assignment[dep_course]
                        dep_reports.append(f"{dep_course} (sem {dep_sem} {cmp} {s})")
                    else:
                        dep_reports.append(f"{dep_course} (unassigned)")
                prereq_str = f"prereqs satisfied: {', '.join(dep_reports)}"

            # Parity explanation
            parity = problem.courses[code].get("parity")
            if parity == "odd":
                parity_str = f"offered in odd terms (sem {s} is odd)"
            elif parity == "even":
                parity_str = f"offered in even terms (sem {s} is even)"
            else:
                parity_str = "no semester parity restriction"

            # Credit room
            sem_load = sum(
                problem.courses[c]["credits"]
                for c in problem.variables
                if assignment[c] == s
            )
            room_str = f"semester {s} load: {sem_load}/{problem.max_credits} credits ({problem.max_credits - sem_load} credits remaining)"

            reason = f"{prereq_str}; {parity_str}; {room_str}."

        trace.append(PlacementTrace(course=code, semester=val, reason=reason))

    # Sort trace chronologically by semester, then course code, NOT_TAKEN at the end
    trace.sort(key=lambda t: (1 if t.semester == NOT_TAKEN else 0, t.semester if t.semester != NOT_TAKEN else 999, t.course))

    return Result(status="SAT", assignment=assignment, trace=trace, stats=stats)


def _collect_leaves_info(formula: Optional[Dict[str, Any]]) -> Set[Tuple[str, str]]:
    """Helper to collect (course, relation) pairs from a formula."""
    if not formula:
        return set()
    kind = formula.get("kind")
    if kind == "leaf":
        return {(formula["course"], formula.get("relation", "PRE"))}
    res: Set[Tuple[str, str]] = set()
    for child in formula.get("items", []):
        res.update(_collect_leaves_info(child))
    return res
