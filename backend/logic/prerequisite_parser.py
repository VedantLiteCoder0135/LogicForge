"""
GraphMind — backend/logic/prerequisite_parser.py (Pair A)

Parses a prerequisite formula STRING, as stored in courses.json's
`prerequisites` field, into the tree shape prerequisite_checker.py and
forward_chaining.py consume:

    {'kind': 'leaf', 'course': <code>, 'relation': 'PRE' | 'CO'}
    {'kind': 'and',  'items': [node, ...]}
    {'kind': 'or',   'items': [node, ...]}

Grammar (informal):

    formula   := term (CONNECTIVE term)*          -- all same connective at one level
    term      := '(' formula ')' | COURSE_CODE [':CO']
    CONNECTIVE:= 'AND' | 'OR'

Example: "CS F211 AND (MATH F211 OR MATH F213)"
      -> {'kind': 'and', 'items': [
              {'kind': 'leaf', 'course': 'CS F211', 'relation': 'PRE'},
              {'kind': 'or', 'items': [
                  {'kind': 'leaf', 'course': 'MATH F211', 'relation': 'PRE'},
                  {'kind': 'leaf', 'course': 'MATH F213', 'relation': 'PRE'}]}]}

CO-requisite convention: a course code suffixed with ':CO' (e.g.
"BIO F341:CO") is a co-requisite leaf; no suffix means PRE. This
convention is NOT specified in docs/data_schema.md -- it's a design
decision made here, since the schema's own example only shows PRE-style
formulas. Flag this for confirmation with whoever owns
backend/models/course.py, since that field is read by more than this
module.

A null/None/empty string input means no prerequisites (course is open),
matching data_schema.md's "`null` means no prerequisites."

Mixing AND and OR at the SAME parenthesis level without explicit
grouping (e.g. "A AND B OR C") is deliberately rejected with a clear
error rather than guessed at -- unlike the raw TTD export Pair A's
build_kb.py had to reverse-engineer, this string format is written by
us, so there's no excuse for the kind of ambiguity that needed the
trailing-connective heuristic there. Every mixed level must be
parenthesized explicitly, e.g. "(A OR B) AND C".
"""

import re

_TOKEN_RE = re.compile(r'\(|\)|AND|OR|[A-Z]+(?:/[A-Z]+)*\s[FG]\d{3}(?::CO)?')


class PrerequisiteParseError(Exception):
    pass


def tokenize(formula_str: str):
    pos = 0
    tokens = []
    s = formula_str.strip()
    while pos < len(s):
        if s[pos].isspace():
            pos += 1
            continue
        m = _TOKEN_RE.match(s, pos)
        if not m:
            raise PrerequisiteParseError(
                f'Could not tokenize at position {pos} in {formula_str!r}: ...{s[pos:pos+20]!r}'
            )
        tokens.append(m.group(0))
        pos = m.end()
    return tokens


def _parse_term(tokens, i):
    if tokens[i] == '(':
        node, i = _parse_formula(tokens, i + 1)
        if i >= len(tokens) or tokens[i] != ')':
            raise PrerequisiteParseError(f'Expected ) at token {i}, got {tokens[i:i+1]}')
        return node, i + 1
    tok = tokens[i]
    if tok in ('AND', 'OR', ')'):
        raise PrerequisiteParseError(f'Expected a course code or ( at token {i}, got {tok!r}')
    if tok.endswith(':CO'):
        course, relation = tok[:-3], 'CO'
    else:
        course, relation = tok, 'PRE'
    return {'kind': 'leaf', 'course': course, 'relation': relation}, i + 1


def _parse_formula(tokens, i):
    node, i = _parse_term(tokens, i)
    items = [node]
    connective = None
    while i < len(tokens) and tokens[i] in ('AND', 'OR'):
        this_connective = tokens[i]
        if connective is None:
            connective = this_connective
        elif this_connective != connective:
            raise PrerequisiteParseError(
                f"Mixed AND/OR at the same level without parentheses (token {i}). "
                f"Found {connective!r} then {this_connective!r} -- wrap the mixed "
                f"part in parentheses explicitly, e.g. '(A OR B) AND C'."
            )
        term, i = _parse_term(tokens, i + 1)
        items.append(term)
    if connective is None:
        return node, i
    kind = 'and' if connective == 'AND' else 'or'
    return {'kind': kind, 'items': items}, i


def parse_prerequisites(formula_str):
    """Entry point. formula_str may be None, '', or a formula string."""
    if not formula_str:
        return None
    tokens = tokenize(formula_str)
    if not tokens:
        return None
    node, i = _parse_formula(tokens, 0)
    if i != len(tokens):
        raise PrerequisiteParseError(
            f'Unexpected trailing tokens after position {i}: {tokens[i:]}'
        )
    return node


if __name__ == '__main__':
    tests = [
        (None, None),
        ('', None),
        ('CS F111', {'kind': 'leaf', 'course': 'CS F111', 'relation': 'PRE'}),
        ('CS F211 AND (MATH F211 OR MATH F213)', {
            'kind': 'and', 'items': [
                {'kind': 'leaf', 'course': 'CS F211', 'relation': 'PRE'},
                {'kind': 'or', 'items': [
                    {'kind': 'leaf', 'course': 'MATH F211', 'relation': 'PRE'},
                    {'kind': 'leaf', 'course': 'MATH F213', 'relation': 'PRE'}]}]}),
        ('BIO F341:CO', {'kind': 'leaf', 'course': 'BIO F341', 'relation': 'CO'}),
        ('(CS F222 OR MATH F213)', {'kind': 'or', 'items': [
            {'kind': 'leaf', 'course': 'CS F222', 'relation': 'PRE'},
            {'kind': 'leaf', 'course': 'MATH F213', 'relation': 'PRE'}]}),
    ]
    passed = 0
    for formula_str, expected in tests:
        actual = parse_prerequisites(formula_str)
        ok = actual == expected
        passed += ok
        print(f"[{'OK' if ok else 'FAIL'}] {formula_str!r} -> {actual}")

    # mixed AND/OR without parens should raise
    try:
        parse_prerequisites('A F111 AND B F111 OR C F111')
        print('[FAIL] expected PrerequisiteParseError for unparenthesized mixed AND/OR')
    except PrerequisiteParseError as e:
        print(f'[OK] correctly rejected unparenthesized mix: {e}')
        passed += 1

    print(f'\n{passed}/{len(tests) + 1} passed')
