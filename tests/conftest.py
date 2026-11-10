"""GraphMind — Pytest Fixtures and Path Setup

Configures sys.path and provides reusable fixtures.
"""

import os
import sys
import pytest

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

# If PairA_CurriculumKB directory exists as a subfolder, add it too
_pair_a_dir = os.path.join(_repo_root, "PairA_CurriculumKB")
if os.path.exists(_pair_a_dir) and _pair_a_dir not in sys.path:
    sys.path.insert(0, _pair_a_dir)

from requirement_resolver import RequirementResolver


@pytest.fixture(scope="session")
def kb_path() -> str:
    candidates = [
        os.path.join(_repo_root, "kb_courses.json"),
        os.path.join(_repo_root, "PairA_CurriculumKB", "kb_courses.json"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "kb_courses.json"


@pytest.fixture(scope="session")
def scope_path() -> str:
    candidates = [
        os.path.join(_repo_root, "curriculum_scope.json"),
        os.path.join(_repo_root, "PairA_CurriculumKB", "curriculum_scope.json"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "curriculum_scope.json"


@pytest.fixture(scope="session")
def resolver(kb_path: str, scope_path: str) -> RequirementResolver:
    """Session-scoped RequirementResolver instance."""
    return RequirementResolver.load(kb_path=kb_path, scope_path=scope_path)
