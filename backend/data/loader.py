"""
GraphMind — backend/data/loader.py (Pair A)

Loads data/curriculum/{common, branches/<branch>, minors/<minor>}
courses.json + requirements.json into Curriculum/Course objects.

NOTE ON backend/models/: docs/architecture.md §3 says Course and
Curriculum are owned jointly by Pair B and Pair C under backend/models/,
since both solvers read them. Those classes may still be in flux while
this loader is being written, so the minimal Course/Curriculum classes
below exist only to make backend/logic/ runnable and testable right now
-- they implement exactly the interface forward_chaining.py and
prerequisite_checker.py need (.code, .credits, .category,
.parsed_prerequisites, .courses dict). WHEN backend/models/course.py and
curriculum.py land, replace these two classes' internals with imports
from there rather than keeping two competing definitions -- the rest of
this file (the actual loading logic) does not need to change.
"""

import json
import os

from ..logic.prerequisite_parser import parse_prerequisites


class Course:
    def __init__(self, code, title, credits, term_parity, category, prerequisites_str):
        self.code = code
        self.title = title
        self.credits = credits
        self.term_parity = term_parity
        self.category = category
        self.prerequisites_str = prerequisites_str
        self.parsed_prerequisites = parse_prerequisites(prerequisites_str)

    def __repr__(self):
        return f'Course({self.code!r})'


class Requirement:
    def __init__(self, category, credit_minimum, eligible_courses):
        self.category = category
        self.credit_minimum = credit_minimum
        self.eligible_courses = eligible_courses


class Curriculum:
    def __init__(self, branch_name, courses: dict, requirements: dict):
        self.branch_name = branch_name
        self.courses = courses          # code -> Course
        self.requirements = requirements  # category -> Requirement

    def known_codes(self):
        return set(self.courses.keys())


def _load_courses_file(path):
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        raw = json.load(f)
    return {
        entry['code']: Course(
            code=entry['code'],
            title=entry.get('title'),
            credits=entry.get('credits'),
            term_parity=entry.get('term_parity', 'both'),
            category=entry.get('category'),
            prerequisites_str=entry.get('prerequisites'),
        )
        for entry in raw
    }


def _load_requirements_file(path):
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        raw = json.load(f)
    return {
        entry['category']: Requirement(
            category=entry['category'],
            credit_minimum=entry['credit_minimum'],
            eligible_courses=entry.get('eligible_courses', []),
        )
        for entry in raw
    }


def load_curriculum(curriculum_dir, branch=None, minor=None):
    """
    Load common/ plus one branch/ (and optionally one minor/) into a
    single merged Curriculum. `curriculum_dir` is the path to
    data/curriculum/. Does NOT assume every branch directory is complete
    -- only loads what's asked for, per data_schema.md §1.
    """
    courses = {}
    requirements = {}

    common_path = os.path.join(curriculum_dir, 'common', 'courses.json')
    courses.update(_load_courses_file(common_path))

    if branch:
        branch_dir = os.path.join(curriculum_dir, 'branches', branch)
        courses.update(_load_courses_file(os.path.join(branch_dir, 'courses.json')))
        requirements.update(_load_requirements_file(os.path.join(branch_dir, 'requirements.json')))

    if minor:
        minor_dir = os.path.join(curriculum_dir, 'minors', minor)
        courses.update(_load_courses_file(os.path.join(minor_dir, 'courses.json')))
        requirements.update(_load_requirements_file(os.path.join(minor_dir, 'requirements.json')))

    branch_label = branch or 'common-only'
    return Curriculum(branch_label, courses, requirements)


if __name__ == '__main__':
    import sys
    curriculum_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'curriculum')
    curr = load_curriculum(curriculum_dir, branch='cse')
    print(f'Loaded curriculum for branch={curr.branch_name!r}')
    print(f'  {len(curr.courses)} courses, {len(curr.requirements)} requirement categories')
    for code, course in list(curr.courses.items())[:5]:
        print(f'  {code}: credits={course.credits}, category={course.category}, '
              f'prereq_tree={course.parsed_prerequisites}')
