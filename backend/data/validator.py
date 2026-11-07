"""
GraphMind — backend/data/validator.py (Pair A)

The four validation checks docs/data_schema.md §5 and the proposal
specify, run against a loaded Curriculum (backend/data/loader.py):

  1. prerequisite-graph cycles
  2. undefined course codes referenced by a prerequisite or
     eligible_courses entry
  3. categories whose eligible-course credit total falls below their
     own credit_minimum
  4. courses unreachable within the degree horizon (structural check;
     ignores term-count and credit-ceiling limits, which are the
     CSP/A* layer's job -- see backend/logic/forward_chaining.py's
     docstring)

This is the module VALIDATION_STATUS.md's rows refer to: a branch's row
there should say "passed" only once this has actually been run against
it with zero unresolved issues (or with remaining issues explicitly
accepted and documented, as in the ~21 pattern-inferred courses
described in the original Pair A README).
"""

from collections import defaultdict

from ..logic.forward_chaining import compute_fixpoint_reachable
from ..logic.prerequisite_checker import evaluate


def _collect_leaf_courses(formula):
    if formula is None:
        return set()
    if formula['kind'] == 'leaf':
        return {formula['course']}
    out = set()
    for child in formula['items']:
        out |= _collect_leaf_courses(child)
    return out


def check_undefined_course_codes(curriculum):
    """Check 2: a prerequisite or eligible_courses entry pointing to a
    course code that doesn't exist anywhere in this curriculum."""
    known = curriculum.known_codes()
    unresolved = defaultdict(list)

    for code, course in curriculum.courses.items():
        for ref in _collect_leaf_courses(course.parsed_prerequisites):
            if ref not in known:
                unresolved[ref].append(code)

    for category, req in curriculum.requirements.items():
        for ref in req.eligible_courses:
            if ref not in known:
                unresolved[ref].append(f'<requirement:{category}>')

    return {ref: sorted(set(referrers)) for ref, referrers in unresolved.items()}


def check_cycles(curriculum):
    """Check 1: DFS over PRE-only edges (CO edges are same-term, not
    'before', and are correctly excluded)."""
    known = curriculum.known_codes()
    graph = defaultdict(set)
    for code, course in curriculum.courses.items():
        formula = course.parsed_prerequisites
        if formula is None:
            continue
        for leaf_course, relation in _iter_leaves_with_relation(formula):
            if relation == 'PRE' and leaf_course in known:
                graph[code].add(leaf_course)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = defaultdict(int)
    cycles = []

    def dfs(node, path):
        color[node] = GRAY
        path.append(node)
        for nxt in graph.get(node, ()):
            if color[nxt] == GRAY:
                idx = path.index(nxt)
                cycles.append(path[idx:] + [nxt])
            elif color[nxt] == WHITE:
                dfs(nxt, path)
        path.pop()
        color[node] = BLACK

    for n in list(graph.keys()):
        if color[n] == WHITE:
            dfs(n, [])
    return cycles


def _iter_leaves_with_relation(formula):
    if formula['kind'] == 'leaf':
        yield formula['course'], formula['relation']
    else:
        for child in formula['items']:
            yield from _iter_leaves_with_relation(child)


def check_category_floor(curriculum):
    """Check 3: can the curriculum, as encoded, even satisfy each
    category's own stated credit_minimum if every eligible course in
    that category were taken?"""
    by_category = defaultdict(list)
    for code, course in curriculum.courses.items():
        if course.category:
            by_category[course.category].append(code)
    for category, req in curriculum.requirements.items():
        for code in req.eligible_courses:
            by_category[category].append(code)

    violations = {}
    for category, req in curriculum.requirements.items():
        codes = set(by_category.get(category, []))
        total_available = sum(
            curriculum.courses[c].credits for c in codes if c in curriculum.courses
        )
        if total_available < req.credit_minimum:
            violations[category] = {
                'credit_minimum': req.credit_minimum,
                'total_available_if_all_taken': total_available,
            }
    return violations


def check_unreachable_courses(curriculum):
    """Check 4: structural reachability from a cold start (empty
    completed set), ignoring term/credit limits."""
    known = curriculum.known_codes()
    reachable, _, _ = compute_fixpoint_reachable(curriculum, set(), known)
    return sorted(known - reachable)


def run_all_validations(curriculum):
    return {
        'branch': curriculum.branch_name,
        'course_count': len(curriculum.courses),
        'cycles': check_cycles(curriculum),
        'undefined_course_codes': check_undefined_course_codes(curriculum),
        'category_floor_violations': check_category_floor(curriculum),
        'unreachable_courses': check_unreachable_courses(curriculum),
    }


if __name__ == '__main__':
    import json
    import os
    from .loader import load_curriculum

    curriculum_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'curriculum')
    curr = load_curriculum(curriculum_dir, branch='cse')
    report = run_all_validations(curr)
    print(json.dumps(report, indent=2))
