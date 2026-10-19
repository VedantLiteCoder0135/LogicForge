"""
config/settings.py
Central configuration for GraphMind — curriculum, solver, benchmark,
and learned-heuristic parameters.
"""

from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Curriculum / Degree constants
# ---------------------------------------------------------------------------

PROGRAM_NAME = "BITS Hyderabad - CS/AI"

MAX_CREDITS_PER_TERM = 24
MIN_CREDITS_PER_TERM = 12
GRADUATION_HORIZON_TERMS = 8

ODD_TERMS = [1, 3, 5, 7]
EVEN_TERMS = [2, 4, 6, 8]

CATEGORY_MIN_CREDITS: dict[str, int] = {
    "core": 90,
    "elective_hdd": 12,
    "elective_ps": 20,
    "minor": 20,
}

KB_PATHS = {
    "courses": BASE_DIR / "data" / "curriculum" / "courses.json",
    "prerequisites": BASE_DIR / "data" / "curriculum" / "prereqs.json",
    "categories": BASE_DIR / "data" / "curriculum" / "categories.json",
}

# ---------------------------------------------------------------------------
# CSP Solver settings
# ---------------------------------------------------------------------------

@dataclass
class CSPConfig:
    variable_ordering: str = "mrv_degree"   # minimum remaining values + degree tiebreak
    value_ordering: str = "lcv"
    propagation: str = "ac3"                 # none | forward_checking | ac3
    max_backtracks: int = 100_000
    timeout_seconds: int = 60

# ---------------------------------------------------------------------------
# A* Planner settings
# ---------------------------------------------------------------------------

@dataclass
class AStarConfig:
    heuristic: str = "composite"            # credit_bound | critical_path | composite | learned
    bundle_breadth_limit: int = 10
    timeout_seconds: int = 60

# ---------------------------------------------------------------------------
# Infeasibility Analyzer settings
# ---------------------------------------------------------------------------

@dataclass
class InfeasibilityConfig:
    method: str = "deletion_based_mus"
    max_core_size: int = 15

# ---------------------------------------------------------------------------
# Learned Heuristic (Deep Learning component)
# ---------------------------------------------------------------------------

@dataclass
class LearnedHeuristicConfig:
    model_type: str = "mlp"                 # mlp | gbm
    features: list[str] = field(default_factory=lambda: [
        "outstanding_credits_per_category",
        "outstanding_course_count",
        "max_remaining_chain_depth",
        "parity_locked_course_count",
        "terms_remaining",
        "unsatisfied_disjunction_count",
    ])
    hidden_layers: list[int] = field(default_factory=lambda: [64, 32])
    learning_rate: float = 0.001
    epochs: int = 100
    batch_size: int = 32
    train_val_split: float = 0.8
    training_data_size: int = 5000
    checkpoint_path: Path = BASE_DIR / "models" / "checkpoints" / "heuristic_regressor.pt"

# ---------------------------------------------------------------------------
# Benchmark / Evaluation settings
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkConfig:
    num_synthetic_students: int = 200
    confidence_level: float = 0.95
    bootstrap_iterations: int = 10_000
    significance_test: str = "wilcoxon"
    random_seed: int = 42
    output_dir: Path = BASE_DIR / "results"

# ---------------------------------------------------------------------------
# Logging settings
# ---------------------------------------------------------------------------

@dataclass
class LoggingConfig:
    level: str = "INFO"
    log_dir: Path = BASE_DIR / "logs"
    log_solver_traces: bool = True
    log_search_stats: bool = True

# ---------------------------------------------------------------------------
# Single importable instance (so other modules do: from config.settings import CSP, ASTAR, ...)
# ---------------------------------------------------------------------------

CSP = CSPConfig()
ASTAR = AStarConfig()
INFEASIBILITY = InfeasibilityConfig()
LEARNED_HEURISTIC = LearnedHeuristicConfig()
BENCHMARK = BenchmarkConfig()
LOGGING = LoggingConfig()