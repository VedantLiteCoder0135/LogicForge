# Migration notes — Pair A's old deliverable → the new repo layout

This restructures Pair A's original flat deliverable (a single `kb_courses.json` of 759 courses from all BITS departments, plus `build_kb.py`/`entailment.py`/`fixpoint.py`/`requirement_resolver.py`) into the layout `docs/data_schema.md` and `docs/architecture.md` specify. **Nothing about the underlying logic changed** — same entailment semantics, same fixpoint algorithm, same prerequisite relationships (still the ones cross-verified against the authoritative TTD table). What changed is where it lives and how it's represented on disk.

## What moved where

| Old | New | Notes |
| --- | --- | --- |
| `kb_courses.json` (759 courses, all departments, JSON-tree formulas) | `data/curriculum/common/courses.json` + `data/curriculum/branches/cse/courses.json` | Only the 27 courses in the original `curriculum_scope.json` were migrated — the declared CS-major scope. The other ~730 courses from other departments were **not** carried over; they were never part of the validated scope to begin with. If another branch needs them later, `migrate_to_new_layout.py` shows the conversion pattern to reuse. |
| JSON-tree prerequisite formulas (`{"kind": "and", "items": [...]}`) | String formulas (`"CS F241 AND CS F215"`) | Converted by `migrate_to_new_layout.py`'s `formula_to_string()`. Parsed back into the same tree shape by the new `backend/logic/prerequisite_parser.py` — the entailment/fixpoint logic itself is byte-for-byte the same algorithm as before, just fed a parsed string instead of reading the tree directly from JSON. |
| `entailment.py` | `backend/logic/prerequisite_checker.py` | Same code, same 6 tests (ported to `tests/test_prerequisites.py`), new location. |
| `fixpoint.py` | `backend/logic/forward_chaining.py` | Same two rules (course-unlock cascade, category credit accumulation), now duck-typed against whatever `Curriculum`/`Course` objects `backend/data/loader.py` (or eventually `backend/models/`) provides, instead of raw dicts. |
| `requirement_resolver.py`'s validation methods | `backend/data/validator.py` | The four checks, now operating on a loaded `Curriculum` rather than a flat KB dict. |
| (new) | `backend/data/loader.py` | Did not exist before — reads `common/` + one `branches/<name>/` (+ optional `minors/<name>/`) into a merged `Curriculum`, per `data_schema.md` §1's design: one branch's data problems never block another branch. |
| `credits_categories.json`, `curriculum_scope.json` | `data/curriculum/branches/cse/requirements.json`, split courses.json files | The real, bulletin-verified credit/category data — nothing here was re-guessed, only reshaped. |

## Design decisions made during this migration

1. **The `:CO` suffix convention for co-requisites in the formula string** (e.g. `"BIO F341:CO"`). `data_schema.md`'s own example string only shows PRE-style formulas and doesn't specify how to mark a co-requisite. **Decided and finalized**: this convention is used consistently throughout `cse` and `eee`'s data and is documented in `backend/logic/prerequisite_parser.py`'s docstring. If whoever owns `backend/models/course.py` (Pair B/C) has a conflicting convention already in use elsewhere, this needs to be reconciled before merging — flag it explicitly rather than silently diverging.
2. **Unparenthesized mixed AND/OR is now a hard parse error**, not a heuristic guess. The original `build_kb.py` needed the trailing-connective heuristic because the *raw TTD export* was genuinely ambiguous. This new string format is something *we* write, so there's no excuse for that ambiguity here — `prerequisite_parser.py` refuses and asks for explicit parentheses instead of guessing.
3. **CS F111 was moved to `common/`**, not `branches/cse/`, since it's a university-wide first-year course, not CSE-specific. If that's wrong for how the team wants branches modeled, it's a one-line move in `migrate_to_new_layout.py` and a rerun.
4. **`ece/` and `e_and_i/` are empty stubs**, not fabricated data. See `VALIDATION_STATUS.md` — do not claim they're supported.
5. **Resolved**: the `CS F211`→`MATH F213` and `CS F320`→`MATH F113` cross-branch references, plus `eee`'s `MATH F212`→`MATH F111`/`MATH F112`, are closed — all four Math courses (real credits and titles from the bulletin, confirmed prerequisite-free) were added to `common/courses.json`. `cse` now has zero undefined references. `eee`'s remaining 5 undefined references (ECE/INSTR cross-department elective alternatives) are a deliberate, documented scope boundary, not an oversight — see `VALIDATION_STATUS.md`.

6. **`eee`'s Discipline Elective gap is closed**: 11 real elective courses (35 credits available against the 12-unit minimum) were added from the bulletin's EEE elective listing, with prerequisites from the same cross-verified KB. `check_category_floor()` now passes for both categories in both branches.

7. **`tests/test_data_validation.py` added** (was missing, listed in `architecture.md` as a required Pair A test file) — 10 tests directly exercising `backend/data/validator.py`'s four checks against real `cse` and `eee` data.

## Addendum: `eee` branch added

Not in `docs/architecture.md`'s original repo layout (which only listed `cse`, `ece`, `e_and_i`), added on request. Sourced the same way as `cse`: Discipline Core courses, credits, and term placement from `DETAILS_OF_PROGRAMMES.pdf`'s EEE semester-wise grid, prerequisites from the already-verified KB. 14 courses, exactly 48 units, matching the bulletin's own stated total.

**This branch is not yet fully supported** — see `VALIDATION_STATUS.md` for the specifics, but briefly: no Discipline Elective courses have been added yet (the validator correctly fails the category-floor check for that category, 0 of 12 units available), and unlike `cse`, `eee`'s prerequisites have not been individually cross-checked against the TTD-authoritative table. Also update `docs/architecture.md`'s repo-layout diagram and any README feature list to mention `eee`, since it currently only names `cse`/`ece`/`e_and_i`.

## Running it

```
python3 -m backend.data.validator      # full validation report for the cse branch
python3 tests/test_prerequisites.py    # 6 tests, no pytest required
python3 -m backend.data.loader         # quick load + print sanity check
```

## Addendum: ECE and E&I added, scope expanded from CSE+EEE to all four branches

Both branches built to the same standard as `cse`/`eee`: 14 Discipline Core courses each, independently verified to sum to exactly 48 units matching the bulletin's own stated total (ECE: `DETAILS_OF_PROGRAMMES.pdf`'s "B.E. Electronics & Communication" grid; E&I: the "B.E. Electronics and Instrumentation" grid), plus real Discipline Elective pools (ECE: 9 courses/28 credits; E&I: 10 courses/32 credits) sourced from each branch's own course-catalog elective listing. See `data/curriculum/SCOPE_DECISION.md` for the updated scope statement and what's still not done (TTD-authoritative cross-check not repeated for these two branches; elective pools are real but partial).

Also added: `requirement_resolver.py` restored at repo root as a compatibility shim (fixes a `tests/conftest.py` import crash — verify against the actual import path used there), a real `Minor in Data Science` (`data/curriculum/minors/data_science/`, 5 Core courses summing to exactly 15 units matching the bulletin), `data/curriculum/VALIDATION_RUN_LOG.md` (verbatim validator output for every branch/minor), `data/curriculum/_raw_kb/` (kb_courses.json moved here with a note clarifying it's a reference artifact, not consumed by the runtime), and `docs/report/pair_a.md`.
