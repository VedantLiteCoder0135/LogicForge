"""
GraphMind — Forward-Chaining Fixpoint Closure (Pair A)

Implements the requirement-resolution engine described in the proposal:
applies derivation rules repeatedly until no new facts are derivable.

Two derivation rules are modeled here:

  R1 (course-unlock cascade): if a course's prerequisite formula evaluates
     to true given the current 'reachable' set, that course becomes
     reachable too. Completing one course can make a whole chain of
     subsequent courses reachable in the same pass, and newly-reachable
     courses can themselves unlock further courses in the NEXT pass -- this
     is exactly why a single pass isn't enough and we need a fixpoint loop.

  R2 (category credit accumulation): given a course -> category assignment
     and a credits-per-course table, sum credits earned so far per
     requirement category. This doesn't itself gate anything in our model
     (no course in the data we've seen requires "N credits in category X" as
     a literal prerequisite leaf), but it's needed for two of the
     validation-suite checks below, and for the CSP/A* planner's category
     credit-floor constraint later.

NOTE ON PLACEHOLDER DATA: credits and requirement-category assignments are
NOT present in prereqs.json (confirmed when we built the KB). The file
credits_categories.json alongside this script is a SMALL, CLEARLY-MARKED
PLACEHOLDER covering a handful of real course codes from the KB, so this
engine and its validation checks can be built, tested, and explained now.
It must be replaced with the real table sourced from the Academic
Regulations / curriculum handout before this is used on real student data.
"""

import json
from entailment import evaluate, UnresolvedReferenceError


def compute_fixpoint_reachable(kb_by_code: dict, initial_completed: set, known_codes: set):
    """
    R1: starting from `initial_completed`, repeatedly scan every course not
    yet in the reachable set and add it if its formula now evaluates True.
    Stops when a full pass adds nothing new (the fixpoint). Returns
    (reachable_set, passes_taken, newly_unlocked_by_pass) -- the last item
    is kept so we can show the cascade pass-by-pass, which is useful both
    for debugging and for the derivation trace GraphMind promises.
    """
    reachable = set(initial_completed)
    newly_unlocked_by_pass = []

    while True:
        unlocked_this_pass = []
        for code, rec in kb_by_code.items():
            if code in reachable:
                continue
            formula = rec['formula']
            try:
                if evaluate(formula, completed=reachable, known_codes=known_codes, lenient=True):
                    unlocked_this_pass.append(code)
            except UnresolvedReferenceError:
                continue  # shouldn't happen with lenient=True, kept for safety
        if not unlocked_this_pass:
            break
        reachable.update(unlocked_this_pass)
        newly_unlocked_by_pass.append(sorted(unlocked_this_pass))

    return reachable, len(newly_unlocked_by_pass), newly_unlocked_by_pass


def compute_category_credits(completed: set, credits_by_code: dict, category_by_code: dict):
    """
    R2: sum credits of completed courses per requirement category. Courses
    with no category assignment in the (placeholder) table are ignored here
    (they simply don't count toward any category total) rather than raising,
    since the real curriculum table will have far more courses than our
    placeholder slice.
    """
    totals = {}
    for code in completed:
        category = category_by_code.get(code)
        credits = credits_by_code.get(code)
        if category is None or credits is None:
            continue
        totals[category] = totals.get(category, 0) + credits
    return totals


# ---------------------------------------------------------------------------
# Validation checks that depend on the fixpoint engine
# ---------------------------------------------------------------------------

def check_unreachable_courses(kb_by_code: dict, known_codes: set):
    """
    'Courses unreachable within the degree horizon' (ignoring term-count and
    credit-ceiling limits, which belong to the CSP/A* layer, not this
    structural check): starting from an empty completed set, run the
    fixpoint. Any course never added is structurally unreachable -- every
    path to it runs through a cycle (we already checked there are none) or
    a dead end (an unresolved reference, or a prerequisite that is itself
    unreachable). This is a necessary-but-not-sufficient sanity check: a
    course CAN be reachable here and still be practically unreachable once
    term-parity and credit ceilings are added by the planner.
    """
    reachable, _, _ = compute_fixpoint_reachable(kb_by_code, set(), known_codes)
    unreachable = sorted(set(kb_by_code.keys()) - reachable)
    return unreachable


def check_category_floor(all_courses_by_category: dict, credits_by_code: dict,
                          category_minimums: dict):
    """
    'Categories whose eligible-course credit total falls below their own
    minimum': this is a KB well-formedness check, not a per-student check --
    it asks whether the curriculum, as encoded, even CAN satisfy each
    category's stated credit floor if a student took every course assigned
    to that category. If the ceiling of available credit in a category is
    already below its floor, no valid plan can ever exist for that
    category, and that's a KB-authoring error worth catching immediately.
    """
    violations = {}
    for category, course_codes in all_courses_by_category.items():
        total_available = sum(credits_by_code.get(c, 0) for c in course_codes)
        minimum = category_minimums.get(category)
        if minimum is not None and total_available < minimum:
            violations[category] = {
                'minimum_required': minimum,
                'total_available_if_all_taken': total_available,
            }
    return violations


if __name__ == '__main__':
    with open('kb_courses.json') as f:
        kb = json.load(f)
    kb_by_code = {c['code']: c for c in kb}
    known_codes = set(kb_by_code.keys())

    with open('credits_categories.json') as f:
        placeholder = json.load(f)
    credits_by_code = placeholder['credits_by_code']
    category_by_code = placeholder['category_by_code']
    category_minimums = placeholder['category_minimums']

    # ---- demo 1: course-unlock cascade from a small starting transcript ----
    starting_transcript = {'BIO F111', 'BIO F110'}
    reachable, passes, by_pass = compute_fixpoint_reachable(kb_by_code, starting_transcript, known_codes)
    print(f'Starting from {sorted(starting_transcript)}:')
    print(f'  fixpoint reached after {passes} pass(es)')
    for i, unlocked in enumerate(by_pass, start=1):
        print(f'  pass {i} newly unlocked ({len(unlocked)}): {unlocked[:8]}{"..." if len(unlocked) > 8 else ""}')
    print(f'  total reachable (incl. starting courses): {len(reachable)} of {len(kb_by_code)} KB courses\n')

    # ---- demo 2: category credit accumulation ----
    totals = compute_category_credits(starting_transcript, credits_by_code, category_by_code)
    print(f'Category credits earned from {sorted(starting_transcript)}: {totals}\n')

    # ---- validation: unreachable-within-horizon (structural) ----
    unreachable = check_unreachable_courses(kb_by_code, known_codes)
    print(f'Structurally unreachable courses (from a cold start, ignoring term limits): {len(unreachable)}')
    print(f'  sample: {unreachable[:10]}\n')

    # ---- validation: category credit floor ----
    all_by_category = {}
    for code, cat in category_by_code.items():
        all_by_category.setdefault(cat, []).append(code)
    floor_violations = check_category_floor(all_by_category, credits_by_code, category_minimums)
    print(f'Category credit-floor violations (placeholder data): {floor_violations}')
