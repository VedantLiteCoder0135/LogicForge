"""Prerequisite formula strings used by the shared planning model.

The tree shape matches Pair A's ``prerequisite_parser`` and the trees Pair B's
CSP solver evaluates:

    {"kind": "leaf", "course": "CS F211", "relation": "PRE" | "CO"}
    {"kind": "and", "items": [node, ...]}
    {"kind": "or", "items": [node, ...]}

A ``:CO`` suffix marks a corequisite (same term or earlier). No suffix means a
prerequisite (strictly earlier term). Mixed AND/OR at one parenthesis level
is rejected; the writer has to parenthesize it.
"""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"\(|\)|AND|OR|[A-Z]+(?:/[A-Z]+)*\s[FG]\d{3}(?::CO)?")


class PrerequisiteParseError(Exception):
    """Raised when a prerequisite string is not a well-formed formula."""


def tokenize(formula_str: str) -> list[str]:
    pos = 0
    tokens: list[str] = []
    text = formula_str.strip()
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        match = _TOKEN_RE.match(text, pos)
        if not match:
            raise PrerequisiteParseError(
                f"Could not tokenize at position {pos} in {formula_str!r}: "
                f"...{text[pos:pos + 20]!r}"
            )
        tokens.append(match.group(0))
        pos = match.end()
    return tokens


def _parse_term(tokens: list[str], index: int) -> tuple[dict, int]:
    if tokens[index] == "(":
        node, index = _parse_formula(tokens, index + 1)
        if index >= len(tokens) or tokens[index] != ")":
            raise PrerequisiteParseError(
                f"Expected ')' at token {index}, got {tokens[index:index + 1]}"
            )
        return node, index + 1
    tok = tokens[index]
    if tok in ("AND", "OR", ")"):
        raise PrerequisiteParseError(
            f"Expected a course code or '(' at token {index}, got {tok!r}"
        )
    if tok.endswith(":CO"):
        course, relation = tok[:-3], "CO"
    else:
        course, relation = tok, "PRE"
    return {"kind": "leaf", "course": course, "relation": relation}, index + 1


def _parse_formula(tokens: list[str], index: int) -> tuple[dict, int]:
    node, index = _parse_term(tokens, index)
    items = [node]
    connective = None
    while index < len(tokens) and tokens[index] in ("AND", "OR"):
        this = tokens[index]
        if connective is None:
            connective = this
        elif this != connective:
            raise PrerequisiteParseError(
                "Mixed AND/OR at the same level without parentheses. "
                "Wrap the mixed part, e.g. '(A OR B) AND C'."
            )
        term, index = _parse_term(tokens, index + 1)
        items.append(term)
    if connective is None:
        return node, index
    kind = "and" if connective == "AND" else "or"
    return {"kind": kind, "items": items}, index


def parse_prerequisites(formula_str: str | None) -> dict | None:
    """Parse a formula string. ``None`` or ``""`` means the course is open."""
    if not formula_str:
        return None
    tokens = tokenize(formula_str)
    if not tokens:
        return None
    node, index = _parse_formula(tokens, 0)
    if index != len(tokens):
        raise PrerequisiteParseError(
            f"Unexpected trailing tokens after position {index}: {tokens[index:]}"
        )
    return node
