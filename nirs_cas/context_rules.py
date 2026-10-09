"""Exact, opt-in TaskSpec checks for the assisted CAS branch.

Every rule is conservative: it either supplies an exact witness, or explains
why it cannot decide.  It never reads dataset labels or repairs OCR output.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import sympy as sp

from .exact_math import expression


@dataclass(frozen=True)
class ContextResult:
    status: str  # VALID | INVALID | UNSUPPORTED
    reason: str
    step_id: str | None = None
    rule: str = ""


def _expr(latex: str) -> sp.Expr | None:
    try:
        return expression(latex)
    except (ValueError, TypeError):
        return None


def _last_numeric_answer(steps: list[dict[str, Any]]) -> tuple[str, sp.Expr] | None:
    from .assisted_rules import rhs_chain

    candidates = [s for s in steps if s.get("role") == "answer"] or steps[-1:]
    for step in candidates[-1:]:
        # Last equality is intentionally used; prose is not interpreted.
        try:
            value = rhs_chain(step["latex"])[-1]
        except (ValueError, TypeError):
            return None
        if value is not None and not value.free_symbols:
            return step["step_id"], value
    return None


def _matrix(raw: str) -> sp.MatrixBase | None:
    value = _expr(raw)
    return value if isinstance(value, sp.MatrixBase) else None


def determinant(spec: dict[str, Any]) -> ContextResult:
    raw = (
        " ".join(g["raw_latex"] for g in spec["task"].get("givens", []))
        or spec["task"]["raw_latex"]
        or ""
    )
    match = re.search(r"\\begin\{vmatrix\}.*?\\end\{vmatrix\}", raw, re.S)
    if not match:
        return ContextResult(
            "UNSUPPORTED", "determinant literal was not found", rule="determinant"
        )
    expected = _expr(match[0])
    answer = _last_numeric_answer(spec["steps"])
    if expected is None or answer is None or expected.free_symbols:
        return ContextResult(
            "UNSUPPORTED",
            "determinant or a final numeric equality is not exactly parseable",
            rule="determinant",
        )
    step_id, actual = answer
    truth = sp.simplify(expected - actual).is_zero
    return ContextResult(
        "VALID" if truth is True else ("INVALID" if truth is False else "UNSUPPORTED"),
        "exact determinant evaluation"
        if sp.simplify(expected - actual) == 0
        else "final numeric determinant value differs from exact SymPy determinant",
        step_id,
        "determinant",
    )


def matrix_system(spec: dict[str, Any]) -> ContextResult:
    raw = (
        " ".join(g["raw_latex"] for g in spec["task"].get("givens", []))
        or spec["task"]["raw_latex"]
        or ""
    )
    matches = list(
        re.finditer(
            r"([XY])\s*([+-])\s*([XY])\s*=\s*(\\begin\{bmatrix\}.*?\\end\{bmatrix\})",
            raw,
            re.S,
        )
    )
    if len(matches) != 2:
        return ContextResult(
            "UNSUPPORTED",
            "requires two explicit X/Y matrix equations",
            rule="matrix_system",
        )
    equations: list[tuple[str, str, str, sp.MatrixBase]] = []
    for match in matches:
        matrix = _matrix(match[4])
        if matrix is None:
            return ContextResult(
                "UNSUPPORTED",
                "matrix literal is not exactly parseable",
                rule="matrix_system",
            )
        equations.append((match[1], match[2], match[3], matrix))
    # First contour deliberately supports the canonical X+Y=A, X-Y=B pair.
    plus = next((entry for entry in equations if entry[:3] == ("X", "+", "Y")), None)
    minus = next((entry for entry in equations if entry[:3] == ("X", "-", "Y")), None)
    if plus is None or minus is None or plus[3].shape != minus[3].shape:
        return ContextResult(
            "UNSUPPORTED",
            "only compatible X+Y=A and X-Y=B systems are supported",
            rule="matrix_system",
        )
    expected = {"X": (plus[3] + minus[3]) / 2, "Y": (plus[3] - minus[3]) / 2}
    seen: dict[str, tuple[str, sp.MatrixBase]] = {}
    for step in spec["steps"]:
        match = re.fullmatch(
            r"\s*([XY])\s*=\s*(\\begin\{bmatrix\}.*?\\end\{bmatrix\})\s*",
            step["latex"],
            re.S,
        )
        if match:
            matrix = _matrix(match[2])
            if matrix is None:
                return ContextResult(
                    "UNSUPPORTED",
                    "recorded matrix answer is not exactly parseable",
                    step["step_id"],
                    "matrix_system",
                )
            seen[match[1]] = (step["step_id"], matrix)
    if set(seen) != {"X", "Y"}:
        return ContextResult(
            "UNSUPPORTED",
            "both X and Y must be explicitly recorded",
            rule="matrix_system",
        )
    for name in ("X", "Y"):
        step_id, actual = seen[name]
        if actual.free_symbols:
            return ContextResult(
                "UNSUPPORTED",
                "Matrix answer has unbound entries",
                step_id,
                "matrix_system",
            )
        from .environment import equal_values

        truth = equal_values(actual, expected[name])
        if truth is None:
            return ContextResult(
                "UNSUPPORTED",
                "Matrix comparison is unresolved",
                step_id,
                "matrix_system",
            )
        if truth is False:
            return ContextResult(
                "INVALID",
                f"{name} does not satisfy the exact matrix system",
                step_id,
                "matrix_system",
            )
    last = next(
        s["step_id"]
        for s in reversed(spec["steps"])
        if s["step_id"] in {v[0] for v in seen.values()}
    )
    return ContextResult(
        "VALID",
        "both matrices satisfy the two exact given equations",
        last,
        "matrix_system",
    )


def definite_integral(spec: dict[str, Any]) -> ContextResult:
    target = spec["task"].get("goal", {}).get("target_latex")
    raw = target or spec["task"]["raw_latex"] or ""
    match = re.search(
        r"\\int_\{([^{}]+)\}\^\{([^{}]+)\}\s*(.*?)\\,?\s*d([A-Za-z])", raw
    )
    if not match:
        return ContextResult(
            "UNSUPPORTED",
            "definite integral with explicit bounds was not found",
            rule="definite_integral",
        )
    lower, upper, body, variable_name = match.groups()
    a, b, integrand = _expr(lower), _expr(upper), _expr(body)
    if a is None or b is None or integrand is None:
        return ContextResult(
            "UNSUPPORTED",
            "integral bounds or integrand are not in the exact parser subset",
            rule="definite_integral",
        )
    variables = [
        symbol for symbol in integrand.free_symbols if symbol.name == variable_name
    ]
    if len(variables) != 1:
        return ContextResult(
            "UNSUPPORTED",
            "integrand must contain exactly one integration variable",
            rule="definite_integral",
        )
    variable = variables[0]
    from .exact_math import math, domain

    segment = sp.Interval(min(a, b), max(a, b))
    if sp.Complement(segment, domain(math(body), variable)).is_empty is not True:
        return ContextResult(
            "UNSUPPORTED",
            "Integrand domain on the whole interval is unresolved",
            rule="definite_integral",
        )
    try:
        expected = sp.integrate(integrand, (variable, a, b))
    except (TypeError, ValueError, NotImplementedError):
        return ContextResult(
            "UNSUPPORTED",
            "SymPy could not integrate this definite integral exactly",
            rule="definite_integral",
        )
    if expected.has(sp.Integral, sp.oo, -sp.oo, sp.nan, sp.zoo):
        return ContextResult(
            "UNSUPPORTED",
            "SymPy returned an unevaluated integral",
            rule="definite_integral",
        )
    answer = _last_numeric_answer(spec["steps"])
    if answer is None:
        return ContextResult(
            "UNSUPPORTED",
            "final numeric integral value is absent or unreadable",
            rule="definite_integral",
        )
    step_id, actual = answer
    truth = sp.simplify(expected - actual).is_zero
    return ContextResult(
        "VALID" if truth is True else ("INVALID" if truth is False else "UNSUPPORTED"),
        "exact definite integral evaluation"
        if sp.simplify(expected - actual) == 0
        else "final value differs from exact definite integral",
        step_id,
        "definite_integral",
    )


# Set/scalar rules share the assisted graph grammar.
from .context_extensions import (
    inequality as inequality,
    equation as equation,
    trigonometric as trigonometric,
    scalar_task as scalar_task,
    function_operation as function_operation,
    check_context as check_context,
)
