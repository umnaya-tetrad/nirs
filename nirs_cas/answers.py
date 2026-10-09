"""Fully consuming answer normalizer. Raw LaTeX and failure reasons survive."""

from __future__ import annotations
from dataclasses import dataclass
import re
import sympy as sp

from .parser import ParseError, normalize_latex
from .exact_math import expression, relation_set


def strip_answer_label(source):
    """Remove only a leading presentation label, never a condition in prose."""
    source = source.strip()
    while True:
        match = re.match(r"\\text\{([^{}]*)\}\s*", source)
        if not match:
            break
        label = match[1].strip().lower()
        if label not in {
            "ответ",
            "ответ:",
            "answer",
            "answer:",
            "a)",
            "b)",
            "а)",
            "б)",
            "i.",
            "ii.",
        } and not re.fullmatch(r"(?:ответ|answer):\s*[абab]\)", label):
            break
        source = source[match.end() :]
    return source


@dataclass(frozen=True)
class Answer:
    raw_latex: str
    value: sp.Set | None = None
    reason: str | None = None

    @property
    def status(self):
        return "OK" if self.value is not None else "PARSE_FAILED"

    def to_dict(self):
        return {
            "raw_latex": self.raw_latex,
            "status": self.status,
            "set": sp.sstr(self.value) if self.value is not None else None,
            "reason": self.reason,
        }


def split_parts(text, separators=",;"):
    depth, start, parts = 0, 0, []
    for i, char in enumerate(text):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth < 0:
                raise ParseError("Unbalanced delimiters")
        elif char in separators and depth == 0:
            parts.append(text[start:i].strip())
            start = i + 1
    if depth:
        raise ParseError("Unbalanced delimiters")
    return parts + [text[start:].strip()]


def _bound(raw):
    raw = raw.strip()
    if raw in (r"\infty", r"+\infty", "∞", "+∞"):
        return sp.oo
    if raw in (r"-\infty", "-∞"):
        return -sp.oo
    result = sp.simplify(expression(raw))
    if result.free_symbols or result.is_real is not True:
        raise ParseError("Interval bounds must be explicit real constants")
    return result


def _values(raw, parameters):
    raw = re.sub(r"^[A-Za-z](?:_\{?\d+\}?)?\s*=", "", raw).strip()
    variants = [raw]
    if r"\pm" in raw:
        if raw.count(r"\pm") != 1:
            raise ParseError("Multiple independent ± signs are ambiguous")
        variants = [raw.replace(r"\pm", sign) for sign in ("+", "-")]
    values = []
    for variant in variants:
        expr = sp.simplify(expression(variant))
        if expr.free_symbols:
            if len(expr.free_symbols) != 1:
                raise ParseError(
                    "Only affine one-parameter integer families are supported"
                )
            old = next(iter(expr.free_symbols))
            if old.name not in parameters:
                raise ParseError(
                    "A periodic parameter requires an explicit integer declaration"
                )
            k = sp.Symbol(old.name, integer=True)
            expr = sp.expand(expr.subs(old, k))
            a = sp.simplify(sp.diff(expr, k))
            b = sp.simplify(expr.subs(k, 0))
            if (
                a.free_symbols
                or a.is_real is not True
                or a.is_zero is not False
                or sp.simplify(expr - a * k - b) != 0
            ):
                raise ParseError("Non-affine or unresolved periodic family")
            if a.is_negative:
                a = -a
            if a.is_positive is not True:
                raise ParseError("Periodic spacing is unresolved")
            values.append(sp.ImageSet(sp.Lambda(k, a * k + b), sp.S.Integers))
        elif expr.is_real is True:
            values.append(sp.FiniteSet(expr))
        else:
            raise ParseError("Expected explicit real roots")
    return sp.Union(*values)


def parse_answer(source: str, variable=None) -> Answer:
    try:
        text = (
            normalize_latex(strip_answer_label(source))
            .replace(r"\{", "{")
            .replace(r"\}", "}")
        )
        if r"\text" in text:
            raise ParseError("Prose is not a mathematical answer")
        text = text.replace("∈", r"\in").replace("∪", r"\cup").replace("±", r"\pm")
        parameters = set()
        declaration = re.compile(
            r"(?:[,;]\s*)?([knl])\s*\\in\s*(?:\\mathbb\{Z\}|\\mathbb Z|ℤ)"
        )
        for match in declaration.finditer(text):
            parameters.add(match[1])
        text = declaration.sub("", text).strip().strip(",; ")
        names = set(
            re.findall(r"(?<![A-Za-z\\])([A-Za-z])(?:_\{?\d+\}?)?\s*(?:=|\\in)", text)
        )
        if len(names) > 1 or (
            variable is not None and names and names != {variable.name}
        ):
            raise ParseError("Independent variables require separate answer parts")
        # Remove only an explicit membership prefix; never search for a substring.
        text = re.sub(r"^[A-Za-z]\s*\\in\s*", "", text)
        terms = re.split(r"\\cup(?![A-Za-z])", text)
        values = []
        for term in terms:
            term = term.strip().strip(",; ")
            if not term:
                raise ParseError("Empty answer part")
            if term in (r"\varnothing", r"\emptyset", "{}"):
                values.append(sp.S.EmptySet)
                continue
            if term in (r"\mathbb{R}", "ℝ"):
                values.append(sp.S.Reals)
                continue
            if (
                term[0] in "[("
                and term[-1] in "] )".replace(" ", "")
                and len(split_parts(term[1:-1])) == 2
            ):
                lo, hi = split_parts(term[1:-1])
                a, b = _bound(lo), _bound(hi)
                if (a == -sp.oo and term[0] != "(") or (b == sp.oo and term[-1] != ")"):
                    raise ParseError("Infinity is not an included endpoint")
                if (
                    a in (-sp.oo, sp.oo)
                    and a != -sp.oo
                    or b in (-sp.oo, sp.oo)
                    and b != sp.oo
                ):
                    raise ParseError("Invalid infinite endpoint")
                if (b - a).is_negative is True:
                    raise ParseError("Interval endpoints are reversed")
                values.append(sp.Interval(a, b, term[0] == "(", term[-1] == ")"))
                continue
            if term.startswith("{") and term.endswith("}"):
                term = term[1:-1]
            if re.search(r"\\(?:leq|geq|neq|le|ge|ne)(?![A-Za-z])|[<>]", term):
                values.append(relation_set(term, variable)[0])
                continue
            parts = split_parts(term)
            if any(not p for p in parts):
                raise ParseError("Empty root list item")
            values.append(sp.Union(*(_values(p, parameters) for p in parts)))
        return Answer(source, sp.Union(*values))
    except (
        ValueError,
        TypeError,
        NotImplementedError,
        RecursionError,
        ZeroDivisionError,
    ) as exc:
        return Answer(source, reason=str(exc))


def parse_answer_parts(sources: list[str], variable=None) -> list[Answer]:
    """Independent answer components remain separate, rather than being unioned."""
    return [parse_answer(source, variable) for source in sources]
