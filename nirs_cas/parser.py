"""Small, fully consuming LaTeX grammar; no eval or task-specific rewrites.

Keep source domain restrictions separately: simplifying x/x must not erase x != 0.
This is intentionally a school-algebra subset, not a general TeX interpreter.
"""
from dataclasses import dataclass
import re
from typing import Literal

import sympy as sp


class ParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedMath:
    normalized_latex: str
    sides: tuple[sp.Expr, ...]
    constraints: tuple[tuple[str, sp.Expr], ...]
    symbols: tuple[sp.Symbol, ...]

    @property
    def is_equation(self) -> bool:
        return len(self.sides) == 2

    def to_dict(self) -> dict:
        return {
            "normalized_latex": self.normalized_latex,
            "kind": "equation" if self.is_equation else "expression",
            "sides": [sp.sstr(x) for x in self.sides],
            "symbols": [str(x) for x in self.symbols],
            "domain": "real",
            "constraints": [{"kind": kind, "expression": sp.sstr(expr)}
                            for kind, expr in self.constraints],
        }


@dataclass(frozen=True)
class ParseResult:
    status: Literal["OK", "PARSE_FAILED"]
    value: ParsedMath | None = None
    reason: str | None = None

    def to_dict(self) -> dict:
        return {"status": self.status, "value": self.value.to_dict() if self.value else None,
                "reason": self.reason}


def normalize_latex(source: str) -> str:
    if not isinstance(source, str) or not source.strip():
        raise ParseError("Expected a nonempty LaTeX string")
    if len(source) > 2048:
        raise ParseError("Expression exceeds 2048 characters")
    text = source.strip()
    for left, right in [("$$", "$$"), ("$", "$"), (r"\(", r"\)"), (r"\[", r"\]")]:
        if text.startswith(left) and text.endswith(right):
            text = text[len(left):-len(right)].strip()
            break
    text = text.translate(str.maketrans({"−": "-", "×": "*", "÷": "/", "·": "*"}))
    text = re.sub(r"\\(?:left|right|displaystyle)(?![A-Za-z])", "", text)
    text = re.sub(r"\\(?:[,!;:]|quad(?![A-Za-z])|qquad(?![A-Za-z])| )", " ", text)
    text = re.sub(r"\\(?:dfrac|tfrac)(?![A-Za-z])", r"\\frac", text)
    text = re.sub(r"\\(?:cdot|times)(?![A-Za-z])", "*", text)
    text = re.sub(r"\\div(?![A-Za-z])", "/", text)
    return text.strip()


TOKEN = re.compile(r"\s+|\\[A-Za-z]+|(?:\d+(?:\.\d+)?|\.\d+)|[A-Za-z]|[+*/^=(){}\[\]-]")
GREEK = {"alpha", "beta", "gamma", "delta", "theta", "lambda", "mu", "sigma", "phi", "omega"}


class _Parser:
    def __init__(self, text: str):
        self.text = text
        self.tokens: list[str] = []
        offset = 0
        # Bare function names must not silently become products of letters.
        if re.search(r"(?<![\\A-Za-z])(?:sin|cos|tan|cot|log|ln|exp|sqrt|arcsin|arccos)\b", text):
            raise ParseError("Functions are outside the selected algebra subset")
        for match in TOKEN.finditer(text):
            if match.start() != offset:
                raise ParseError(f"Unsupported input at character {offset}")
            offset = match.end()
            token = match.group()
            if not token.isspace():
                self.tokens.append(token)
        if offset != len(text):
            raise ParseError(f"Unsupported input at character {offset}")
        if len(self.tokens) > 256:
            raise ParseError("Expression exceeds 256 tokens")
        self.i = 0
        self.depth = 0
        self.constraints: list[tuple[str, sp.Expr]] = []
        self.symbols: set[sp.Symbol] = set()

    def peek(self) -> str:
        return self.tokens[self.i] if self.i < len(self.tokens) else ""

    def take(self, expected: str | None = None) -> str:
        token = self.peek()
        if not token or (expected is not None and token != expected):
            raise ParseError(f"Expected {expected or 'token'}, got {token or 'end of input'}")
        self.i += 1
        return token

    def parse(self) -> ParsedMath:
        sides = [self.expression()]
        if self.peek() == "=":
            self.take("=")
            sides.append(self.expression())
        if self.peek():
            raise ParseError(f"Unconsumed token {self.peek()!r}; one expression/equation per step")
        return ParsedMath(self.text, tuple(sides), tuple(self.constraints),
                          tuple(sorted(self.symbols, key=str)))

    def expression(self) -> sp.Expr:
        value = self.product()
        while self.peek() in ("+", "-"):
            op = self.take()
            rhs = self.product()
            if op == "-":
                rhs = sp.Mul(-1, rhs, evaluate=False)
            value = sp.Add(value, rhs, evaluate=False)
        return value

    @staticmethod
    def starts_atom(token: str) -> bool:
        return bool(token) and (token in ("(", "{", "[") or token.startswith("\\")
                                or token[0].isalnum() or token[0] == ".")

    def product(self) -> sp.Expr:
        value = self.unary()
        while True:
            token = self.peek()
            if token in ("*", "/"):
                self.take()
                rhs = self.unary()
                if token == "/":
                    self.restrict("nonzero", rhs)
                    rhs = sp.Pow(rhs, -1, evaluate=False)
                value = sp.Mul(value, rhs, evaluate=False)
            elif self.starts_atom(token):
                # 2 3 is not a valid implicit multiplication convention.
                if re.fullmatch(r"[\d.]+", token) and re.fullmatch(r"[\d.]+", self.tokens[self.i - 1]):
                    raise ParseError("Adjacent numeric literals require an explicit operator")
                value = sp.Mul(value, self.unary(), evaluate=False)
            else:
                return value

    def unary(self) -> sp.Expr:
        if self.peek() in ("+", "-"):
            op = self.take()
            # Depth bounded by token limit for repeated unary signs.
            rhs = self.unary()
            return rhs if op == "+" else sp.Mul(-1, rhs, evaluate=False)
        value = self.atom()
        if self.peek() == "^":
            self.take()
            power = self.exponent()
            value = self.power(value, power)
            if self.peek() == "^":
                raise ParseError("Repeated superscript; use explicit grouping")
        return value

    def exponent(self) -> sp.Rational:
        braced = self.peek() == "{"
        if braced:
            self.take("{")
        sign = 1
        if braced and self.peek() in ("+", "-"):
            sign = -1 if self.take() == "-" else 1
        token = self.take()
        if not token.isdecimal() or len(token) > 2 or (not braced and len(token) != 1):
            raise ParseError("Use an integer or a braced rational exponent; |numerator| <= 20")
        numerator = int(token) * sign
        denominator = 1
        if braced and self.peek() == "/":
            self.take("/")
            token = self.take()
            if not token.isdecimal() or len(token) > 2:
                raise ParseError("Invalid exponent denominator")
            denominator = int(token)
        if braced:
            self.take("}")
        if abs(numerator) > 20 or not 1 <= denominator <= 12:
            raise ParseError("Exponent outside configured bounds")
        return sp.Rational(numerator, denominator)

    def power(self, base: sp.Expr, exponent: sp.Rational) -> sp.Expr:
        def weight(expr):
            if expr.is_Atom:
                return 1
            if expr.is_Pow and expr.exp.is_Rational:
                return weight(expr.base) * max(1, abs(expr.exp))
            return sum(weight(arg) for arg in expr.args)
        if weight(base) * max(1, abs(exponent)) > 256:
            raise ParseError("Power expression exceeds complexity budget")
        if exponent <= 0:
            self.restrict("nonzero", base)
        if exponent.q % 2 == 0:
            self.restrict("nonnegative", base)
        # Real odd roots, including negative arguments; never principal complex roots.
        if exponent.q > 1 and exponent.q % 2:
            return sp.Pow(sp.real_root(base, exponent.q), exponent.p, evaluate=False)
        return sp.Pow(base, exponent, evaluate=False)

    def restrict(self, kind: str, expr: sp.Expr) -> None:
        value = sp.simplify(expr)
        if not value.free_symbols:
            valid = value.is_nonzero if kind == "nonzero" else value.is_nonnegative
            if valid is not True:
                raise ParseError(f"Undefined real expression: {kind} restriction fails")
        self.constraints.append((kind, expr))

    def group(self, opener: str) -> sp.Expr:
        self.take(opener)
        self.depth += 1
        if self.depth > 24:
            raise ParseError("Nesting exceeds 24 groups")
        value = self.expression()
        self.take({"(": ")", "{": "}", "[": "]"}[opener])
        self.depth -= 1
        return value

    def atom(self) -> sp.Expr:
        token = self.peek()
        if token in ("(", "{", "["):
            return self.group(token)
        token = self.take()
        if re.fullmatch(r"(?:\d+(?:\.\d+)?|\.\d+)", token):
            if sum(c.isdigit() for c in token) > 12:
                raise ParseError("Numeric literal exceeds 12 digits")
            return sp.Rational(token)
        if re.fullmatch(r"[A-Za-z]", token) or token.lstrip("\\") in GREEK:
            symbol = sp.Symbol(token.lstrip("\\"), real=True)
            self.symbols.add(symbol)
            if len(self.symbols) > 8:
                raise ParseError("More than 8 variables")
            return symbol
        if token == r"\pi":
            return sp.pi
        if token == r"\frac":
            numerator = self.group("{")
            denominator = self.group("{")
            self.restrict("nonzero", denominator)
            return sp.Mul(numerator, sp.Pow(denominator, -1, evaluate=False), evaluate=False)
        if token == r"\sqrt":
            degree = 2
            if self.peek() == "[":
                self.take("[")
                n = self.take()
                if not n.isdecimal() or len(n) > 2 or not 2 <= int(n) <= 12:
                    raise ParseError("Root index must be an integer from 2 to 12")
                degree = int(n)
                self.take("]")
            return self.power(self.group("{"), sp.Rational(1, degree))
        raise ParseError(f"Unsupported token {token!r}")


def parse_latex(source: str) -> ParseResult:
    """Return PARSE_FAILED rather than accepting a prefix or inventing a verdict."""
    try:
        value = _Parser(normalize_latex(source)).parse()
        return ParseResult("OK", value)
    except (ParseError, RecursionError, ValueError, TypeError, ZeroDivisionError) as exc:
        return ParseResult("PARSE_FAILED", reason=str(exc))
