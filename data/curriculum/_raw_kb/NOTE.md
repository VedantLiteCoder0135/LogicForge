# kb_courses.json — NOT used by the runtime

**Confirmed: 0 of 759 courses in this file have a `credits` field.** It also has no `category` or `semester`/`term_parity` fields. This is not an oversight to "complete" — it was never meant to carry that data.

## What this file actually is

`kb_courses.json` is the raw, all-department prerequisite knowledge base built early in Pair A's work (`build_kb.py`, documented fully in `PairA_original_README.md`) by parsing the h4u-sourced `prereqs.json` export and cross-verifying it against the actual TTD-authoritative prerequisite table. It covers **759 courses across every BITS department** — not just `cse`/`eee` — but it only ever captured **prerequisite relationships** (code, title, PRE/CO formula). Credits, requirement categories, and term-parity were never in scope for this file, because that data doesn't exist in the TTD prerequisite export at all — it comes from a completely different source (the Academic Bulletin's semester-wise degree-plan tables), which is a per-branch, per-degree-programme document, not a per-course one.

## What `backend/data/loader.py` actually reads

`backend/data/validator.py`, `backend/logic/`, and `requirement_resolver.py` **never read this file**. They read `data/curriculum/common/courses.json`, `data/curriculum/branches/<branch>/courses.json`, and `data/curriculum/minors/<minor>/courses.json` — files with real credits, categories, and term-parity, sourced directly from the bulletin and individually verified (see `VALIDATION_RUN_LOG.md` for proof this actually runs clean).

## Why it's still kept in the repo

It's genuinely useful as a reference: if the team later wants to add a new branch or expand electives (see `SCOPE_DECISION.md`), this file already has the correct, cross-verified prerequisite formula for any of its 759 courses — someone just needs to look up the course, pull its real credits/category/semester from the bulletin (same method documented in `MIGRATION_NOTES.md`), and add it to the appropriate `courses.json`. Treating it as throwaway and deleting it would mean redoing that cross-verification work from scratch.

## Decision

**Keep, but exclude from the runtime data path and from any "is the KB complete" claim.** If asked in viva/report "does your KB have credits for all 759 courses," the honest answer is: this reference file doesn't and was never meant to; the actual curriculum data the system uses (`data/curriculum/common/` and `data/curriculum/branches/`) does, for every course in the declared `cse`+`eee` scope, each one individually bulletin-verified.
