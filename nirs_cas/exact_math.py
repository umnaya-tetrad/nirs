"""Bounded assisted-only grammar and exact real set operations.

No eval/sympify of model strings. The ordinary parser stays unchanged.
"""

from __future__ import annotations

import re
import sympy as sp

from .parser import (
    _Parser,
    _matrix_atoms,
    normalize_latex,
    ParseError,
    ParsedMath,
    FUNCTIONS,
)
from .verifier import _domain, _set_equal


class ExactParser(_Parser):
    def exponent(self):
        if self.peek() in ("+", "-"):
            sign = -1 if self.take() == "-" else 1
            return sign * super().exponent()
        if self.peek() == "{":
            value = self.group("{")
        elif re.fullmatch(r"[A-Za-z]", self.peek()):
            value = self.atom()
        else:
            return super().exponent()
        value = sp.simplify(value)
        if value.is_Rational:
            if abs(value.p) > 20 or value.q > 12:
                raise ParseError("Exponent exceeds rational bounds")
        elif len(value.free_symbols) != 1 or sp.count_ops(value) > 12:
            raise ParseError("Only a bounded single-variable exponent is supported")
        return value

    def power(self, base, exponent):
        if exponent.is_Rational:
            return super().power(base, exponent)
        base = sp.simplify(base)
        if base.free_symbols or base.is_positive is not True:
            raise ParseError("Symbolic exponent requires a constant positive base")
        return sp.Pow(base, exponent, evaluate=False)

    def unary(self):
        # Permit a symbolic factorial only here; evaluate after exact bindings.
        if self.peek() in ("+", "-"):
            op = self.take()
            value = self.unary()
            return value if op == "+" else -value
        value = self.atom()
        while self.peek() == "!":
            self.take()
            number = sp.simplify(value)
            if number.free_symbols:
                self.restrict("nonnegative", number)
                value = sp.factorial(number, evaluate=False)
            elif number.is_Integer is True and 0 <= number <= 100:
                value = sp.factorial(number)
            else:
                raise ParseError("Factorial needs an integer from 0 to 100")
        if self.peek() == "^":
            self.take()
            if self.peek() == r"\circ":
                self.take()
                return value * sp.pi / 180
            value = self.power(value, self.exponent())
            if self.peek() == "^":
                raise ParseError("Repeated superscript")
        return value

    def atom(self):
        if (
            self.peek() == r"\log"
            and self.i + 1 < len(self.tokens)
            and self.tokens[self.i + 1] == "_"
        ):
            self.take()
            self.take("_")
            base = self.group("{") if self.peek() == "{" else super().atom()
            base = sp.simplify(base)
            if (
                base.free_symbols
                or base.is_positive is not True
                or (base - 1).is_zero is not False
            ):
                raise ParseError(
                    "Logarithm base must be a positive constant different from 1"
                )
            argument = (
                self.group(self.peek()) if self.peek() in ("(", "{") else self.unary()
            )
            self.restrict("positive", argument)
            return sp.log(argument, evaluate=False) / sp.log(base)
        token = self.peek()
        if (
            token.lstrip("\\") in FUNCTIONS
            and self.i + 1 < len(self.tokens)
            and self.tokens[self.i + 1] in ("(", "{")
        ):
            name = self.take().lstrip("\\")
            argument = self.group(self.peek())
            if name in ("log", "ln"):
                self.restrict("positive", argument)
            if name in ("tan", "sec"):
                self.restrict("nonzero", sp.cos(argument))
            if name in ("cot", "csc"):
                self.restrict("nonzero", sp.sin(argument))
            if name in ("arcsin", "arccos"):
                self.restrict("nonnegative", 1 - argument**2)
            return FUNCTIONS[name](argument)
        return super().atom()


def math(source: str, bindings=None) -> ParsedMath:
    text = normalize_latex(source)
    if re.search(r"\\frac\{d(?:\^\{?\d+\}?)?[A-Za-z]", text) or re.search(
        r"\\frac\s*\{\s*d(?:\s*\^\s*(?:\{\s*\d+\s*\}|\d+))?\s*(?:[A-Za-z]|\\[A-Za-z]+)?\s*\}\s*\{\s*d", text
    ):
        raise ParseError("Differential notation needs a calculus verifier")
    text, atoms, constraints = _matrix_atoms(text)
    if re.search(r"(?<![\\A-Za-z])[A-Za-z]{4,}(?![A-Za-z])", text):
        raise ParseError("Bare word is not an exact mathematical token")
    complex_mode = bool(re.search(r"(?<![A-Za-z])i(?![A-Za-z])", text))
    return ExactParser(text, {**atoms, **(bindings or {})}, constraints, complex_mode=complex_mode).parse()


def expression(source: str) -> sp.Expr:
    parsed = math(source)
    if parsed.is_equation:
        raise ParseError("Expected one expression")
    return parsed.sides[0]


def resolved(value: sp.Set) -> sp.Set:
    if not isinstance(value, sp.Set) or value.has(sp.ConditionSet, sp.Integral):
        raise ParseError("Exact set was not resolved")
    return value


def domain(parsed: ParsedMath, variable: sp.Symbol) -> sp.Set:
    return resolved(_domain(parsed, variable))


def equal_sets(left: sp.Set, right: sp.Set) -> bool | None:
    # Normalize unions of rational pi-periodic families by residues. This is
    # exact integer arithmetic, never a finite sample of possible roots.
    def residues(value):
        terms = value.args if isinstance(value, sp.Union) else (value,)
        families = []
        for term in terms:
            if not isinstance(term, sp.ImageSet) or term.base_set != sp.S.Integers:
                return None
            k = term.lamda.variables[0]
            expr = sp.expand(term.lamda.expr / sp.pi)
            b = sp.simplify(expr.subs(k, 0))
            a = sp.simplify(sp.diff(expr, k))
            if (
                not a.is_Rational
                or not b.is_Rational
                or a == 0
                or sp.simplify(expr - a * k - b) != 0
            ):
                return None
            families.append((abs(a), b))
        return families

    a, b = residues(left), residues(right)
    if a is not None and b is not None:
        scale = sp.ilcm(*[v.q for pair in a + b for v in pair])
        periods = [int(pair[0] * scale) for pair in a + b]
        period = sp.ilcm(*periods)
        if period > 10000:
            return None

        def canonical(families):
            out = set()
            for p, r in families:
                p, r = int(p * scale), int(r * scale)
                out.update((r + i * p) % period for i in range(int(period) // p))
            return out

        return canonical(a) == canonical(b)
    return _set_equal(left, right)


def finite_restriction(value: sp.Set, interval: sp.Interval) -> sp.Set:
    if interval in (sp.S.EmptySet,) or interval.is_FiniteSet:
        return resolved(sp.Intersection(value, interval))
    if (
        not isinstance(interval, sp.Interval)
        or interval.start in (-sp.oo, sp.oo)
        or interval.end in (-sp.oo, sp.oo)
    ):
        raise ParseError("A finite interval is required")
    if isinstance(value, sp.Union):
        return sp.Union(*(finite_restriction(term, interval) for term in value.args))
    if isinstance(value, sp.ImageSet) and value.base_set == sp.S.Integers:
        k = value.lamda.variables[0]
        f = sp.expand(value.lamda.expr)
        a = sp.simplify(sp.diff(f, k))
        b = sp.simplify(f.subs(k, 0))
        if a.is_positive is not True or sp.simplify(f - a * k - b) != 0:
            raise ParseError("Only positive affine periodic families are supported")
        lo, hi = (
            sp.simplify((interval.start - b) / a),
            sp.simplify((interval.end - b) / a),
        )
        first = sp.floor(lo) + 1 if interval.left_open else sp.ceiling(lo)
        last = sp.ceiling(hi) - 1 if interval.right_open else sp.floor(hi)
        if not first.is_Integer or not last.is_Integer or last - first > 10000:
            raise ParseError(
                "Finite family restriction exceeds exact enumeration budget"
            )
        return sp.FiniteSet(
            *(sp.simplify(f.subs(k, i)) for i in range(int(first), int(last) + 1))
        )
    result = resolved(sp.Intersection(value, interval))
    if not isinstance(result, sp.FiniteSet) and result != sp.S.EmptySet:
        raise ParseError("SymPy did not construct an exact finite root set")
    return result


RELATION = re.compile(r"\\(?:leq|geq|neq|le|ge|ne)(?![A-Za-z])|<=|>=|!=|[<>=]")
OPS = {
    "<": sp.Lt,
    ">": sp.Gt,
    "<=": sp.Le,
    ">=": sp.Ge,
    "=": sp.Eq,
    "!=": sp.Ne,
    r"\le": sp.Le,
    r"\leq": sp.Le,
    r"\ge": sp.Ge,
    r"\geq": sp.Ge,
    r"\ne": sp.Ne,
    r"\neq": sp.Ne,
}


def relation_set(source: str, variable=None) -> tuple[sp.Set, sp.Symbol]:
    matches = list(RELATION.finditer(source))
    if not matches:
        raise ParseError("No relation found")
    parts = RELATION.split(source)
    parsed = [math(p) for p in parts]
    symbols = set().union(*(set(p.symbols) for p in parsed))
    if variable is None:
        if len(symbols) != 1:
            raise ParseError("Requires exactly one real variable")
        variable = next(iter(symbols))
    if symbols - {variable}:
        raise ParseError("Unbound parameters in relation")
    result = sp.S.Reals
    for p in parsed:
        result = sp.Intersection(result, domain(p, variable))
    for i, match in enumerate(matches):
        left, right = parsed[i].sides[0], parsed[i + 1].sides[0]
        op = OPS[match[0]]
        if op in (sp.Eq, sp.Ne):
            roots = resolved(sp.solveset(left - right, variable, domain=sp.S.Reals))
            solution = roots if op == sp.Eq else sp.Complement(sp.S.Reals, roots)
        else:
            solution = sp.solve_univariate_inequality(
                op(left, right), variable, relational=False
            )
        result = resolved(sp.Intersection(result, solution))
    return result, variable
