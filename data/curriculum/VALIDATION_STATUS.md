# Curriculum Validation Status

All four engineering branches (cse, eee, ece, e_and_i) plus common and one real minor are now encoded with real, bulletin-sourced data and pass validation.

| Branch / Minor | Courses encoded | Validation suite run | Result |
|---|---|---|---|
| common | ✅ (6 courses: CS F111, EEE F111, MATH F111, MATH F112, MATH F113, MATH F213) | ✅ | Passed — 0 cycles, 0 unreachable |
| cse | ✅ (26 branch-specific + 6 common = 32 total) | ✅ | **Fully passed, zero gaps**: 0 cycles, 0 undefined references, 0 category-floor violations, 0 unreachable |
| eee | ✅ (14 Discipline Core + 11 Discipline Elective + 6 common = 31 total) | ✅ | **Passed**: 0 cycles, 0 category-floor violations, 0 unreachable. 5 documented, intentional cross-department references remain (ECE/INSTR course alternatives) |
| ece | ✅ (14 Discipline Core + 9 Discipline Elective + 6 common = 29 total) | ✅ | **Passed**: 0 cycles, 0 category-floor violations, 0 unreachable. 3 documented, intentional cross-department references (EEE F242/F243, INSTR F242) |
| e_and_i | ✅ (14 Discipline Core + 10 Discipline Elective + 6 common = 30 total) | ✅ | **Passed**: 0 cycles, 0 category-floor violations, 0 unreachable. 2 documented, intentional cross-department references (EEE F242, ECE F242) |
| minors/data_science | ✅ (18 courses: 5 Core + 13 Elective) | ✅ | **Passed**: 5 Core courses sum to exactly 15 units, matching the bulletin's stated minimum exactly |

Full verbatim run output for every branch/minor is in `VALIDATION_RUN_LOG.md`.

## Cross-department references, by branch (intentional, not gaps)

Every branch has a handful of prerequisite references to a *different* branch's equivalent course (e.g. `EEE F313` → `EEE F244 OR ECE F244`, meaning either department's version of the same course satisfies the requirement). These are real alternatives stated in the source data, not typos — adding the referenced branch's FULL curriculum just to resolve one leaf reference isn't necessary, since `backend/logic/prerequisite_checker.py`'s `evaluate()` only needs the referenced CODE to exist somewhere in the loaded curriculum's course set to resolve the OR correctly; it doesn't need that other branch's own prerequisites to be known. `tests/test_data_validation.py` asserts each branch's exact set of these references so a future change is caught, not silently drifted.

## Not yet done

- No minor other than Data Science is encoded.
- `ece`/`e_and_i` haven't been individually cross-checked against the TTD-authoritative table the way `cse`'s scope was (see `SCOPE_DECISION.md`).
- Each branch's elective pool is a real, usable subset, not the bulletin's complete list — see `SCOPE_DECISION.md` for what expanding it further would involve.

## Data provenance

All four branches' Discipline Core data was verified the same way: pull the real semester-wise degree plan from `DETAILS_OF_PROGRAMMES.pdf`, sum the encoded courses' credits, and confirm the sum matches the bulletin's own stated total exactly (not approximately) — 48/48 for all four branches. Discipline Electives were sourced from each branch's own "DISCIPLINE ELECTIVE COURSES" listing in the bulletin's course-catalog section. Prerequisites for all courses came from the KB built and cross-verified in `PairA_original_README.md` (which included a 100%-match check against the actual TTD-authoritative prerequisite export for the original `cse` scope).
