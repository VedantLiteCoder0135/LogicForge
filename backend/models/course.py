"""Static course and degree-requirement records.

Owned with Pair B. Both solvers read these fields; neither solver stores
its own copy of the curriculum.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Course:
    """One course after the curriculum JSON has been loaded."""

    code: str
    title: str | None
    credits: int
    term_parity: str | None
    category: str
    prerequisites_str: str | None
    parsed_prerequisites: dict | None


@dataclass(frozen=True)
class Requirement:
    """Credit floor for one requirement category."""

    category: str
    credit_minimum: int
    eligible_courses: tuple[str, ...] = ()
