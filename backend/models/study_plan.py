"""A semester-by-semester plan. Both solvers produce this shape."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .planning_problem import NOT_TAKEN


@dataclass
class StudyPlan:
    """Assignment of outstanding courses to terms.

    ``assignment`` maps a course code to a semester integer or ``NOT_TAKEN``.
    ``terms_used`` is the number of terms after ``current_semester`` through
    the last scheduled course. An empty plan of already-satisfied requirements
    has ``terms_used == 0``.
    """

    assignment: dict[str, Any]
    terms_used: int
    trace: list[Any] = field(default_factory=list)

    def courses_by_term(self) -> dict[int, list[str]]:
        grouped: dict[int, list[str]] = {}
        for code, semester in self.assignment.items():
            if semester == NOT_TAKEN or not isinstance(semester, int):
                continue
            grouped.setdefault(semester, []).append(code)
        for codes in grouped.values():
            codes.sort()
        return dict(sorted(grouped.items()))

    def untaken(self) -> list[str]:
        return sorted(
            code for code, semester in self.assignment.items() if semester == NOT_TAKEN
        )
