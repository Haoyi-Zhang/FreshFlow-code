"""Parser and operations for the small free constructor algebra."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterator, TypeAlias

Term: TypeAlias = tuple
_TOKEN = re.compile(r"\s*(pair|src|unit|[A-Za-z][A-Za-z0-9-]*|[(),])")


class TermError(ValueError):
    """A malformed or over-sized term."""


@dataclass
class _Tokens:
    items: list[str]
    pos: int = 0

    def take(self, expected: str | None = None) -> str:
        if self.pos >= len(self.items):
            raise TermError("unexpected end of term")
        item = self.items[self.pos]
        if expected is not None and item != expected:
            raise TermError(f"expected {expected!r}, found {item!r}")
        self.pos += 1
        return item


def _tokenize(text: str) -> list[str]:
    if not isinstance(text, str) or not text or len(text) > 100_000:
        raise TermError("term must be a nonempty string of at most 100000 characters")
    out: list[str] = []
    at = 0
    while at < len(text):
        match = _TOKEN.match(text, at)
        if match is None:
            raise TermError(f"invalid term syntax near offset {at}")
        out.append(match.group(1))
        at = match.end()
    return out


def parse_term(text: str, *, max_depth: int = 128) -> Term:
    tokens = _Tokens(_tokenize(text))

    def parse(depth: int) -> Term:
        if depth > max_depth:
            raise TermError("term depth exceeds limit")
        head = tokens.take()
        if head == "unit":
            return ("unit",)
        if head == "src":
            tokens.take("(")
            name = tokens.take()
            if name in {"pair", "src", "unit", "(", ")", ","}:
                raise TermError("invalid origin name")
            tokens.take(")")
            return ("src", name)
        if head == "pair":
            tokens.take("(")
            left = parse(depth + 1)
            tokens.take(",")
            right = parse(depth + 1)
            tokens.take(")")
            return ("pair", left, right)
        raise TermError(f"unknown constructor {head!r}")

    term = parse(0)
    if tokens.pos != len(tokens.items):
        raise TermError("trailing tokens in term")
    return term


def format_term(term: Term) -> str:
    if term[0] == "unit":
        return "unit"
    if term[0] == "src":
        return f"src({term[1]})"
    if term[0] == "pair":
        return f"pair({format_term(term[1])},{format_term(term[2])})"
    raise TermError("invalid internal term")


def lineage(term: Term) -> frozenset[str]:
    if term[0] == "unit":
        return frozenset()
    if term[0] == "src":
        return frozenset((term[1],))
    if term[0] == "pair":
        return lineage(term[1]) | lineage(term[2])
    raise TermError("invalid internal term")


def iter_origins(term: Term) -> Iterator[str]:
    yield from sorted(lineage(term))
