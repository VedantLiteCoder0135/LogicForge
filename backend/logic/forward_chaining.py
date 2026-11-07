"""
GraphMind — backend/logic/forward_chaining.py (Pair A)

Forward-chaining requirement-resolution engine: course-unlock cascade
(R1) and category credit accumulation (R2), as described in
docs/proposal.pdf. Operates on whatever Curriculum/Course objects
backend/data/loader.py hands it -- duck-typed on the interface below so
it doesn't need to import backend/models/ directly (Pair B/C own that
module and may still be finalizing its exact class shape):

    a "curriculum" is anything with .courses: dict[code -> course]
    a "course" is anything with .code, .credits, .category,
        .parsed_prerequisites (the tree from prerequisite_parser)

See backend/data/loader.py for the concrete objects currently used to
satisfy this interface.
"""

from .prerequisite_checker import evaluate, UnresolvedReferenceError


def compute_fixpoint_reachable(curriculum, initial_completed: set, known_codes: set):
    """R1: course-unlock cascade. Returns (reachable_set, passes_taken,
    newly_unlocked_by_pass)."""
    reachable = set(initial_completed)
    newly_unlocked_by_pass = []

    while True:
        unlocked_this_pass = []
        for code, course in curriculum.courses.items():
            if code in reachable:
                continue
            try:
                if evaluate(course.parsed_prerequisites, completed=reachable,
                            known_codes=known_codes, lenient=True):
                    unlocked_this_pass.append(code)
            except UnresolvedReferenceError:
                continue
        if not unlocked_this_pass:
            break
        reachable.update(unlocked_this_pass)
        newly_unlocked_by_pass.append(sorted(unlocked_this_pass))

    return reachable, len(newly_unlocked_by_pass), newly_unlocked_by_pass


def compute_category_credits(curriculum, completed: set):
    """R2: sum credits of completed courses per requirement category."""
    totals = {}
    for code in completed:
        course = curriculum.courses.get(code)
        if course is None or course.category is None:
            continue
        totals[course.category] = totals.get(course.category, 0) + course.credits
    return totals
