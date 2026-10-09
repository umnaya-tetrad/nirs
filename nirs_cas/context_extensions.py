"""Exact assisted checks of full answer sets and computational conditions."""

from __future__ import annotations
import re
import sympy as sp
from .assisted_rules import (
    inequality_set,
    task_roots,
    answer_candidate,
    rhs_chain,
    function_answers,
    constraint_domain,
)
from .environment import exact_scalar
from .exact_math import math, equal_sets, domain
from .parser import ParseError


def givens(spec):
    return [g["raw_latex"] for g in spec["task"].get("givens", [])]


def constraints(spec):
    return [c["raw_latex"] for c in spec["task"].get("constraints", [])]


def matrix_bindings(raws):
    equations = {}
    for raw in raws:
        m = re.fullmatch(r"\s*X\s*([+-])\s*Y\s*=\s*(.+)", raw, re.S)
        if not m:
            raise ParseError("Requires explicit X+Y and X-Y matrix givens")
        value = math(m[2]).sides[0]
        if not isinstance(value, sp.MatrixBase) or value.free_symbols:
            raise ParseError("Expected constant matrix literal")
        equations[m[1]] = value
    if set(equations) != {"+", "-"} or equations["+"].shape != equations["-"].shape:
        raise ParseError("Matrix givens must have matching dimensions")
    a, b = equations["+"], equations["-"]
    return {
        sp.Symbol("X", real=True): (a + b) / 2,
        sp.Symbol("Y", real=True): (a - b) / 2,
    }


def answer(steps):
    candidates = [s for s in steps if s.get("role") == "answer"] or steps[-1:]
    if not candidates:
        raise ParseError("No written answer")
    last = candidates[-1]
    return last["step_id"], rhs_chain(last["latex"])[-1]


def value_result(expected, actual, step_id, rule):
    from .context_rules import ContextResult

    diff = sp.simplify(expected - actual)
    truth = diff.is_zero
    if truth is None and diff.is_rational_function() and diff != 0:
        truth = False
    return ContextResult(
        "VALID" if truth is True else ("INVALID" if truth is False else "UNSUPPORTED"),
        "Exact value comparison"
        if truth is not None
        else "Symbolic comparison is unresolved",
        step_id,
        rule,
    )


def inequality(spec):
    from .context_rules import ContextResult

    raw = next(
        (
            g
            for g in givens(spec)
            if re.search(r"\\(?:geq|leq|ge|le)(?![A-Za-z])|[<>]", g)
        ),
        spec["task"].get("raw_latex") or "",
    )
    expected, x = inequality_set(raw, constraints(spec))
    step_id, actual = answer_candidate(spec["steps"], x)
    equal = equal_sets(expected, actual)
    return ContextResult(
        "VALID" if equal is True else ("INVALID" if equal is False else "UNSUPPORTED"),
        "Exact complete inequality solution-set comparison",
        step_id,
        "inequality",
    )


def equation(spec):
    from .context_rules import ContextResult

    raw = next(
        (g for g in givens(spec) if "=" in g), spec["task"].get("raw_latex") or ""
    )
    expected, x = task_roots(raw, constraints(spec))
    step_id, actual = answer_candidate(spec["steps"], x)
    equal = equal_sets(expected, actual)
    return ContextResult(
        "VALID" if equal is True else ("INVALID" if equal is False else "UNSUPPORTED"),
        "Exact complete equation root-set comparison",
        step_id,
        "equation",
    )


def trigonometric(spec):
    from .context_rules import ContextResult

    if spec["task"].get("goal", {}).get("type") == "evaluate":
        return scalar_task(spec)
    raw = next(
        (g for g in givens(spec) if "=" in g), spec["task"].get("raw_latex") or ""
    )
    restrictions = constraints(spec) + [g for g in givens(spec) if r"\in" in g]
    expected, x = task_roots(raw, restrictions)
    step_id, actual = answer_candidate(spec["steps"], x)
    equal = equal_sets(expected, actual)
    return ContextResult(
        "VALID" if equal is True else ("INVALID" if equal is False else "UNSUPPORTED"),
        "Exact complete canonical trig root-set comparison",
        step_id,
        "trigonometric",
    )


def scalar_task(spec):
    from .context_rules import ContextResult

    target = spec["task"].get("goal", {}).get("target_latex")
    if not target:
        raise ParseError("Task has no explicit mathematical target")
    step_id, actual = answer(spec["steps"])
    target_parsed = math(target)
    if (
        spec["task"].get("goal", {}).get("type") == "simplify"
        and len(target_parsed.symbols) == 1
    ):
        x = target_parsed.symbols[0]
        allowed = constraint_domain(constraints(spec), x)
        equal = equal_sets(
            sp.Intersection(domain(target_parsed, x), allowed),
            sp.Intersection(domain(math(sp.latex(actual)), x), allowed),
        )
        if equal is not True:
            return ContextResult(
                "INVALID" if equal is False else "UNSUPPORTED",
                "Simplification changes expression domain",
                step_id,
                "scalar_task",
            )
    try:
        expected = exact_scalar(target, givens(spec), constraints(spec))
    except ParseError:
        parsed = math(target)
        if (
            parsed.is_equation
            or not parsed.symbols
            or spec["task"].get("goal", {}).get("type") != "simplify"
        ):
            raise
        if len(parsed.symbols) > 1:
            raise ParseError("Multivariate simplification domain is unsupported")
        x = parsed.symbols[0]
        allowed = constraint_domain(constraints(spec), x)
        equal = equal_sets(
            sp.Intersection(domain(parsed, x), allowed),
            sp.Intersection(domain(math(sp.latex(actual)), x), allowed),
        )
        if equal is not True:
            return ContextResult(
                "INVALID" if equal is False else "UNSUPPORTED",
                "Simplification changes expression domain",
                step_id,
                "scalar_task",
            )
        expected = parsed.sides[0]
    if actual.free_symbols and not expected.free_symbols:
        raise ParseError("Final scalar answer has unresolved variables")
    if actual.free_symbols - expected.free_symbols:
        raise ParseError("Final scalar answer has unbound parameters")
    return value_result(expected, actual, step_id, "scalar_task")


def function_operation(spec):
    from .context_rules import ContextResult

    checks = function_answers(givens(spec), spec["steps"])
    bad = next((c for c in checks if c[1] != "VALID"), checks[-1])
    return ContextResult(bad[1], bad[2], bad[0], "function_operation")


def check_context(spec):
    from .context_rules import (
        ContextResult,
        determinant,
        matrix_system,
        definite_integral,
    )

    if spec["compilation"]["status"] != "supported":
        return ContextResult(
            "UNSUPPORTED", "; ".join(spec["compilation"]["reasons"]), rule="task_spec"
        )
    task_class = spec["compilation"]["task_class"]
    rules = {
        "determinant": determinant,
        "matrix_system": matrix_system,
        "definite_integral": definite_integral,
        "inequality": inequality,
        "trigonometric": trigonometric,
        "equation": equation,
        "expression": scalar_task,
        "function_operation": function_operation,
    }
    rule = rules.get(task_class)
    if task_class == "equation" and spec["task"].get("goal", {}).get("type") in (
        "evaluate",
        "simplify",
    ):
        rule = scalar_task
    if rule is None:
        return ContextResult("UNSUPPORTED", "No exact class rule", rule=task_class)
    try:
        return rule(spec)
    except (
        ValueError,
        TypeError,
        NotImplementedError,
        RecursionError,
        ZeroDivisionError,
    ) as exc:
        return ContextResult(
            "UNSUPPORTED",
            str(exc),
            spec["steps"][-1]["step_id"] if spec["steps"] else None,
            task_class,
        )
