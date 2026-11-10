"""
GraphMind — requirement_resolver.py (Pair A, compatibility shim)

URGENT FIX: this file was removed from the repo root during the migration
to the backend/data + backend/logic + data/curriculum layout (see
MIGRATION_NOTES.md), since its logic was split into those modules. That
removal broke tests/conftest.py, which imports `RequirementResolver` from
this exact path -- this file restores it as a thin compatibility wrapper,
not a duplicate implementation. All actual logic still lives in
backend/data/loader.py, backend/data/validator.py, and backend/logic/.

If tests/conftest.py imports from a DIFFERENT path than repo-root
`requirement_resolver.py` (e.g. `from backend.requirement_resolver import
...`), move/symlink this file to match rather than duplicating it --
check conftest.py's actual import line before assuming this fixes it.

Usage (matches the original pre-migration API):

    from requirement_resolver import RequirementResolver

    resolver = RequirementResolver.load(branch='cse')
    resolver.is_eligible('CS F364', completed={'CS F211', 'CS F222'})
    resolver.why_not_eligible('CS F364', completed={'CS F211'})
    resolver.reachable_from(completed={'CS F111'})
    resolver.category_totals(completed={'CS F111', 'CS F211'})
    resolver.run_all_validations()
"""

import os

from backend.data.loader import load_curriculum
from backend.data.validator import run_all_validations as _run_all_validations
from backend.logic.prerequisite_checker import evaluate, missing_requirements
from backend.logic.forward_chaining import compute_fixpoint_reachable, compute_category_credits

_DEFAULT_CURRICULUM_DIR = os.path.join(os.path.dirname(__file__), 'data', 'curriculum')


class RequirementResolver:
    def __init__(self, curriculum):
        self.curriculum = curriculum
        self.known_codes = curriculum.known_codes()

    # ---- loading ----------------------------------------------------

    @classmethod
    def load(cls, branch=None, minor=None, curriculum_dir=None):
        curriculum_dir = curriculum_dir or _DEFAULT_CURRICULUM_DIR
        curriculum = load_curriculum(curriculum_dir, branch=branch, minor=minor)
        return cls(curriculum)

    def courses_in_scope(self):
        return set(self.curriculum.courses.keys())

    # ---- single-course queries ---------------------------------------

    def formula_for(self, code):
        if code not in self.curriculum.courses:
            raise KeyError(f'{code!r} not found in curriculum')
        return self.curriculum.courses[code].parsed_prerequisites

    def is_eligible(self, code, completed: set, concurrently_taking: set = frozenset()):
        formula = self.formula_for(code)
        return evaluate(formula, completed, concurrently_taking, known_codes=self.known_codes)

    def why_not_eligible(self, code, completed: set, concurrently_taking: set = frozenset()):
        formula = self.formula_for(code)
        return missing_requirements(formula, completed, concurrently_taking)

    # ---- whole-curriculum queries --------------------------------

    def reachable_from(self, completed: set):
        reachable, passes, by_pass = compute_fixpoint_reachable(
            self.curriculum, completed, self.known_codes
        )
        return reachable

    def category_totals(self, completed: set):
        return compute_category_credits(self.curriculum, completed)

    # ---- validation suite -----------------------------------------

    def run_all_validations(self):
        return _run_all_validations(self.curriculum)


if __name__ == '__main__':
    resolver = RequirementResolver.load(branch='cse')
    print(f'Loaded cse: {len(resolver.courses_in_scope())} courses')
    completed = {'CS F111', 'CS F211', 'CS F222'}
    print(f'CS F212 eligible: {resolver.is_eligible("CS F212", completed)}')
    print(f'Validation report: {resolver.run_all_validations()}')
