"""
GraphMind — Prerequisite Entailment Evaluator (Pair A)

Evaluates a course's prerequisite formula (as produced by build_kb.py) against
a student's state to answer: "is this course currently eligible?"

A formula node is one of:
    {'kind': 'leaf', 'course': <code>, 'relation': 'PRE' | 'CO'}
    {'kind': 'and',  'items': [node, ...]}
    {'kind': 'or',   'items': [node, ...]}

Two different questions matter here, and they are NOT the same evaluation:

1. Entailment against completed courses only (strict "PRE" semantics):
   can the student register for this course RIGHT NOW, given what they have
   *already finished* in past terms? A 'CO' leaf does NOT need to already be
   completed for this question -- co-requisites are satisfied by being taken
   in the SAME term, which this function alone can't see (that needs the
   term-assignment context from the CSP/search planner). So this evaluator
   treats a CO leaf as satisfied if the course is in the "committed" set
   (completed OR concurrently registered this term), which the caller
   supplies explicitly -- see `evaluate`.

2. Reference resolution: whether every leaf in the formula refers to a code
   that actually exists in the KB. We don't want a malformed or
   unresolved-reference formula to silently evaluate as satisfiable just
   because of a Python truthiness accident -- so `evaluate` raises if asked
   to evaluate a formula containing a leaf for an unknown course code, unless
   the caller explicitly opts into lenient mode (treat unknown refs as
   automatically satisfied, useful only for debugging/fuzzing, never for a
   real planning run).

No prerequisite formula (`formula is None`) means the course is open with no
gating -- trivially satisfied.
"""

import json


class UnresolvedReferenceError(Exception):
    """Raised when a formula references a course code the KB doesn't have,
    and the caller did not opt into lenient mode."""


def evaluate(formula, completed: set, concurrently_taking: set = frozenset(),
             known_codes: set = None, lenient: bool = False) -> bool:
    """
    Returns True iff `formula` is satisfied given:
      - completed: course codes the student has already finished in a
        PRIOR term (eligible to satisfy a PRE leaf).
      - concurrently_taking: course codes the student is registered for IN
        THE SAME TARGET TERM (eligible to satisfy a CO leaf, together with
        anything in `completed` -- a course finished earlier obviously also
        satisfies a corequisite).
      - known_codes: the full set of valid course codes in the KB, used to
        catch unresolved references. Pass None to skip this check (e.g. if
        you've already validated the KB once and trust it).
      - lenient: if True, a leaf referencing an unknown code is treated as
        satisfied rather than raising. Only use this for debugging.
    """
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
        # default / 'PRE': must be already completed in an earlier term
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
    """
    Explanation support: given a formula that currently evaluates to False,
    return a human-readable description of what's missing. This is the kind
    of derivation trace GraphMind promises for every plan decision.

    We don't try to find the *single cheapest* fix (that's the infeasibility
    analyser's job, built on minimal-core extraction) -- just report, for an
    AND node, every unsatisfied branch, and for an OR node, the one 'nearest'
    branch (fewest total missing leaves) as the natural suggestion, while
    noting the alternative paths exist.
    """
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
                continue  # this branch is actually fine; OR overall would be satisfied
            branch_reports.append(missing_requirements(child, completed, concurrently_taking))
        if len(formula['items']) > 1:
            nearest = min(branch_reports, key=len) if branch_reports else None
            return f"need ONE of [{' OR '.join(branch_reports)}] (closest: {nearest})"
        return branch_reports[0] if branch_reports else None


# ---------------------------------------------------------------------------
# Self-test against the real KB built in build_kb.py
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    with open('kb_courses.json') as f:
        kb = json.load(f)
    by_code = {c['code']: c for c in kb}
    known_codes = set(by_code.keys())

    def formula_for(code):
        return by_code[code]['formula']

    tests_passed = 0
    tests_failed = 0

    def check(label, actual, expected):
        global tests_passed, tests_failed
        ok = actual == expected
        tests_passed += ok
        tests_failed += not ok
        print(f"[{'OK' if ok else 'FAIL'}] {label}: got {actual}, expected {expected}")

    # Simple AND chain: BIO F312 needs both BIO F211 and BIO F111
    f = formula_for('BIO F312')
    check('BIO F312 with nothing completed', evaluate(f, completed=set()), False)
    check('BIO F312 with only BIO F111', evaluate(f, completed={'BIO F111'}), False)
    check('BIO F312 with both prereqs', evaluate(f, completed={'BIO F111', 'BIO F211'}), True)

    # Real OR-of-cross-listed-equivalents case found in the data: EEE F437
    # needs ONE of ECE/ECOM/EEE/INSTR F214.
    f = formula_for('EEE F437')
    check('EEE F437 with none completed', evaluate(f, completed=set()), False)
    check('EEE F437 with EEE F214 only', evaluate(f, completed={'EEE F214'}), True)
    check('EEE F437 with ECOM F214 only', evaluate(f, completed={'ECOM F214'}), True)
    check('EEE F437 with an unrelated course', evaluate(f, completed={'CS F111'}), False)

    # Co-requisite case: BIO G515 lists BIO F341 as CO (can take same term)
    f = formula_for('BIO G515')
    check('BIO G515, prereq not completed/concurrent', evaluate(f, completed=set()), False)
    check(
        'BIO G515, BIO F341 taken concurrently (not yet completed)',
        evaluate(f, completed=set(), concurrently_taking={'BIO F341'}),
        True,
    )
    check(
        'BIO G515, BIO F341 already completed earlier',
        evaluate(f, completed={'BIO F341'}),
        True,
    )

    # No-prereq course should be trivially open
    f = formula_for('BIO F110')
    check('BIO F110 (no prereqs) always open', evaluate(f, completed=set()), True)

    # Unresolved reference should raise unless lenient
    import copy
    poisoned = copy.deepcopy(formula_for('BIO F312'))
    poisoned['items'][0]['course'] = 'ZZZZ F999'
    raised = False
    try:
        evaluate(poisoned, completed=set(), known_codes=known_codes)
    except UnresolvedReferenceError:
        raised = True
    check('unresolved reference raises by default', raised, True)
    check(
        'unresolved reference tolerated in lenient mode (poisoned leaf passes, BIO F111 still missing)',
        evaluate(poisoned, completed=set(), known_codes=known_codes, lenient=True),
        False,  # AND's second branch (BIO F111) is still unsatisfied even though the first is leniently OK
    )
    check(
        'lenient mode genuinely satisfies the poisoned leaf once the other branch is met',
        evaluate(poisoned, completed={'BIO F111'}, known_codes=known_codes, lenient=True),
        True,
    )

    # missing_requirements explanation trace, on a real multi-branch case
    f = formula_for('EEE F437')
    print('\nExplanation trace for EEE F437 with nothing completed:')
    print(' ', missing_requirements(f, completed=set()))

    f = formula_for('BIO F312')
    print('Explanation trace for BIO F312 with only BIO F111 completed:')
    print(' ', missing_requirements(f, completed={'BIO F111'}))

    print(f'\n{tests_passed} passed, {tests_failed} failed')
