"""
GraphMind — Curriculum KB Builder (Pair A: Krishna Gupta, Pratham Singla)

Takes the raw h4u-style prereqs.json (course name + title squashed together,
flat prereq list with a trailing AND/OR 'condition', occasional pre-built
'prereqs_nested' tree) and produces:

  1. kb_courses.json       -- cleaned course records with code/title split,
                              and prereqs expressed as a propositional formula
                              tree ready for the entailment evaluator.
  2. validation_report.json -- issues found: unresolved references, duplicate
                              course codes, self-references, prereq-graph
                              cycles, and raw name-variant typos we patched.

Design notes / things to explain in viva:

- The flat 'prereqs' list is NOT a clean boolean tree. Each item's
  'condition' field describes the connective glueing THIS item to the NEXT
  item in the list (a "trailing" connective), not a connective that applies
  to the item itself. E.g.:

      [ {A, OR}, {B, OR}, {C, AND} ]   means   (A OR B OR C) AND <next clause>

  Because the file never tells us where an OR-run begins, the safe parse is:
  scan left to right, accumulate a run of items joined by OR, and whenever we
  hit an item whose condition is AND (or we reach the end of the list), close
  that OR-run (as a single item if it has length 1) and AND it with the rest.
  This matches every example we inspected by hand in the real data (e.g.
  EEE F437, ECE F331, EEE F439 all end in exactly one AND after a run of ORs).

  This heuristic is a judgement call, not a guarantee — it is flagged in the
  validation report whenever a list contains both AND and OR so a human can
  sanity-check the parse instead of trusting it blindly.

- When 'prereqs_nested' is already present we trust it over the flat list,
  since it's an explicit tree with no ambiguity.

- Course "name" strings mix course code and title with no delimiter other
  than whitespace, e.g. "BIO F211 BIOLOGICAL CHEMISTRY". We split on the
  pattern: 1-6 letters, space, one letter (F/G) + 3 digits, then title.

- Known raw-data typos (stray internal spaces, alternate titles) cause
  prereq references that don't match any course's own name. We normalize
  whitespace and case before matching, but true unresolved references
  (typos, or courses missing from this export) are reported, not silently
  dropped -- this is the kind of thing the validation suite must catch.
"""

import json
import re
import sys
from collections import defaultdict

COURSE_CODE_RE = re.compile(r'^([A-Z]{2,6}\s[FG]\d{3})\s+(.*)$')

# Matches a leading run of one or more '/'-separated department prefixes
# followed by one or more '/'-separated F/G-codes, e.g.
#   "EEE/ECE F244"                      -> depts=[EEE,ECE]      codes=[F244]
#   "EEE/ INSTR/ ECE F211"              -> depts=[EEE,INSTR,ECE] codes=[F211]
#   "BITS / CHE / ME / MF F201 / F243 / F213 / F213 MATERIAL..." ->
#       depts=[BITS,CHE,ME,MF]          codes=[F201,F243,F213,F213]
CROSSLIST_RE = re.compile(
    r'^((?:[A-Z]+\s*/\s*)*[A-Z]+)\s+((?:[FG]\d{3}\s*/\s*)*[FG]\d{3})\b(.*)$'
)

# Matches a code whose digits got split by a stray space, e.g. "G62 1" -> "G621"
SPLIT_DIGIT_RE = re.compile(r'([FG]\d{1,2})\s+(\d)\b')


def fix_stray_digit_split(cleaned: str) -> str:
    """'MEL G62 1 VLSI DESIGN' -> 'MEL G621 VLSI DESIGN'."""
    return SPLIT_DIGIT_RE.sub(lambda m: m.group(1) + m.group(2), cleaned)


def expand_crosslisted(raw_ref: str, known_codes: set):
    """
    Given a raw prereq reference string, try to expand department/code
    slash-notation into the list of actual course codes it could mean,
    keeping only ones that exist in the catalog. Returns a list of codes
    (possibly a single code, possibly empty if nothing resolves).
    Falls back to normal single-code parsing if there's no slash notation.
    """
    cleaned = re.sub(r'\s+', ' ', raw_ref.strip()).upper()
    cleaned = fix_stray_digit_split(cleaned)

    m = CROSSLIST_RE.match(cleaned)
    if not m:
        single = normalize_key(cleaned)
        return [single] if single in known_codes else ([single] if not known_codes else [])

    dept_part, code_part, _rest = m.groups()
    depts = [d.strip() for d in dept_part.split('/') if d.strip()]
    codes = [c.strip() for c in code_part.split('/') if c.strip()]

    candidates = [f'{d} {c}' for d in depts for c in codes]
    resolved = [c for c in candidates if c in known_codes]
    return resolved if resolved else candidates  # return best-effort even if unresolved, for reporting


def split_code_title(raw_name: str):
    """Split 'CS F211 DISCRETE STRUCTURES' -> ('CS F211', 'DISCRETE STRUCTURES')."""
    cleaned = re.sub(r'\s+', ' ', raw_name.strip())
    m = COURSE_CODE_RE.match(cleaned)
    if not m:
        return None, cleaned
    return m.group(1), m.group(2).strip()


def normalize_key(code_or_name: str) -> str:
    """
    Normalize a course reference to just its code for matching, e.g.
    'BIO F111 GENERAL BIOLOGY' -> 'BIO F111'. Falls back to the cleaned full
    string if no code pattern is found (rare, but we don't want a silent
    KeyError-shaped bug -- these show up as unparsed/unresolved instead).
    """
    cleaned = re.sub(r'\s+', ' ', code_or_name.strip()).upper()
    m = COURSE_CODE_RE.match(cleaned)
    if m:
        return m.group(1)
    return cleaned


def make_leaf_or_crosslist_node(raw_ref: str, relation: str, known_codes: set):
    """
    Build a leaf for a single course reference, expanding department/code
    slash-notation (e.g. 'EEE/ECE F244') into an OR of the resolved
    alternatives when there's more than one. A plain reference with no
    slash notation returns a single leaf as before.
    """
    candidates = expand_crosslisted(raw_ref, known_codes)
    if len(candidates) <= 1:
        code = candidates[0] if candidates else normalize_key(raw_ref)
        return {'kind': 'leaf', 'course': code, 'relation': relation}
    return {
        'kind': 'or',
        'items': [{'kind': 'leaf', 'course': c, 'relation': relation} for c in candidates],
    }


def flat_to_formula(prereq_items, known_codes: set):
    """
    Convert the flat [{prereq_name, pre_cop, condition}, ...] list into a
    nested formula tree, using the 'trailing connective' rule described in
    the module docstring. Returns (formula_node, had_mixed_connectives: bool).
    """
    if not prereq_items:
        return None, False

    conditions_seen = {item.get('condition', 'AND') for item in prereq_items}
    had_mixed = len(conditions_seen) > 1

    and_groups = []
    current_or_run = []

    for item in prereq_items:
        relation = item.get('pre_cop', 'PRE').replace('-', '').replace(' ', '').upper()
        leaf = make_leaf_or_crosslist_node(item['prereq_name'], relation, known_codes)
        current_or_run.append(leaf)
        cond = item.get('condition', 'AND')
        if cond == 'AND':
            # closes the current OR-run; emit it and start fresh
            if len(current_or_run) == 1:
                and_groups.append(current_or_run[0])
            else:
                and_groups.append({'kind': 'or', 'items': current_or_run})
            current_or_run = []
        # if 'OR', keep accumulating into current_or_run

    # leftover run (list ended without a final AND) still needs closing
    if current_or_run:
        if len(current_or_run) == 1:
            and_groups.append(current_or_run[0])
        else:
            and_groups.append({'kind': 'or', 'items': current_or_run})

    if len(and_groups) == 1:
        return and_groups[0], had_mixed
    return {'kind': 'and', 'items': and_groups}, had_mixed


def nested_to_formula(node, known_codes: set):
    """Convert an existing prereqs_nested tree into our internal formula shape."""
    if node is None:
        return None
    if 'prereq_name' in node:
        relation = node.get('pre_cop', 'PRE').replace('-', '').replace(' ', '').upper()
        return make_leaf_or_crosslist_node(node['prereq_name'], relation, known_codes)
    kind = 'and' if node.get('type') == 'AND' else 'or'
    return {'kind': kind, 'items': [nested_to_formula(child, known_codes) for child in node.get('items', [])]}


def collect_leaf_courses(formula):
    """Return the set of course keys referenced anywhere in a formula tree."""
    if formula is None:
        return set()
    if formula['kind'] == 'leaf':
        return {formula['course']}
    out = set()
    for child in formula['items']:
        out |= collect_leaf_courses(child)
    return out


def build():
    with open('prereqs.json') as f:
        raw = json.load(f)

    # ---- pass 1: collect every known course code, so cross-listing and
    #      reference resolution in pass 2 has a catalog to check against ----
    known_codes = set()
    for entry in raw:
        code, _ = split_code_title(entry['name'])
        if code:
            known_codes.add(normalize_key(code))

    courses = {}            # normalized_code -> record
    duplicates = []
    unparsed_names = []

    for entry in raw:
        code, title = split_code_title(entry['name'])
        if code is None:
            unparsed_names.append(entry['name'])
            key = normalize_key(entry['name'])
        else:
            key = normalize_key(code)

        if entry.get('prereqs_nested'):
            formula = nested_to_formula(entry['prereqs_nested'], known_codes)
            had_mixed = False
            source = 'nested'
        else:
            formula, had_mixed = flat_to_formula(entry.get('prereqs', []), known_codes)
            source = 'flat'

        record = {
            'code': code or key,
            'title': title,
            'raw_name': entry['name'],
            'completion_requirement': entry.get('completion_requirement'),
            'formula': formula,
            'formula_source': source,
            'mixed_connectives_in_flat_list': had_mixed,
        }

        if key in courses:
            duplicates.append(key)
        courses[key] = record

    # ---- validation pass ----
    all_codes = set(courses.keys())
    unresolved_refs = defaultdict(list)   # referenced_course -> [courses that reference it]
    self_refs = []
    for key, rec in courses.items():
        if rec['formula'] is None:
            continue
        referenced = collect_leaf_courses(rec['formula'])
        for ref in referenced:
            if ref == key:
                self_refs.append(key)
            if ref not in all_codes:
                unresolved_refs[ref].append(key)

    # ---- cycle detection (simple DFS over PRE edges only; CO edges are
    #      same-term and shouldn't be treated as strict "before" ordering) ----
    graph = defaultdict(set)
    for key, rec in courses.items():
        if rec['formula'] is None:
            continue
        for leaf_course, relation in _iter_leaves_with_relation(rec['formula']):
            if relation == 'PRE' and leaf_course in all_codes:
                graph[key].add(leaf_course)   # key depends on leaf_course

    cycles = find_cycles(graph)

    mixed_flagged = [k for k, r in courses.items() if r['mixed_connectives_in_flat_list']]

    report = {
        'total_courses': len(courses),
        'duplicate_course_keys': sorted(set(duplicates)),
        'unparsed_course_name_strings': unparsed_names,
        'unresolved_prereq_references': {
            ref: sorted(set(referrers)) for ref, referrers in unresolved_refs.items()
        },
        'self_referencing_courses': sorted(set(self_refs)),
        'prerequisite_cycles_found': cycles,
        'flat_lists_with_mixed_AND_OR_needing_manual_review': sorted(mixed_flagged),
        'note': (
            'credits, term-parity (odd/even offering), and requirement-category '
            'data are NOT present in this source and must be joined in from the '
            'Academic Regulations / curriculum handout.'
        ),
    }

    with open('kb_courses.json', 'w') as f:
        json.dump(list(courses.values()), f, indent=2)
    with open('validation_report.json', 'w') as f:
        json.dump(report, f, indent=2)

    return report


def _iter_leaves_with_relation(formula):
    if formula['kind'] == 'leaf':
        yield formula['course'], formula['relation']
    else:
        for child in formula['items']:
            yield from _iter_leaves_with_relation(child)


def find_cycles(graph):
    """DFS-based cycle detection over the PRE dependency graph. Returns a list
    of cycles (each a list of course keys) found."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = defaultdict(int)
    cycles = []

    def dfs(node, path):
        color[node] = GRAY
        path.append(node)
        for nxt in graph.get(node, ()):
            if color[nxt] == GRAY:
                # found a cycle: slice path from nxt's first occurrence
                idx = path.index(nxt)
                cycles.append(path[idx:] + [nxt])
            elif color[nxt] == WHITE:
                dfs(nxt, path)
        path.pop()
        color[node] = BLACK

    for n in list(graph.keys()):
        if color[n] == WHITE:
            dfs(n, [])
    return cycles


if __name__ == '__main__':
    sys.setrecursionlimit(10000)
    report = build()
    print(json.dumps({k: v for k, v in report.items() if k != 'note'}, indent=2)[:3000])
    print('\n... full details in validation_report.json, cleaned KB in kb_courses.json')
