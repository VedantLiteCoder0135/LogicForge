"""
GraphMind — tests/test_data_validation.py (Pair A)

Tests for backend/data/validator.py's four checks, against the real
cse branch curriculum data. Run with:
    python3 -m pytest tests/test_data_validation.py -v
or:
    python3 tests/test_data_validation.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.data.loader import load_curriculum
from backend.data.validator import (
    check_cycles,
    check_undefined_course_codes,
    check_category_floor,
    check_unreachable_courses,
    run_all_validations,
)

CURRICULUM_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'curriculum')


def test_cse_has_no_cycles():
    curr = load_curriculum(CURRICULUM_DIR, branch='cse')
    assert check_cycles(curr) == []


def test_cse_has_no_undefined_references():
    """
    MATH F111/F112/F113/F213 were added to common/courses.json (real
    credits/titles from the bulletin, all genuinely prerequisite-free),
    closing what was previously a documented gap. cse should now be
    fully closed.
    """
    curr = load_curriculum(CURRICULUM_DIR, branch='cse')
    undefined = check_undefined_course_codes(curr)
    assert undefined == {}, f'Unexpected undefined references: {undefined}'


def test_cse_category_floor_passes():
    curr = load_curriculum(CURRICULUM_DIR, branch='cse')
    violations = check_category_floor(curr)
    assert violations == {}, f'Unexpected category floor violations: {violations}'


def test_cse_unreachable_courses():
    curr = load_curriculum(CURRICULUM_DIR, branch='cse')
    assert check_unreachable_courses(curr) == []


def test_eee_has_no_cycles():
    curr = load_curriculum(CURRICULUM_DIR, branch='eee')
    assert check_cycles(curr) == []


def test_eee_category_floor_passes():
    """
    11 real Discipline Elective courses (35 credits available) were added
    from the bulletin's EEE elective listing, closing what was previously
    a documented gap (0 of 12 units available). See VALIDATION_STATUS.md.
    """
    curr = load_curriculum(CURRICULUM_DIR, branch='eee')
    violations = check_category_floor(curr)
    assert violations == {}, f'Unexpected category floor violations: {violations}'


def test_eee_known_undefined_references():
    """
    Documented, expected, intentional gap (VALIDATION_STATUS.md): several
    eee courses reference cross-department elective alternatives (ECE and
    INSTR variants of the same course). These are genuinely a different
    branch -- building them out would mean encoding the entire ECE/INSTR
    curriculum, which is out of this project's declared focused scope.
    The MATH F111/F112 gap (for the MATH F212 Optimization slot) was
    closed by adding those courses to common/courses.json. This test
    exists to catch a regression (the remaining gap changing
    unexpectedly), not to demand it be zero.
    """
    curr = load_curriculum(CURRICULUM_DIR, branch='eee')
    undefined = check_undefined_course_codes(curr)
    expected_keys = {'ECE F244', 'INSTR F243', 'ECE F434', 'ECE F242', 'INSTR F242'}
    assert set(undefined.keys()) == expected_keys


def test_eee_discipline_core_floor_passes():
    curr = load_curriculum(CURRICULUM_DIR, branch='eee')
    violations = check_category_floor(curr)
    assert 'Discipline Core' not in violations


def test_ece_has_no_cycles():
    curr = load_curriculum(CURRICULUM_DIR, branch='ece')
    assert check_cycles(curr) == []


def test_ece_category_floor_passes():
    curr = load_curriculum(CURRICULUM_DIR, branch='ece')
    violations = check_category_floor(curr)
    assert violations == {}, f'Unexpected category floor violations: {violations}'


def test_ece_known_undefined_references():
    """
    Documented, expected, intentional gap: ECE F344 and ECE F424 reference
    cross-department elective alternatives (EEE/INSTR variants of the same
    requirement). See VALIDATION_STATUS.md.
    """
    curr = load_curriculum(CURRICULUM_DIR, branch='ece')
    undefined = check_undefined_course_codes(curr)
    expected_keys = {'EEE F243', 'EEE F242', 'INSTR F242'}
    assert set(undefined.keys()) == expected_keys


def test_e_and_i_has_no_cycles():
    curr = load_curriculum(CURRICULUM_DIR, branch='e_and_i')
    assert check_cycles(curr) == []


def test_e_and_i_category_floor_passes():
    curr = load_curriculum(CURRICULUM_DIR, branch='e_and_i')
    violations = check_category_floor(curr)
    assert violations == {}, f'Unexpected category floor violations: {violations}'


def test_e_and_i_known_undefined_references():
    """
    Documented, expected, intentional gap: INSTR F424 references
    cross-department elective alternatives (EEE/ECE variants of the same
    requirement). See VALIDATION_STATUS.md.
    """
    curr = load_curriculum(CURRICULUM_DIR, branch='e_and_i')
    undefined = check_undefined_course_codes(curr)
    expected_keys = {'EEE F242', 'ECE F242'}
    assert set(undefined.keys()) == expected_keys


def test_minor_data_science_loads_and_passes():
    curr = load_curriculum(CURRICULUM_DIR, branch='cse', minor='data_science')
    assert check_category_floor(curr) == {}
    assert check_cycles(curr) == []
    assert check_undefined_course_codes(curr) == {}


def test_run_all_validations_returns_expected_shape():
    curr = load_curriculum(CURRICULUM_DIR, branch='cse')
    report = run_all_validations(curr)
    for key in ('branch', 'course_count', 'cycles', 'undefined_course_codes',
                'category_floor_violations', 'unreachable_courses'):
        assert key in report
    assert report['branch'] == 'cse'
    # 26 cse-specific courses + 6 common courses (CS F111, EEE F111, MATH F111/F112/F113/F213)
    assert report['course_count'] == 32


def test_common_courses_load_into_both_branches():
    """CS F111 and EEE F111 are common -- both should be visible when
    loading either branch, since loader.py merges common/ in first."""
    cse = load_curriculum(CURRICULUM_DIR, branch='cse')
    eee = load_curriculum(CURRICULUM_DIR, branch='eee')
    assert 'CS F111' in cse.courses
    assert 'EEE F111' in cse.courses  # common courses, visible in any branch
    assert 'CS F111' in eee.courses
    assert 'EEE F111' in eee.courses


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
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
