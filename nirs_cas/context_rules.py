"""Exact, opt-in TaskSpec checks for the assisted CAS branch.

Every rule is conservative: it either supplies an exact witness, or explains
why it cannot decide.  It never reads dataset labels or repairs OCR output.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import sympy as sp

from .parser import parse_latex


@dataclass(frozen=True)
class ContextResult:
    status: str  # VALID | INVALID | UNSUPPORTED
    reason: str
    step_id: str | None = None
    rule: str = ""


def _expr(latex: str) -> sp.Expr | None:
    parsed = parse_latex(latex)
    if parsed.status != "OK" or parsed.value is None or parsed.value.is_equation:
        return None
    return parsed.value.sides[0]


def _last_numeric_answer(steps: list[dict[str, Any]]) -> tuple[str, sp.Expr] | None:
    for step in reversed(steps):
        # Last equality is intentionally used; prose is not interpreted.
        pieces = step["latex"].replace(".", "").split("=")
        if len(pieces) < 2:
            continue
        value = _expr(pieces[-1].strip())
        if value is not None and not value.free_symbols:
            return step["step_id"], value
    return None


def _last_expression_answer(steps: list[dict[str, Any]]) -> tuple[str, sp.Expr] | None:
    """Take only a written RHS, never infer a value from prose."""
    for step in reversed(steps):
        pieces = step["latex"].replace(".", "").split("=")
        if len(pieces) < 2:
            continue
        rhs = pieces[-1].strip().rstrip(",.")
        rhs = rhs.split(r"\quad", 1)[0].strip()
        rhs = re.split(r",\s*[A-Za-z]\s*\\(?:neq|ne)", rhs, maxsplit=1)[0].strip()
        value = _expr(rhs)
        if value is not None:
            return step["step_id"], value
    return None


def _matrix(raw: str) -> sp.MatrixBase | None:
    value = _expr(raw)
    return value if isinstance(value, sp.MatrixBase) else None


def determinant(spec: dict[str, Any]) -> ContextResult:
    raw = spec["task"]["raw_latex"] or ""
    match = re.search(r"\\begin\{vmatrix\}.*?\\end\{vmatrix\}", raw, re.S)
    if not match:
        return ContextResult("UNSUPPORTED", "determinant literal was not found", rule="determinant")
    expected = _expr(match[0])
    answer = _last_numeric_answer(spec["steps"])
    if expected is None or answer is None or expected.free_symbols:
        return ContextResult("UNSUPPORTED", "determinant or a final numeric equality is not exactly parseable", rule="determinant")
    step_id, actual = answer
    return ContextResult("VALID" if sp.simplify(expected - actual) == 0 else "INVALID",
                         "exact determinant evaluation" if sp.simplify(expected - actual) == 0 else "final numeric determinant value differs from exact SymPy determinant",
                         step_id, "determinant")


def matrix_system(spec: dict[str, Any]) -> ContextResult:
    raw = spec["task"]["raw_latex"] or ""
    matches = list(re.finditer(r"([XY])\s*([+-])\s*([XY])\s*=\s*(\\begin\{bmatrix\}.*?\\end\{bmatrix\})", raw, re.S))
    if len(matches) != 2:
        return ContextResult("UNSUPPORTED", "requires two explicit X/Y matrix equations", rule="matrix_system")
    equations: list[tuple[str, str, str, sp.MatrixBase]] = []
    for match in matches:
        matrix = _matrix(match[4])
        if matrix is None:
            return ContextResult("UNSUPPORTED", "matrix literal is not exactly parseable", rule="matrix_system")
        equations.append((match[1], match[2], match[3], matrix))
    # First contour deliberately supports the canonical X+Y=A, X-Y=B pair.
    plus = next((entry for entry in equations if entry[:3] == ("X", "+", "Y")), None)
    minus = next((entry for entry in equations if entry[:3] == ("X", "-", "Y")), None)
    if plus is None or minus is None or plus[3].shape != minus[3].shape:
        return ContextResult("UNSUPPORTED", "only compatible X+Y=A and X-Y=B systems are supported", rule="matrix_system")
    expected = {"X": (plus[3] + minus[3]) / 2, "Y": (plus[3] - minus[3]) / 2}
    seen: dict[str, tuple[str, sp.MatrixBase]] = {}
    for step in spec["steps"]:
        match = re.search(r"\b([XY])\s*=\s*(\\begin\{bmatrix\}.*?\\end\{bmatrix\})", step["latex"], re.S)
        if match:
            matrix = _matrix(match[2])
            if matrix is None:
                return ContextResult("UNSUPPORTED", "recorded matrix answer is not exactly parseable", step["step_id"], "matrix_system")
            seen[match[1]] = (step["step_id"], matrix)
    if set(seen) != {"X", "Y"}:
        return ContextResult("UNSUPPORTED", "both X and Y must be explicitly recorded", rule="matrix_system")
    for name in ("X", "Y"):
        step_id, actual = seen[name]
        if actual.shape != expected[name].shape or any(sp.simplify(a - b) != 0 for a, b in zip(actual, expected[name])):
            return ContextResult("INVALID", f"{name} does not satisfy the exact matrix system", step_id, "matrix_system")
    return ContextResult("VALID", "both matrices satisfy the two exact given equations", max(v[0] for v in seen.values()), "matrix_system")


def definite_integral(spec: dict[str, Any]) -> ContextResult:
    raw = spec["task"]["raw_latex"] or ""
    match = re.search(r"\\int_\{([^{}]+)\}\^\{([^{}]+)\}\s*(.*?)\\,?\s*d([A-Za-z])", raw)
    if not match:
        return ContextResult("UNSUPPORTED", "definite integral with explicit bounds was not found", rule="definite_integral")
    lower, upper, body, variable_name = match.groups()
    a, b, integrand = _expr(lower), _expr(upper), _expr(body)
    if a is None or b is None or integrand is None:
        return ContextResult("UNSUPPORTED", "integral bounds or integrand are not in the exact parser subset", rule="definite_integral")
    variables = [symbol for symbol in integrand.free_symbols if symbol.name == variable_name]
    if len(variables) != 1:
        return ContextResult("UNSUPPORTED", "integrand must contain exactly one integration variable", rule="definite_integral")
    variable = variables[0]
    try:
        expected = sp.integrate(integrand, (variable, a, b))
    except (TypeError, ValueError, NotImplementedError):
        return ContextResult("UNSUPPORTED", "SymPy could not integrate this definite integral exactly", rule="definite_integral")
    if expected.has(sp.Integral):
        return ContextResult("UNSUPPORTED", "SymPy returned an unevaluated integral", rule="definite_integral")
    answer = _last_numeric_answer(spec["steps"])
    if answer is None:
        return ContextResult("UNSUPPORTED", "final numeric integral value is absent or unreadable", rule="definite_integral")
    step_id, actual = answer
    return ContextResult("VALID" if sp.simplify(expected - actual) == 0 else "INVALID",
                         "exact definite integral evaluation" if sp.simplify(expected - actual) == 0 else "final value differs from exact definite integral",
                         step_id, "definite_integral")


def _relation_set(raw: str) -> tuple[sp.Set, sp.Symbol] | None:
    match = re.search(r"(\\leq|\\geq|\\le|\\ge|<=|>=|<|>)", raw)
    if not match:
        return None
    left, right = _expr(raw[:match.start()].strip()), _expr(raw[match.end():].strip())
    if left is None or right is None:
        return None
    variables = sorted((left - right).free_symbols, key=str)
    if len(variables) != 1:
        return None
    op = {"<": sp.Lt, ">": sp.Gt, "<=": sp.Le, ">=": sp.Ge, r"\le": sp.Le, r"\leq": sp.Le, r"\ge": sp.Ge, r"\geq": sp.Ge}[match[0]]
    try:
        result = sp.solve_univariate_inequality(op(left, right), variables[0], relational=False)
    except (TypeError, ValueError, NotImplementedError):
        return None
    return result, variables[0]


def _bound(raw: str) -> sp.Expr | None:
    value = raw.strip().replace("+\\infty", "\\infty").replace("-\\infty", "-\\infty")
    if value in {r"\infty", "∞"}:
        return sp.oo
    if value in {r"-\infty", "-∞"}:
        return -sp.oo
    return _expr(value)


def _interval_set(raw: str) -> sp.Set | None:
    # Accept textbook Russian/FERMAT notation (a; b], [a,b), and x∈ forms.
    clean = raw.replace(r"\left", "").replace(r"\right", "").replace(" ", "")
    match = re.search(r"([\[(])([^;,]+)[;,]([^\]\)]+)([\]\)])", clean)
    if not match:
        return None
    left, lower, upper, right = match.groups()
    a, b = _bound(lower), _bound(upper)
    if a is None or b is None:
        return None
    return sp.Interval(a, b, left == "(", right == ")")


def _answer_set(steps: list[dict[str, Any]], variable: sp.Symbol) -> tuple[str, sp.Set] | None:
    for step in reversed(steps):
        interval = _interval_set(step["latex"])
        if interval is not None:
            return step["step_id"], interval
        relation = _relation_set(step["latex"])
        if relation and relation[1] == variable:
            return step["step_id"], relation[0]
    return None


def inequality(spec: dict[str, Any]) -> ContextResult:
    givens = spec["task"]["givens"]
    raw = givens[0]["raw_latex"] if givens else (spec["task"]["raw_latex"] or "")
    expected = _relation_set(raw)
    if expected is None:
        return ContextResult("UNSUPPORTED", "inequality is outside the exact univariate parser subset", rule="inequality")
    expected_set, variable = expected
    candidate = _answer_set(spec["steps"], variable)
    if candidate is None:
        return ContextResult("UNSUPPORTED", "no exact inequality answer set in recorded steps", rule="inequality")
    step_id, actual = candidate
    equal = sp.SymmetricDifference(expected_set, actual).is_empty
    if equal is None:
        return ContextResult("UNSUPPORTED", "exact inequality-set comparison is inconclusive", step_id, "inequality")
    return ContextResult("VALID" if equal else "INVALID", "exact inequality solution-set comparison", step_id, "inequality")


def trigonometric(spec: dict[str, Any]) -> ContextResult:
    # Only certify a finite explicit set after exact interval restriction.
    # A frequent FERMAT family: known sin/cos values and quadrants, followed
    # by evaluation of sin(x+y). It is fully exact and needs no trig solver.
    if spec["task"].get("goal", {}).get("target_latex") == r"\sin(x+y)":
        values = {g["raw_latex"].replace(" ", ""): g["raw_latex"] for g in spec["task"]["givens"]}
        sx = next((_expr(g.split("=", 1)[1]) for g in values.values() if g.replace(" ", "").startswith(r"\sinx=")), None)
        cy = next((_expr(g.split("=", 1)[1]) for g in values.values() if g.replace(" ", "").startswith(r"\cosy=")), None)
        constraints = " ".join(item["raw_latex"].lower() for item in spec["task"]["constraints"])
        if sx is None or cy is None or "second quadrant" not in constraints:
            return ContextResult("UNSUPPORTED", "requires exact sin x, cos y and second-quadrant constraints", rule="trigonometric")
        cx = -sp.sqrt(1 - sx**2)
        sy = sp.sqrt(1 - cy**2)
        expected = sp.simplify(sx * cy + cx * sy)
        answer = _last_numeric_answer(spec["steps"])
        if answer is None:
            return ContextResult("UNSUPPORTED", "final trig value is absent or unreadable", rule="trigonometric")
        step_id, actual = answer
        return ContextResult("VALID" if sp.simplify(expected - actual) == 0 else "INVALID", "exact quadrant-aware sine-addition evaluation" if sp.simplify(expected - actual) == 0 else "final value contradicts exact quadrant-aware sine-addition evaluation", step_id, "trigonometric")
    # If the written solution has already established explicit periodic
    # families, verify its *interval selection* exactly. This deliberately
    # does not pretend to prove the preceding trig transformation.
    interval = next((_interval_set(item["raw_latex"]) for item in spec["task"]["constraints"] + spec["task"]["givens"] if _interval_set(item["raw_latex"]) is not None), None)
    families: list[tuple[sp.Expr, sp.Expr]] = []
    for step in spec["steps"]:
        text = step["latex"]
        for match in re.finditer(r"x\s*=\s*(.*?)\s*\+\s*(2?\\pi)\s*[knl]", text):
            base, period = _expr(match[1].strip()), _expr(match[2])
            if base is not None and period is not None:
                families.append((base, period))
        if re.search(r"x\s*=\s*\\pi\s*[knl]", text):
            families.append((sp.Integer(0), sp.pi))
    if interval is not None and families:
        expected_values = set()
        for base, period in families:
            for integer in range(-20, 21):
                value = sp.simplify(base + period * integer)
                if sp.simplify(interval.contains(value)) is sp.S.true:
                    expected_values.add(value)
        # The finite part is conventionally after «б)» or the last answer
        # branch. We parse only semicolon-separated pure LaTex values.
        final = spec["steps"][-1]
        marker = re.search(r"\\text\{б\)\s*\}\s*(.*)$", final["latex"])
        fragment = marker[1] if marker else final["latex"]
        fragment = re.sub(r"\\text\{[^{}]*\}", "", fragment).replace("x=", "")
        actual_values = set()
        for piece in re.split(r"[;,]", fragment):
            value = _expr(piece.strip().rstrip("."))
            if value is not None and not value.free_symbols:
                actual_values.add(sp.simplify(value))
        if expected_values and actual_values:
            return ContextResult("VALID" if actual_values == expected_values else "INVALID",
                                 "exact periodic-family intersection with the stated interval" if actual_values == expected_values else "selected finite trig roots differ from the exact intersection of written families and interval",
                                 final["step_id"], "trigonometric_family")
    given = next((g["raw_latex"] for g in spec["task"]["givens"] if "=" in g["raw_latex"]), None)
    if not given:
        return ContextResult("UNSUPPORTED", "trigonometric equation was not extracted", rule="trigonometric")
    parsed = parse_latex(given)
    if parsed.status != "OK" or not parsed.value or not parsed.value.is_equation:
        return ContextResult("UNSUPPORTED", "trigonometric equation is outside exact parser subset", rule="trigonometric")
    variables = parsed.value.symbols
    if len(variables) != 1:
        return ContextResult("UNSUPPORTED", "requires one trigonometric variable", rule="trigonometric")
    variable = variables[0]
    interval = None
    for constraint in [item["raw_latex"] for item in spec["task"]["constraints"]] + [item["raw_latex"] for item in spec["task"]["givens"]]:
        match = re.search(r"x\s*\\in\s*\\left([\[\(])\s*([^;,]+)\s*[;,]\s*([^\]\)]+)\\right([\]\)])", constraint)
        if match:
            left, lower, upper, right = match.groups()
            a, b = _expr(lower.strip()), _expr(upper.strip())
            if a is not None and b is not None:
                interval = sp.Interval(a, b, left == "(", right == ")")
                break
    if interval is None:
        return ContextResult("UNSUPPORTED", "finite interval for trig root selection is absent or unreadable", rule="trigonometric")
    try:
        expected = sp.solveset(parsed.value.sides[0] - parsed.value.sides[1], variable, domain=interval)
    except (TypeError, ValueError, NotImplementedError):
        return ContextResult("UNSUPPORTED", "SymPy could not solve the trigonometric equation exactly", rule="trigonometric")
    if not isinstance(expected, sp.FiniteSet):
        return ContextResult("UNSUPPORTED", "exact trigonometric root set is not finite", rule="trigonometric")
    candidates: list[tuple[str, sp.Expr]] = []
    for step in spec["steps"]:
        for match in re.finditer(r"x\s*=\s*([^,;]+)", step["latex"]):
            value = _expr(match[1])
            if value is not None:
                if value.free_symbols:
                    return ContextResult("UNSUPPORTED", "parametric trig families require an exact family parser", step["step_id"], "trigonometric")
                candidates.append((step["step_id"], value))
    if not candidates:
        return ContextResult("UNSUPPORTED", "no finite explicit x=c answer candidates", rule="trigonometric")
    actual = sp.FiniteSet(*(value for _, value in candidates))
    step_id = candidates[-1][0]
    return ContextResult("VALID" if actual == expected else "INVALID",
                         "exact trigonometric roots selected on the stated interval" if actual == expected else "trigonometric root set differs from the exact interval-restricted set",
                         step_id, "trigonometric")


def scalar_task(spec: dict[str, Any]) -> ContextResult:
    """Exact evaluation/simplification when a target is machine-readable."""
    target = spec["task"]["goal"].get("target_latex")
    raw = spec["task"]["raw_latex"] or ""
    if not target:
        divide = re.search(r"Divide \}\s*(.*?)\s*\\text\{ by \}\s*(.*?)(?:\.|$)", raw)
        value = re.search(r"(?:Find the value of|Find the cube root of) \}\s*(.*?)(?:\.|$)", raw)
        if divide:
            target = f"({divide[1]}) \\div ({divide[2]})"
        elif value:
            target = value[1]
    if not target:
        return ContextResult("UNSUPPORTED", "task has no explicit mathematical target", rule="scalar_task")
    # Substitute only explicit scalar givens such as n=5; no prose inference.
    substitutions: dict[sp.Symbol, sp.Expr] = {}
    for given in spec["task"]["givens"]:
        match = re.fullmatch(r"\s*([A-Za-z])\s*=\s*(.+?)\s*", given["raw_latex"])
        if match:
            value = _expr(match[2])
            if value is not None and not value.free_symbols:
                substitutions[sp.Symbol(match[1], real=True)] = value
    rendered = target
    for symbol, value in substitutions.items():
        rendered = re.sub(rf"(?<![A-Za-z]){re.escape(symbol.name)}(?![A-Za-z])", sp.latex(value), rendered)
    expected = _expr(rendered)
    answer = _last_expression_answer(spec["steps"])
    if expected is None or answer is None:
        return ContextResult("UNSUPPORTED", "target or recorded answer is not exactly parseable", rule="scalar_task")
    step_id, actual = answer
    if expected.free_symbols or actual.free_symbols:
        return ContextResult("UNSUPPORTED", "scalar task still contains free symbols", step_id, "scalar_task")
    return ContextResult("VALID" if sp.simplify(expected - actual) == 0 else "INVALID",
                         "exact task evaluation" if sp.simplify(expected - actual) == 0 else "recorded final value differs from exact task value", step_id, "scalar_task")


def function_operation(spec: dict[str, Any]) -> ContextResult:
    givens = {item["raw_latex"].strip()[0]: item["raw_latex"].split("=", 1)[1].strip() for item in spec["task"]["givens"] if re.match(r"^[fg]\(x\)\s*=", item["raw_latex"].strip())}
    if set(givens) != {"f", "g"}:
        return ContextResult("UNSUPPORTED", "requires explicit f(x) and g(x) definitions", rule="function_operation")
    f, g = _expr(givens["f"]), _expr(givens["g"])
    if f is None or g is None:
        return ContextResult("UNSUPPORTED", "function definitions are not exactly parseable", rule="function_operation")
    x = next(iter((f.free_symbols | g.free_symbols)), None)
    if x is None:
        return ContextResult("UNSUPPORTED", "function variable is absent", rule="function_operation")
    expected_by_marker = [("f+g", f + g), ("f-g", f - g), ("fg", f * g), ("frac", sp.cancel(f / g))]
    checked = 0
    last_step = None
    for step in spec["steps"]:
        text = step["latex"].replace(" ", "")
        marker = "frac" if r"\frac{f}{g}" in text else next((name for name, _ in expected_by_marker[:3] if f"({name})" in text), None)
        if marker is None:
            continue
        actual_data = _last_expression_answer([step])
        expected = dict(expected_by_marker)[marker]
        if actual_data is None:
            return ContextResult("UNSUPPORTED", "function answer is not exactly parseable", step["step_id"], "function_operation")
        step_id, actual = actual_data
        # The writer may call the independent variable t; compare polynomial
        # shapes after replacing its sole free symbol with x.
        if len(actual.free_symbols) == 1:
            actual = actual.subs(next(iter(actual.free_symbols)), x)
        if actual.free_symbols - {x} or sp.simplify(actual - expected) != 0:
            return ContextResult("INVALID", f"{marker} result differs from exact function operation", step_id, "function_operation")
        checked += 1
        last_step = step_id
    if checked != 4:
        return ContextResult("UNSUPPORTED", "not all four requested function operations are explicitly recorded", last_step, "function_operation")
    return ContextResult("VALID", "all requested function operations match exact definitions", last_step, "function_operation")


RULES = {"determinant": determinant, "matrix_system": matrix_system, "definite_integral": definite_integral,
         "inequality": inequality, "trigonometric": trigonometric, "function_operation": function_operation,
         "expression": scalar_task}


def check_context(spec: dict[str, Any]) -> ContextResult:
    if spec["compilation"]["status"] == "unsupported":
        return ContextResult("UNSUPPORTED", "; ".join(spec["compilation"]["reasons"]), rule="task_spec")
    task_class = spec["compilation"]["task_class"]
    raw = spec["task"]["raw_latex"] or ""
    if task_class == "trigonometric" or (task_class == "equation" and any(token in raw for token in (r"\sin", r"\cos", r"\tan"))):
        return trigonometric(spec)
    if task_class == "equation" and spec["task"]["goal"].get("type") in {"evaluate", "simplify"}:
        return scalar_task(spec)
    rule = RULES.get(task_class)
    return rule(spec) if rule else ContextResult("UNSUPPORTED", f"no context rule for {task_class}", rule=task_class)
