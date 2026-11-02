"""
GraphMind — Requirement Resolver (Pair A deliverable, integration layer)

This is the single module the rest of the system (Constraint Model Builder,
CSP Solver, A* Planner) imports from -- it wraps everything Pair A built
(KB loader, entailment evaluator, forward-chaining fixpoint engine) behind
one clean API, matching the "Requirement Resolver" box in the architecture
diagram in the proposal.

Usage:

    from requirement_resolver import RequirementResolver

    resolver = RequirementResolver.load(
        kb_path='kb_courses.json',
        scope_path='curriculum_scope.json',   # optional; narrows to a scope
    )

    resolver.is_eligible('CS F364', completed={'CS F211', 'CS F222'})
    resolver.why_not_eligible('CS F364', completed={'CS F211'})
    resolver.reachable_from(completed={'CS F111'})
    resolver.category_totals(completed={'CS F111', 'CS F211'})
    resolver.run_all_validations()

Everything here is pure/read-only over the KB -- no mutation, no I/O beyond
the initial load, so it's safe for Pair B/C to call repeatedly inside a
backtracking search loop without worrying about shared-state bugs.
"""

import json

from entailment import evaluate, missing_requirements, UnresolvedReferenceError
from fixpoint import (
    compute_fixpoint_reachable,
    compute_category_credits,
    check_unreachable_courses,
    check_category_floor,
)
from build_kb import build as rebuild_kb_from_raw  # re-exported for convenience/CI


class RequirementResolver:
    def __init__(self, kb_by_code: dict, credits_by_code: dict,
                 category_by_code: dict, category_minimums: dict):
        self.kb_by_code = kb_by_code
        self.known_codes = set(kb_by_code.keys())
        self.credits_by_code = credits_by_code
        self.category_by_code = category_by_code
        self.category_minimums = category_minimums

    # ---- loading ----------------------------------------------------

    @classmethod
    def load(cls, kb_path='kb_courses.json', scope_path=None):
        with open(kb_path) as f:
            kb_list = json.load(f)
        kb_by_code = {c['code']: c for c in kb_list}

        credits_by_code, category_by_code, category_minimums = {}, {}, {}
        if scope_path:
            with open(scope_path) as f:
                scope = json.load(f)
            for entry in scope['courses']:
                credits_by_code[entry['code']] = entry['credits']
                category_by_code[entry['code']] = entry['category']
            category_minimums = scope.get('category_minimums', {})

        return cls(kb_by_code, credits_by_code, category_by_code, category_minimums)

    def courses_in_scope(self):
        """If a scope was loaded, the course codes it covers; otherwise the
        full KB. Pairs B/C should typically build their CSP/search variables
        from this, not from the raw KB, to respect the project's declared
        'focused curriculum scope' design decision (proposal, Sec. 3)."""
        if self.category_by_code:
            return set(self.category_by_code.keys())
        return set(self.known_codes)

    # ---- single-course queries ---------------------------------------

    def formula_for(self, code):
        if code not in self.kb_by_code:
            raise KeyError(f'{code!r} not found in KB')
        return self.kb_by_code[code]['formula']

    def is_eligible(self, code, completed: set, concurrently_taking: set = frozenset()):
        formula = self.formula_for(code)
        return evaluate(formula, completed, concurrently_taking, known_codes=self.known_codes)

    def why_not_eligible(self, code, completed: set, concurrently_taking: set = frozenset()):
        """Returns None if already eligible, else a human-readable reason --
        the basis for GraphMind's per-course derivation trace."""
        formula = self.formula_for(code)
        return missing_requirements(formula, completed, concurrently_taking)

    # ---- whole-KB / whole-plan queries --------------------------------

    def reachable_from(self, completed: set):
        """Full forward-chaining closure: every course reachable (eventually
        eligible) starting from `completed`, ignoring term/credit limits --
        those are the CSP/A* layer's job, not the resolver's."""
        reachable, passes, by_pass = compute_fixpoint_reachable(
            self.kb_by_code, completed, self.known_codes
        )
        return reachable

    def category_totals(self, completed: set):
        if not self.category_by_code:
            raise ValueError('No curriculum scope loaded -- call load(..., scope_path=...) first')
        return compute_category_credits(completed, self.credits_by_code, self.category_by_code)

    # ---- validation suite (run once, at KB-build time / CI) -----------

    def run_all_validations(self):
        """Returns a single combined report: everything build_kb.py's own
        validation already found (duplicates, unresolved refs, cycles,
        mixed-connective flags -- loaded from validation_report.json if
        present) plus the two fixpoint-dependent checks (structural
        unreachability, category credit floor) computed fresh here."""
        report = {}
        try:
            with open('validation_report.json') as f:
                report['kb_structural'] = json.load(f)
        except FileNotFoundError:
            report['kb_structural'] = 'validation_report.json not found -- run build_kb.py first'

        report['structurally_unreachable_courses'] = check_unreachable_courses(
            self.kb_by_code, self.known_codes
        )

        # A scope course can be "unreachable" for two very different reasons:
        # genuinely gated behind something uncompletable, or simply ABSENT
        # from the KB (the source export never had a row for it at all, e.g.
        # a newer elective). These need different fixes, so report separately.
        if self.category_by_code:
            scope_codes = set(self.category_by_code.keys())
            report['scope_courses_missing_from_kb_entirely'] = sorted(
                scope_codes - self.known_codes
            )

        if self.category_by_code:
            all_by_category = {}
            for code, cat in self.category_by_code.items():
                all_by_category.setdefault(cat, []).append(code)
            report['category_floor_violations'] = check_category_floor(
                all_by_category, self.credits_by_code, self.category_minimums
            )
        else:
            report['category_floor_violations'] = 'no curriculum scope loaded -- skipped'

        return report


# ---------------------------------------------------------------------------
# Demonstration / smoke test, run as a script
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    resolver = RequirementResolver.load(
        kb_path='kb_courses.json',
        scope_path='curriculum_scope.json',
    )

    print(f'Courses in declared curriculum scope: {len(resolver.courses_in_scope())}')

    # A student who has done the common first-year-equivalent CS courses
    completed = {'CS F111', 'CS F211', 'CS F222'}
    print(f'\nCompleted: {sorted(completed)}')

    for code in ['CS F212', 'CS F364', 'CS F351', 'CS F372']:
        eligible = resolver.is_eligible(code, completed)
        reason = resolver.why_not_eligible(code, completed)
        print(f'  {code}: eligible={eligible}' + (f'  (blocked by: {reason})' if reason else ''))

    reachable = resolver.reachable_from(completed)
    scope_reachable = reachable & resolver.courses_in_scope()
    print(f'\nReachable within declared scope from this transcript: {len(scope_reachable)} '
          f'of {len(resolver.courses_in_scope())}')

    totals = resolver.category_totals(completed)
    print(f'Category credit totals so far: {totals}')

    print('\nFull validation report:')
    report = resolver.run_all_validations()
    print(f"  structurally unreachable (whole KB): {len(report['structurally_unreachable_courses'])}")
    print(f"  category floor violations (scope):   {report['category_floor_violations']}")
    print(f"  scope courses missing from KB entirely: {report['scope_courses_missing_from_kb_entirely']}")
