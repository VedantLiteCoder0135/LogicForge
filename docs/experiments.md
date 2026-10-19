# Experiments (E1–E5)

These five experiments are defined in the submitted proposal (`docs/proposal.pdf`, §3) and this document should stay aligned with it — if an experiment's scope changes here, the proposal and this doc should not disagree about what's being measured.

| ID | Experiment | Independent variable | Measures | Owner |
|---|---|---|---|---|
| E1 | Solver comparison | CSP backtracking vs. A* | Plan validity rate, optimality gap, wall-clock time, nodes expanded/backtracks | Pair C |
| E2 | Propagation ablation | plain backtracking → +forward checking → +AC‑3 → +MRV/LCV | Backtrack count, runtime | Pair B |
| E3 | Heuristic ablation | credit bound / critical path / composite / learned heuristic | Nodes expanded, optimality gap | Pair C |
| E4 | Grounding comparison (correctness) | solver output vs. independent verifier | Plan validity rate, constraint violations found | Pair D |
| E5 | End-user evaluation | 6–10 volunteer students, own transcripts | Plan correctness, usefulness rating | Pair D |

## E1 — Solver comparison

Runs the CSP solver and A* planner on the **same** instances (same `PlanningProblem` object — see `docs/architecture.md` §3) and compares:
- **Validity**: does the returned plan pass the independent verifier?
- **Optimality gap**: for small instances where exhaustive search is tractable, how far is the returned plan from optimal?
- **Time / nodes expanded**: wall-clock and search-effort comparison.

Implemented in `experiments/` (script TBD, owned by Pair C — not yet encoded as of this writing). Paired comparisons on identical instances use the Wilcoxon signed-rank test, per the proposal, since node-count distributions are expected to be skewed.

## E2 — Propagation ablation

Implemented in `experiments/csp_ablation.py` (Pair B). Runs the CSP solver in four configurations — plain backtracking, +forward checking, +AC‑3, +MRV/LCV ordering — on the same instance set, and reports backtrack count and runtime per configuration. This measures the actual contribution of each propagation/ordering technique, not just whether the solver eventually succeeds.

## E3 — Heuristic ablation

Implemented in `experiments/heuristic_comparison.py` (Pair C). Runs A* with each of: the credit bound alone, the critical-path bound alone, their pointwise maximum (composite), and the learned heuristic. Reports nodes expanded and optimality gap per heuristic. This is where the "does the learned heuristic actually outperform the hand-crafted one" question (flagged as a real risk in the proposal, not an assumed win) gets answered with evidence.

## E4 — Grounding comparison (correctness)

Every plan produced by either solver is re-validated by `backend/verification/plan_checker.py` (Pair D), which checks each prerequisite, requirement, credit, and semester constraint independently of the solver that produced the plan. E4 reports the plan validity rate and any constraint violations the verifier catches — this is the system's defense against "the CSP solver and A* both agree, so it must be right," since both could share an undetected bug in a part of the model they both rely on.

## E5 — End-user evaluation

6–10 volunteer students (team members and classmates, per the proposal — no third-party academic records are collected or stored) run their **own** transcripts through GraphMind and report on plan correctness and usefulness. This is the Application track's realistic-user requirement (course guidelines, Appendix A). Results and any consent/data-handling notes live under `experiments/results/`.

## Benchmark set

All experiments that need many instances (primarily E1–E3) draw from a shared benchmark of **~200 synthetic student states**, stratified by difficulty — credit-budget slack, prerequisite chain depth, minor vs. no minor — per the proposal. Results are reported as means with 95% bootstrap confidence intervals.

## Status

None of E1–E5 have produced results yet as of this document's writing — this file defines what each experiment measures and how, not that it has run. Update the relevant section with a link to its script and its first results once that experiment is actually implemented and run (see the Component Status table in the root `README.md`).
