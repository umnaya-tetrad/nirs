"""Exact bindings from explicit mathematical fields, never prose."""

import sympy as sp
from .exact_math import math, relation_set
from .parser import ParseError


def equal_values(left, right):
    if isinstance(left, sp.MatrixBase) or isinstance(right, sp.MatrixBase):
        if not isinstance(left, sp.MatrixBase) or not isinstance(right, sp.MatrixBase):
            return None
        if left.shape != right.shape:
            return False
        return sp.simplify(left - right).is_zero_matrix
    return sp.simplify(left - right).is_zero


def bindings(givens):
    result = {}
    for raw in givens:
        try:
            parsed = math(raw)
        except (ValueError, TypeError):
            continue
        if parsed.is_equation:
            left, right = parsed.sides
            if isinstance(left, sp.Symbol) and not right.free_symbols:
                value = sp.simplify(right)
                if not isinstance(value, sp.MatrixBase) and value.is_real is not True:
                    raise ParseError("Binding must have a resolved real value")
                if left in result and equal_values(result[left], value) is not True:
                    raise ParseError("Conflicting explicit bindings")
                result[left] = value
            elif left.func in (sp.sin, sp.cos) and not right.free_symbols:
                value = sp.simplify(right)
                if (1 - value**2).is_nonnegative is not True:
                    raise ParseError("Trig binding is outside [-1,1]")
                if left in result and sp.simplify(result[left] - value) != 0:
                    raise ParseError("Conflicting trig bindings")
                result[left] = value
    return result


def substitute(parsed, environment):
    for kind, expr in parsed.constraints:
        value = sp.simplify(expr.subs(environment, simultaneous=True))
        if not value.free_symbols:
            truth = {
                "nonzero": value.is_nonzero,
                "positive": value.is_positive,
                "nonnegative": value.is_nonnegative,
            }[kind]
            if truth is not True:
                raise ParseError("Substitution violates the expression domain")
    values = []
    for expr in parsed.sides:
        # Validate innermost symbolic factorials before subs() can evaluate
        # them. This also bounds nested factorials and very large bindings.
        for factorial in sorted(expr.atoms(sp.factorial), key=sp.count_ops):
            argument = sp.simplify(
                factorial.args[0].subs(environment, simultaneous=True)
            )
            if (
                argument.free_symbols
                or argument.is_Integer is not True
                or not 0 <= argument <= 100
            ):
                raise ParseError(
                    "Factorial substitution needs a bounded nonnegative integer"
                )
        value = sp.expand_trig(expr).subs(environment, simultaneous=True)
        for factorial in value.atoms(sp.factorial):
            argument = sp.simplify(factorial.args[0])
            if (
                argument.free_symbols
                or argument.is_Integer is not True
                or not 0 <= argument <= 100
            ):
                raise ParseError(
                    "Factorial substitution needs a bounded nonnegative integer"
                )
        value = sp.simplify(value.doit())
        if value.has(sp.nan, sp.zoo, sp.oo, -sp.oo):
            raise ParseError("Undefined substituted value")
        values.append(value)
    return values


def trig_environment(givens, constraints):
    result = bindings(givens)
    for term, value in list(result.items()):
        if term.func not in (sp.sin, sp.cos):
            continue
        argument = term.args[0]
        if not isinstance(argument, sp.Symbol):
            continue
        allowed = sp.S.Reals
        for raw in constraints:
            if r"\text" in raw:
                raise ParseError(
                    "Quadrant prose is not an explicit mathematical constraint"
                )
            from .answers import parse_answer

            if raw.strip().startswith(argument.name):
                answer = parse_answer(raw, argument)
                if answer.value is None:
                    raise ParseError(answer.reason)
                allowed = sp.Intersection(allowed, answer.value)
            else:
                try:
                    solution, variable = relation_set(raw)
                except (ValueError, TypeError, NotImplementedError):
                    continue
                if variable == argument:
                    allowed = sp.Intersection(allowed, solution)
        if allowed == sp.S.EmptySet:
            raise ParseError("Contradictory angle constraints")
        sign_sin = sign_cos = None
        for q, quadrant in enumerate(
            (
                sp.Interval.open(0, sp.pi / 2),
                sp.Interval.open(sp.pi / 2, sp.pi),
                sp.Interval.open(sp.pi, 3 * sp.pi / 2),
                sp.Interval.open(3 * sp.pi / 2, 2 * sp.pi),
            )
        ):
            if sp.Complement(allowed, quadrant).is_empty is True:
                sign_sin = 1 if q < 2 else -1
                sign_cos = 1 if q in (0, 3) else -1
                break
        if sign_sin is None:
            raise ParseError(
                "Angle sign is not proved by a structured quadrant interval"
            )
        own_sign = sign_sin if term.func == sp.sin else sign_cos
        if (value * own_sign).is_positive is not True:
            raise ParseError("Given trig value contradicts its quadrant")
        other = sp.cos(argument) if term.func == sp.sin else sp.sin(argument)
        expected = (sign_cos if term.func == sp.sin else sign_sin) * sp.sqrt(
            1 - value**2
        )
        if other in result and sp.simplify(result[other] - expected) != 0:
            raise ParseError("Inconsistent sin/cos bindings")
        result[other] = expected
    return result


def exact_scalar(target, givens, constraints=()):
    env = (
        trig_environment(givens, constraints)
        if any(r"\sin" in g or r"\cos" in g for g in givens)
        else bindings(givens)
    )
    parsed = math(target)
    values = substitute(parsed, env)
    if len(values) != 1 or values[0].free_symbols:
        raise ParseError("Task target has unresolved variables")
    return values[0]
