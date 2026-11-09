"""
GraphMind — backend/logic/prerequisite_checker.py (Pair A)

Entailment: given a parsed prerequisite formula tree (from
prerequisite_parser.parse_prerequisites) and a student's state, answer
"is this course eligible right now." Same logic as Pair A's original
entailment.py; moved here and adapted to the new module layout, with no
change to the underlying semantics -- see docs/architecture.md §3 for
why this distinction (PRE vs CO) matters to the shared PlanningProblem
both solvers consume.
"""


class UnresolvedReferenceError(Exception):
    """Raised when a formula references a course code the curriculum
    doesn't have, unless the caller opts into lenient mode."""


def evaluate(formula, completed: set, concurrently_taking: set = frozenset(),
             known_codes: set = None, lenient: bool = False) -> bool:
    if formula is None:
        return True

    if formula['kind'] == 'leaf':
        course = formula['course']
        if known_codes is not None and course not in known_codes:
            if lenient:
                return True
            raise UnresolvedReferenceError(
                f'Formula references unknown course code: {course!r}'
            )
        if formula['relation'] == 'CO':
            return course in completed or course in concurrently_taking
        return course in completed

    if formula['kind'] == 'and':
        return all(
            evaluate(child, completed, concurrently_taking, known_codes, lenient)
            for child in formula['items']
        )

    if formula['kind'] == 'or':
        return any(
            evaluate(child, completed, concurrently_taking, known_codes, lenient)
            for child in formula['items']
        )

    raise ValueError(f"Unknown formula node kind: {formula.get('kind')!r}")


def missing_requirements(formula, completed: set, concurrently_taking: set = frozenset()):
    """Human-readable explanation of what's missing -- feeds
    backend/explanations/plan_explainer.py's derivation trace (Pair D)."""
    if formula is None or evaluate(formula, completed, concurrently_taking, known_codes=None, lenient=True):
        return None

    if formula['kind'] == 'leaf':
        rel = 'co-requisite' if formula['relation'] == 'CO' else 'prerequisite'
        return f"missing {rel}: {formula['course']}"

    if formula['kind'] == 'and':
        unsatisfied = [
            missing_requirements(child, completed, concurrently_taking)
            for child in formula['items']
        ]
        unsatisfied = [u for u in unsatisfied if u is not None]
        return '; '.join(unsatisfied)

    if formula['kind'] == 'or':
        branch_reports = []
        for child in formula['items']:
            if evaluate(child, completed, concurrently_taking, known_codes=None, lenient=True):
                continue
            branch_reports.append(missing_requirements(child, completed, concurrently_taking))
        if len(formula['items']) > 1:
            nearest = min(branch_reports, key=len) if branch_reports else None
            return f"need ONE of [{' OR '.join(branch_reports)}] (closest: {nearest})"
        return branch_reports[0] if branch_reports else None
