"""
GraphMind — tests/test_prerequisites.py (Pair A)

Tests for backend/logic/prerequisite_parser.py and prerequisite_checker.py,
against real course data loaded through backend/data/loader.py.
Run with: python3 -m pytest tests/test_prerequisites.py -v
(or python3 tests/test_prerequisites.py to run without pytest)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.data.loader import load_curriculum
from backend.logic.prerequisite_checker import evaluate, missing_requirements, UnresolvedReferenceError

CURRICULUM_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'curriculum')


def _load():
    return load_curriculum(CURRICULUM_DIR, branch='cse')


def test_plain_and_chain():
    curr = _load()
    course = curr.courses['CS F213']  # requires CS F111
    assert evaluate(course.parsed_prerequisites, completed=set()) is False
    assert evaluate(course.parsed_prerequisites, completed={'CS F111'}) is True


def test_or_alternatives():
    curr = _load()
    course = curr.courses['CS F211']  # (CS F222 OR MATH F213)
    assert evaluate(course.parsed_prerequisites, completed=set()) is False
    assert evaluate(course.parsed_prerequisites, completed={'CS F222'}) is True
    # MATH F213 is outside the loaded branch/common scope, so it's an
    # unresolved reference here -- that's expected, not a bug (see
    # VALIDATION_STATUS.md). Use lenient mode to test entailment logic
    # alone, independent of that scope gap.
    assert evaluate(course.parsed_prerequisites, completed={'MATH F213'}, lenient=True) is True


def test_no_prerequisite_course_is_open():
    curr = _load()
    course = curr.courses['CS F212']
    assert course.parsed_prerequisites is None
    assert evaluate(course.parsed_prerequisites, completed=set()) is True


def test_and_of_two_leaves():
    curr = _load()
    course = curr.courses['CS F342']  # CS F241 AND CS F215
    assert evaluate(course.parsed_prerequisites, completed={'CS F241'}) is False
    assert evaluate(course.parsed_prerequisites, completed={'CS F241', 'CS F215'}) is True


def test_missing_requirements_explanation():
    curr = _load()
    course = curr.courses['CS F351']  # CS F222 AND CS F214
    reason = missing_requirements(course.parsed_prerequisites, completed={'CS F222'})
    assert reason is not None
    assert 'CS F214' in reason


def test_eee_branch_loads_and_entails():
    curr = load_curriculum(CURRICULUM_DIR, branch='eee')
    # common/EEE F111 pulled in automatically by the loader
    assert 'EEE F111' in curr.courses
    f211 = curr.courses['EEE F211']  # requires EEE F111
    assert evaluate(f211.parsed_prerequisites, completed=set()) is False
    assert evaluate(f211.parsed_prerequisites, completed={'EEE F111'}) is True
    f313 = curr.courses['EEE F313']  # (EEE F244 OR ECE F244)
    assert evaluate(f313.parsed_prerequisites, completed={'EEE F244'}) is True


def test_unresolved_reference_raises_by_default():
    curr = _load()
    known = curr.known_codes()
    course = curr.courses['CS F211']  # references MATH F213, outside scope
    raised = False
    try:
        evaluate(course.parsed_prerequisites, completed=set(), known_codes=known)
    except UnresolvedReferenceError:
        raised = True
    assert raised


if __name__ == '__main__':
    tests = [v for k, v in list(globals().items()) if k.startswith('test_')]
    passed, failed = 0, 0
    for t in tests:
        try:
            t()
            print(f'[OK] {t.__name__}')
            passed += 1
        except AssertionError as e:
            print(f'[FAIL] {t.__name__}: {e}')
            failed += 1
    print(f'\n{passed} passed, {failed} failed')
