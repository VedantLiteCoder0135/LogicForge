# Pair A — Curriculum KB & Requirement Resolver
**Owners:** Krishna Gupta, Pratham Singla
**Maps to proposal milestones:** Week 1 (KB schema, loader, validation suite, toy curriculum) and Week 2 (prerequisite formulas, entailment evaluator, fixpoint closure)

## What this is

The "Requirement Resolver" box in the architecture diagram. Everything here
is pure and read-only once loaded, so Pairs B/C (CSP solver, A* planner) can
call it repeatedly inside search without shared-state bugs.

## File manifest, in build order

1. **`build_kb.py`** — parses the raw `prereqs.json` (735 real BITS courses,
   sourced via h4u.app / the `handoutsforyou` repo, which itself re-exports
   TTD's CMS prerequisites sheet) into a clean KB: course code split from
   title, prerequisites converted from a flat ambiguous list into a proper
   AND/OR propositional formula tree.
   - **The trailing-connective heuristic** (documented in the file's
     docstring) is the one genuinely non-obvious design decision here: the
     source data's flat list encodes each item's connective to the *next*
     item, not itself, so an OR-run must be detected and closed before an
     AND. This is the thing to be able to explain unprompted in viva.
   - Also expands cross-listed course codes (e.g. `"EEE/ECE F244"` →
     an OR of `EEE F214` / `ECE F214` / ...) and fixes a couple of
     stray-whitespace typos found in the raw data (e.g. `"G62 1"` → `"G621"`).
   - **Found and worth citing:** `h4u`'s own `scripts/prereqs.py` mislabels
     `completion_requirement` as `"One"` for any list containing an OR, even
     when the list is a genuine AND/OR mix, and only builds a real nested
     tree for 4 hardcoded course codes. Our heuristic is a more faithful
     reconstruction for the other 43 mixed-connective courses in the data.
   - Outputs `kb_courses.json` (the clean KB) and `validation_report.json`
     (duplicates, unresolved references, self-references, prerequisite
     cycles, and the list of mixed-connective courses flagged for manual
     review).

2. **`entailment.py`** — evaluates a formula tree against a student's
   completed/concurrent-course sets. Distinguishes `PRE` (must be finished
   in an earlier term) from `CO` (co-requisite, satisfiable same-term).
   Raises `UnresolvedReferenceError` on a dangling reference rather than
   silently mis-evaluating. `missing_requirements()` produces the
   human-readable derivation trace GraphMind promises for every plan
   decision. 14 tests, all passing, run against real courses (`BIO F312`
   for a plain AND chain, `EEE F437` for the OR-of-cross-listed-equivalents
   case, `BIO G515` for a co-requisite).

3. **`fixpoint.py`** — forward-chaining closure. Repeatedly scans for newly
   eligible courses until a full pass unlocks nothing new (the fixpoint).
   On the real 735-course KB, starting from two first-year courses, the
   entire KB becomes reachable in **5 passes** — a concrete number worth
   citing for the "unlocking cascades" claim in the proposal. Also computes
   category credit accumulation, and implements two validation checks that
   depend on the closure: structural unreachability (0 found, confirming
   the graph has no dead ends beyond already-flagged unresolved refs) and
   category credit-floor violations (a KB well-formedness check: can the
   curriculum, as encoded, even satisfy its own stated minimums?).

4. **`requirement_resolver.py`** — the integration layer. Wraps the above
   three into one class (`RequirementResolver`) with the API Pairs B/C
   actually call: `is_eligible`, `why_not_eligible`, `reachable_from`,
   `category_totals`, `run_all_validations`.

5. **`curriculum_scope.json`** — the declared "focused curriculum scope"
   (proposal, Sec. 3): 25 real CS-major courses (codes and titles pulled
   directly from the KB) with credits/category/term-parity fields.

## ✅ `curriculum_scope.json` is now REAL, verified data

Replaced after the user supplied the official BITS Pilani Hyderabad "Details
of Programmes" bulletins (two editions, cross-checked and identical for the
CS programme). Every `credits` and `category` value is read directly off
the bulletin's "Semester-wise Pattern for Students Admitted to B.E. Computer
Science Programme" grid and its course-list L-P-U table, not reconstructed
or guessed. **Sanity check that confirms correct transcription: the 14
Discipline Core courses sum to exactly 48 units, matching the bulletin's own
stated "Discipline Core — 48 Units (14 Courses)" — an exact match, not just
plausible.** `term_parity` for core courses is read off the Year/Semester
column (odd overall semester number → `"odd"`, even → `"even"`); Discipline
Elective courses have no fixed slot in the grid, so their `term_parity`
correctly stays `null` — genuinely unspecified, not an oversight.

A new validation check (`scope_courses_missing_from_kb_entirely` in
`requirement_resolver.py`) caught something real while rebuilding this:
**`CS F315` and `CS F317` are in the official bulletin's elective pool but
are entirely absent from `prereqs.json`** (not merely unresolved — the
source export never had a row for them at all, presumably because they're
newer electives TTD hadn't yet added when h4u last scraped CMS). This is a
genuine KB-coverage gap, not a parsing bug, and needs the actual prereqs for
these two pulled from CMS directly before they can be used in planning.

## ✅ Cross-verified against the authoritative TTD prerequisite table

The user supplied a fourth source: `Pre-requisite_November_2025.pdf`, the
actual TTD-published prerequisite export with explicit `PREREQ1 AND/OR
PREREQ2 AND/OR PREREQ3 AND/OR PREREQ4` columns and a `PRE`/`CO` flag per
slot — unambiguous by construction, unlike `prereqs.json`'s flat list that
needed the trailing-connective heuristic. This is strictly better ground
truth than anything used so far.

**Result: every one of the 27 declared-scope courses, and every course they
reference (`CS F222`, `CS F215`, `MATH F213`, `MATH F113`, `CS F429`,
`BITS F464`, etc.), matches this authoritative source exactly** — including
the newer additions (`CS F316`, `CS F430`, `CS F431`, `CS G518`, `CS F426`,
`CS F427`). This is a genuine, citable validation result: the automatically
parsed KB (`build_kb.py`, built from the h4u-sourced `prereqs.json`) is
confirmed accurate against the primary TTD table itself for the entire
declared scope, not merely plausible. The only gap found was `CS F429`'s
title, which was unknown before (we'd only inferred it has no prerequisite)
— this document reveals it as "Natural Language Processing," now patched in.

This also resolves the lingering caveat about the 43
`mixed_connectives_in_flat_list`-flagged courses and the trailing-connective
heuristic: for every CS-scope course that happened to fall in that flagged
set (none did, as it turns out — all scope courses' flat lists were single-
connective), there's now a path to fully authoritative verification using
this document, by locating that course's row and reading its explicit
`PREREQ`/`AND`/`OR` columns directly rather than inferring from the flat
list's trailing-connective pattern. Doing this for the remaining ~750
non-scope courses in the full KB (beyond the 27 already checked) would
retire the heuristic entirely, but is a larger undertaking than this
project's declared scope requires.

## ✅ Unresolved references and the CS F315/F317 gap — now resolved

The user supplied a third source: `Academic-Bulletin-2025-26.pdf` (951
pages), which contains the official per-course descriptions, including an
explicit `"Pre-requisite: ..."` line wherever a course actually has one.
Reading several of the ~21 previously-unresolved codes' own entries in this
document (`CE F231`, `MBA G518`, `BITS F103`) and both of the KB-absent
electives (`CS F315`, `CS F317`) confirmed a consistent pattern: **every one
of them genuinely has no prerequisite** — they're absent from the h4u/TTD
`prereqs.json` export because that export doesn't always have a row for
every zero-prerequisite course, not because the course doesn't exist.

`patch_missing_courses.py` applies this, transparently:
- `CS F315` and `CS F317` are added with `"verified_source": "bulletin"` —
  their exact bulletin text was read and confirmed prerequisite-free.
- The other 21 previously-unresolved codes are added with
  `"verified_source": "inferred_from_pattern"` — treated as open based on
  the consistent sample, but **not individually bulletin-confirmed**. This
  distinction is preserved in the data itself (each course record carries
  its own `verified_source` and `note`), not just asserted here.

After the patch: **0 unresolved references, 0 structurally unreachable
courses, all 27 scoped courses reachable.** Confirmed by rerunning
`requirement_resolver.py`.

**Still genuinely remaining** — concretely, before Week 3's "real curriculum
encoded and cross-checked" milestone:

- [ ] If a grade-critical plan ever depends on one of the 21
      `pattern_inferred` courses in `patch_report.json`, confirm it
      individually against the bulletin or CMS rather than trusting the
      inference — the sample was consistent but small (5 of 21)
- [ ] Add the BITS F3xx/F4xx cross-listed discipline electives (Image
      Processing, Neural Networks and Fuzzy Logic, Machine Learning, etc. —
      listed in the bulletin's elective pool) to `curriculum_scope.json` if
      your declared scope needs them
- [ ] Add credits for Humanities/Open Electives and the first-year common
      pool (MATH/PHY/CHEM/BIO Fxxx, BITS F110-112/221/225) if extending
      scope beyond the CS-major core
- [ ] Spot-check a sample of the 43
      `flat_lists_with_mixed_AND_OR_needing_manual_review` entries against
      the bulletin or CMS, since the trailing-connective heuristic is a
      judgment call, not a guarantee (one spot-checked case, `CS F211`,
      confirmed correct against the bulletin's semester-plan ordering)

## Known, reported limitations (for the Discussion & Limitations section)

- Per-term credit-window sum constraints are explicitly out of scope for
  this module (they're binary-constraint-only territory via AC-3; the
  proposal already flags this as Pair B's bounds-checking responsibility,
  not this resolver's).
- `reachable_from()` ignores term count and credit ceilings by design — it
  answers "structurally possible ever," not "possible within N remaining
  semesters." That's the CSP/A* layer's job.
- The source data (`prereqs.json`) only covers prerequisites — it has no
  credits/categories/term-parity at all, confirmed by inspecting the full
  `handoutsforyou` repo source, not just its public output file.

## Quick self-check before committing

```
python3 build_kb.py              # regenerates kb_courses.json + validation_report.json
python3 entailment.py             # 14/14 tests should pass
python3 fixpoint.py                # demo cascade + category checks
python3 requirement_resolver.py    # full integration smoke test
```
