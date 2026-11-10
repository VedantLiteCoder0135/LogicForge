# Pair A: Curriculum Knowledge Base & Requirement Resolver

**Authors:** Krishna Gupta, Pratham Singla

## 1. What we built

Pair A owns the layer between raw curriculum data and the planning model both solvers consume: a curriculum knowledge base, a propositional-formula entailment evaluator for prerequisites, a forward-chaining closure engine, and the validation suite that checks the curriculum data is internally consistent before anything is planned against it.

Concretely:
- `backend/logic/prerequisite_parser.py` — parses a prerequisite formula string (e.g. `"CS F211 AND (MATH F211 OR MATH F213)"`) into a propositional-logic tree of AND/OR/leaf nodes. A leaf can be a strict prerequisite (`PRE`, must be completed in an earlier term) or a co-requisite (`CO`, satisfiable in the same term — marked with a `:CO` suffix, e.g. `"BIO F341:CO"`).
- `backend/logic/prerequisite_checker.py` — entailment: given a formula and a student's completed/concurrent-course sets, decides eligibility and produces a human-readable explanation when a course isn't eligible yet.
- `backend/logic/forward_chaining.py` — the course-unlock cascade (repeatedly applies the entailment rule until a full pass unlocks nothing new) and category credit accumulation.
- `backend/data/loader.py` — merges `common/` + one branch's + (optionally) one minor's course and requirement data into a single `Curriculum` object.
- `backend/data/validator.py` — four checks: prerequisite-graph cycles, undefined course-code references, category credit-floor violations, and structural unreachability.
- `data/curriculum/` — the actual curriculum data: `common/` (university-wide first-year courses), `branches/cse/` and `branches/eee/` (fully verified), `branches/ece/` and `branches/e_and_i/` (empty stubs, see §4), and `minors/data_science/` (a real minor, see §3).

## 2. Methodology: how the curriculum data was verified

We did not trust a single source. The curriculum data went through four independent sources, each one tightening correctness:

1. **`prereqs.json`**, a community-maintained export (via the `handoutsforyou`/h4u.app project) of BITS's TTD-published prerequisite sheet — 735 courses, used as the initial parse target.
2. **Two editions of the official BITS Academic Bulletin** (`DETAILS_OF_PROGRAMMES.pdf`, `Bulletin-2024-25-Details_of_Programmes.pdf`), giving the real semester-wise degree plan with exact credits. Verification check: the CSE branch's 14 Discipline Core courses summed to **exactly 48 units**, matching the bulletin's own stated total — not merely plausible, an exact match. The EEE branch's 14 Discipline Core courses hit the same exact match.
3. **The full 951-page bulletin** with per-course descriptions (`Academic-Bulletin-2025-26.pdf`), used to confirm — not guess — that several courses genuinely have no prerequisite, closing what would otherwise look like missing data.
4. **The actual TTD-authoritative prerequisite export** (`Pre-requisite_November_2025.pdf`), with explicit `PREREQ1 AND/OR PREREQ2...` columns, unambiguous by construction. Cross-checking every CSE-scope course against this table found **100% agreement** with what we'd already parsed from source 1 — the strongest validation result in the project, since it's confirmation against the actual primary source rather than internal self-consistency.

## 3. The real Minor in Data Science

An earlier benchmark used a made-up minor. We replaced it with **BITS's actual "Minor in Data Science"** (`DETAILS_OF_PROGRAMMES.pdf`), which states a 5-course/15-unit minimum. The 5 Core courses we encoded (`BITS F464`, `CS F320`, `MATH F432`, `BITS F453`, `BITS F454`) sum to exactly 15 credits, matching the bulletin's stated minimum exactly — the same verification standard used for branch Discipline Core. An elective pool of 13 additional real courses is also encoded (`data/curriculum/minors/data_science/`).

## 4. Scope: all four engineering branches

We initially scoped the curriculum data to CSE and EEE only, per the proposal's own stated design principle (§3: *"a correct, validated knowledge base for one program supports stronger results than a shallow encoding of several"*) — building out a branch shallowly isn't worth the risk of the solvers producing confidently-wrong plans for it. We then extended the same verification bar to ECE and E&I rather than leaving them as placeholders: each branch's Discipline Core credit total was independently computed and checked against the bulletin's own stated figure, and all four matched exactly (48/48 units for CSE, EEE, ECE, and E&I alike). Full reasoning and what's still not done in `data/curriculum/SCOPE_DECISION.md`.

## 5. Validation results

All four validator checks were run against every branch and recorded verbatim in `data/curriculum/VALIDATION_RUN_LOG.md`. Summary:

| Branch/Minor | Discipline Core | Result |
|---|---|---|
| cse | 14 courses, 48/48 units (exact) | PASS, zero gaps |
| eee | 14 courses, 48/48 units (exact) | PASS, 5 documented intentional cross-department references |
| ece | 14 courses, 48/48 units (exact) | PASS, 3 documented intentional cross-department references |
| e_and_i | 14 courses, 48/48 units (exact) | PASS, 2 documented intentional cross-department references |
| cse + Minor in Data Science | — | PASS, zero gaps |

24 unit tests across `tests/test_prerequisites.py` and `tests/test_data_validation.py` all pass, exercising the parser, entailment checker, and all four validator checks against this real data for every branch and the minor.

## 6. Known limitations, stated plainly

- Each branch has a small number of undefined cross-department references (eee: 5, ece: 3, e_and_i: 2) — these are deliberate, documented alternatives (e.g. a course's real prerequisite is "department X's version OR department Y's version OR department Z's version," and only one branch's leaf resolves within that branch's own loaded curriculum). This does not break entailment, since `evaluate()` only needs the matching leaf code to exist in the loaded set to satisfy an OR — it is a genuine, not a hidden, gap, asserted explicitly by tests.
- `kb_courses.json` (a 759-course, all-department prerequisite reference file built early in this work) deliberately has no credits/categories/term-parity — it was never meant to, since that data doesn't exist in its source (the TTD prerequisite export). It is kept as a reference artifact (`data/curriculum/_raw_kb/`) for future expansion (e.g. deeper elective pools), but is **not** read by the runtime; see `_raw_kb/NOTE.md`.
- The bulletin's EEE Discipline Core has one slot that's either `MATH F212` (3 credits) or `ME F344` (2 credits) — we encoded only the `MATH F212` variant; the alternative isn't yet modeled.
- `ece`/`e_and_i`'s data hasn't been individually cross-checked against the TTD-authoritative prerequisite export the way `cse`'s original 27-course scope was (that cross-check found 100% agreement) — it comes from the same already-verified KB, but that specific double-check wasn't repeated for these two branches.
- No branch's elective pool is exhaustive — each has a real, usable, verified subset of the bulletin's full elective listing, not the complete list.
