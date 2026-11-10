"""GraphMind — CSP Solver Package (Pair B)

Provides the constraint satisfaction problem formulation and solver for curriculum planning.
"""

from .model import Constraint, NOT_TAKEN, Problem, build_problem
from .solver import PlacementTrace, Result, SolverConfig, solve

__all__ = [
    "Problem",
    "build_problem",
    "Constraint",
    "NOT_TAKEN",
    "SolverConfig",
    "Result",
    "PlacementTrace",
    "solve",
]
