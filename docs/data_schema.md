# Curriculum Data Schema

GraphMind's curriculum data is split into three clearly separate layers so that branches and minors can be added and validated **independently**, and so the system never silently treats an unvalidated branch as supported.

```
data/curriculum/
├── common/
│   └── courses.json            # courses every student takes regardless of branch (HSS, labs, electives shared across branches)
├── branches/
│   ├── cse/
│   │   ├── courses.json        # courses specific to this branch
│   │   └── requirements.json   # this branch's requirement categories + credit minimums
│   ├── ece/
│   │   ├── courses.json
│   │   └── requirements.json
│   └── e_and_i/
│       ├── courses.json
│       └── requirements.json
├── minors/
│   └── <minor_name>/
│       ├── courses.json        # courses specific to the minor
│       └── requirements.json   # the minor's own credit floor + eligible-course rules
├── branches.json               # registry of which branch/minor directories exist
└── VALIDATION_STATUS.md        # which of the above have passed the validation suite — see §3
```

## 1. Why three layers instead of one flat list

A course like a core CS course belongs to `common/` or a branch's `courses.json` depending on whether it's shared. Keeping common, branch-specific, and minor data in separate files means:

- Pair A can finish and validate one branch (e.g. the toy curriculum, then the team's own branch) without the KB loader needing all branches to exist.
- A validation failure in one branch's `requirements.json` never blocks another branch from being used.
- The planning model only loads the common data plus the one branch (and optional minor) relevant to the student being planned for — it does not assume every branch directory is complete.

## 2. `courses.json` — course object

Each entry in a `courses.json` (common, branch, or minor) represents one `Course` (see `docs/architecture.md` §3 for the corresponding Python model):

| Field | Type | Meaning |
|---|---|---|
| `code` | string | Course code, e.g. `"CS F211"` |
| `title` | string | Display name |
| `credits` | number | Credit value |
| `term_parity` | `"odd"` \| `"even"` \| `"both"` | Which terms this course is offered in |
| `category` | string | Requirement category this course counts toward (must match a category defined in the owning branch's or minor's `requirements.json`, or a shared category for `common/`) |
| `prerequisites` | string \| null | A prerequisite formula string, e.g. `"CS F211 AND (MATH F211 OR MATH F213)"`, parsed by `backend/logic/prerequisite_parser.py`. `null` means no prerequisites. |

## 3. `requirements.json` — branch or minor requirement categories

Each branch or minor defines its own requirement categories and the credit minimum for each:

| Field | Type | Meaning |
|---|---|---|
| `category` | string | Category name, referenced by `courses.json` entries' `category` field |
| `credit_minimum` | number | Minimum credits a student must accumulate in this category to graduate (or complete the minor) |
| `eligible_courses` | list[string] | Course codes that count toward this category, beyond what's implied by `courses.json`'s own `category` field (used for cross-listed or elective-pool courses) |

A category whose `eligible_courses` (plus matching `courses.json` entries) can't reach its own `credit_minimum` is exactly the kind of error the validation suite (`backend/data/validator.py`) is meant to catch — see §4.

## 4. `branches.json` — registry

`branches.json` lists which branch and minor directories exist under `curriculum/`. This is a registry, not a claim of support — a branch being listed here means its directory exists, **not** that it has passed validation. That distinction is tracked separately in `VALIDATION_STATUS.md`.

## 5. `VALIDATION_STATUS.md` — do not claim a branch is supported before this says so

GraphMind is designed to support 3–4 branches, but the proposal is explicit that a focused, validated scope beats a shallow encoding of several branches at once (see `docs/proposal.pdf`, §3). `VALIDATION_STATUS.md` is the single place that tracks, per branch/minor, whether `backend/data/validator.py` has actually been run against it and passed:

```markdown
| Branch / Minor | Courses encoded | Validation suite run | Result |
|---|---|---|---|
| common         | ⬜ | ⬜ | — |
| cse            | ⬜ | ⬜ | — |
| ece            | ⬜ | ⬜ | — |
| e_and_i        | ⬜ | ⬜ | — |
| <minor_name>   | ⬜ | ⬜ | — |
```

The validation suite checks (per the proposal):
- prerequisite-graph cycles
- undefined course codes referenced by a prerequisite or `eligible_courses` entry
- categories whose eligible-course credit total falls below their own `credit_minimum`
- courses unreachable within the degree horizon

**A branch is only "supported" once its row here says the validation suite has run and passed.** README feature claims and demo scope should match this table, not `branches.json`'s mere presence of a directory.
