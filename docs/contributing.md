# Contributing

Branching strategy, PR rules, and commit conventions for LogicForge. Read this before your first commit.

## 1. Branching strategy

**`main` is protected. Nobody commits to `main` directly — ever, including for a demo checkout.** All work happens on personal branches and lands on `main` only via a reviewed Pull Request. PRs merge **straight into `main`** — there is no intermediate integration branch.

```
main                        ← always green, always demo-able, protected — PRs merge straight here
 ├─ pairA/krishna-<feature>
 ├─ pairA/pratham-<feature>
 ├─ pairB/aditya-<feature>
 ├─ pairB/kshitij-<feature>
 ├─ pairC/raj-<feature>
 ├─ pairC/jenil-<feature>
 ├─ pairD/mubeen-<feature>
 └─ pairD/vedant-<feature>
```

**Naming convention:** `<pair>/<firstname>-<short-feature-description>`
Examples: `pairA/krishna-prereq-parser`, `pairB/kshitij-ac3-propagation`, `pairC/raj-astar-heuristics`, `pairD/vedant-infeasibility-core`.

## 2. Day-to-day workflow (every member, every time)

```bash
git checkout main
git pull origin main
git checkout -b pairX/yourname-feature-name

# ... do your work, commit often with meaningful messages ...
git add .
git commit -m "pairX: short description of what changed and why"
git push origin pairX/yourname-feature-name
```

Then open a **Pull Request into `main`** on GitHub.

## 3. PR rules

1. **At least one reviewer required** — ideally your pair partner first (they know the component), then one person from another pair for a sanity check before anything touching the shared planning model (`backend/models/`) or an integration point (`planning_service.py`) merges.
2. **PR description must state:** what changed, which milestone/experiment it serves, and how it was tested.
3. **No merging your own PR** unless it's a trivial doc/typo fix.
4. Keep PRs small and scoped to one feature — easier to review, easier to isolate when something breaks.
5. Squash or keep history as a team decision, but **commit history must reflect work across the semester**, not a last-minute dump — the course guidelines explicitly check for this.
6. Delete your branch after it's merged to keep the branch list readable.
7. If a PR changes `backend/models/` (shared by Pair B and Pair C) or `backend/services/planning_service.py` (the integration seam Pair D owns), say so explicitly in the description and get sign-off from the other affected pair, not just one reviewer.

## 4. Commit message convention

```
pairX: <imperative, present-tense summary>

Examples:
pairA: add AC-3 arc consistency pass to KB loader
pairC: implement critical-path admissible heuristic
pairD: add deletion-based conflicting-constraint extraction
```

## 5. Report contributions (`docs/report/`)

**Pair D (Mubeen Khan, Vedant Shah) owns compiling `docs/report/`** — the written report, individual-contributions section, and final structure (Introduction, Background/Related Work, Method, Results/Evaluation, Discussion & Limitations). This fits their existing role: they're already independently re-validating every pair's output for the verifier, so they're positioned to pull together what each component actually does and how it was tested.

- Every pair writes their **own section** (what you built, how you tested it) as a PR into `docs/report/`, same branch and review rules as code.
- Pair D merges, edits for consistency, and owns the final structure.
- Each pair is still responsible for the accuracy of their own section in the viva — Pair D compiling it does not transfer ownership of content. If you can't explain a section you submitted, it's treated as if you didn't do that part.

## 6. AI tool usage

Log any AI-assisted work (Claude, ChatGPT, Copilot, etc.) in [`docs/ai_usage.md`](./ai_usage.md) — tool, what it helped with, and how you verified the output — either as part of your PR or shortly after. You own anything you submit; "the AI generated it" is not an excuse for an error, and you must be able to explain it in the viva.
