"""Load ``data/curriculum`` into ``Course`` / ``Curriculum`` objects.

The directory layout is the one Pair A writes and ``docs/data_schema.md``
describes: ``common/courses.json`` plus ``branches/<branch>/courses.json``
and ``requirements.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

from .course import Course, Requirement
from .formula import parse_prerequisites


class Curriculum:
    """Merged common + one branch (+ optional minor) course catalogue."""

    def __init__(
        self,
        branch_name: str,
        courses: dict[str, Course],
        requirements: dict[str, Requirement],
    ) -> None:
        self.branch_name = branch_name
        self.courses = courses
        self.requirements = requirements

    def known_codes(self) -> set[str]:
        return set(self.courses)


def _load_courses(path: Path) -> dict[str, Course]:
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    courses: dict[str, Course] = {}
    for entry in raw:
        code = entry["code"]
        prereq = entry.get("prerequisites")
        courses[code] = Course(
            code=code,
            title=entry.get("title"),
            credits=int(entry.get("credits") or 0),
            term_parity=entry.get("term_parity") or "both",
            category=entry.get("category") or "",
            prerequisites_str=prereq,
            parsed_prerequisites=parse_prerequisites(prereq),
        )
    return courses


def _load_requirements(path: Path) -> dict[str, Requirement]:
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    requirements: dict[str, Requirement] = {}
    for entry in raw:
        category = entry["category"]
        requirements[category] = Requirement(
            category=category,
            credit_minimum=int(entry.get("credit_minimum") or 0),
            eligible_courses=tuple(entry.get("eligible_courses") or ()),
        )
    return requirements


def load_curriculum(
    curriculum_dir: str | Path,
    branch: str | None = None,
    minor: str | None = None,
) -> Curriculum:
    """Merge common courses with one branch and an optional minor."""
    root = Path(curriculum_dir)
    courses = _load_courses(root / "common" / "courses.json")
    requirements: dict[str, Requirement] = {}
    if branch:
        branch_dir = root / "branches" / branch
        courses.update(_load_courses(branch_dir / "courses.json"))
        requirements.update(_load_requirements(branch_dir / "requirements.json"))
    if minor:
        minor_dir = root / "minors" / minor
        courses.update(_load_courses(minor_dir / "courses.json"))
        requirements.update(_load_requirements(minor_dir / "requirements.json"))
    return Curriculum(branch or "common-only", courses, requirements)
