"""Conservative feasibility verifier. Not a general proof checker.

Each step must preserve the real solution set (equations) or value AND domain
(expressions). The first symbolic equation is a trusted premise. Conditional
reasoning, systems, inequalities and changes of step kind are unsupported.
"""
from dataclasses import dataclass, asdict
from typing import Literal

import sympy as sp
from .parser import ParsedMath, parse_latex


@dataclass(frozen=True)
class StepResult:
    status: Literal["VALID", "INVALID", "UNSUPPORTED"]
    reason: str
    parse_status: str = "OK"

    def to_dict(self):
        return asdict(self)


class Unsupported(ValueError):
    pass


def _domain(parsed: ParsedMath, variable: sp.Symbol) -> sp.Set:
    domain = sp.S.Reals
    for kind, expr in parsed.constraints:
        if kind == "nonzero":
            excluded = sp.solveset(expr, variable, domain=sp.S.Reals)
            constraint = sp.Complement(sp.S.Reals, excluded)
        elif kind == "positive":
            constraint = sp.solve_univariate_inequality(expr > 0, variable, relational=False)
        else:
            constraint = sp.solve_univariate_inequality(expr >= 0, variable, relational=False)
        if constraint.has(sp.ConditionSet):
            raise Unsupported("Domain could not be resolved exactly")
        domain = sp.Intersection(domain, constraint)
    if domain.has(sp.ConditionSet):
        raise Unsupported("Domain could not be resolved exactly")
    return domain


def _set_equal(left: sp.Set, right: sp.Set) -> bool | None:
    if left.has(sp.ConditionSet) or right.has(sp.ConditionSet):
        return None
    if left == right:
        return True
    difference = sp.SymmetricDifference(left, right)
    return difference.is_empty


def _constant_truth(parsed: ParsedMath) -> bool | None:
    difference = sp.simplify(parsed.sides[0] - parsed.sides[1])
    return difference.is_zero


def _compare(left: ParsedMath, right: ParsedMath) -> StepResult:
    if left.is_equation != right.is_equation:
        raise Unsupported("Expression/equation conversion needs task context")
    variables = sorted(set(left.symbols) | set(right.symbols), key=str)
    if len(variables) > 1:
        # Multivariate domain equivalence is outside this feasibility verifier.
        if any(expr.free_symbols for _, expr in left.constraints + right.constraints):
            raise Unsupported("Multivariate domain restrictions")
        values = left.sides + right.sides
        if not all(v.is_polynomial(*variables) for v in values):
            raise Unsupported("Nonpolynomial multivariate transition")
        if left.is_equation:
            a = sp.expand(left.sides[0] - left.sides[1])
            b = sp.expand(right.sides[0] - right.sides[1])
            if a == b:
                return StepResult("VALID", "Identical polynomial equations")
            if a != 0:
                ratio = sp.cancel(b / a)
                if not ratio.free_symbols and ratio.is_nonzero is True:
                    return StepResult("VALID", "Equations differ by a nonzero constant factor")
            raise Unsupported("Multivariate solution-set equivalence not established")
        difference = sp.Poly(sp.expand(left.sides[0] - right.sides[0]), *variables)
        return StepResult("VALID" if difference.is_zero else "INVALID", "Polynomial identity test")

    if left.is_equation:
        if not variables:
            a, b = _constant_truth(left), _constant_truth(right)
            equal = None if a is None or b is None else a == b
        else:
            variable = variables[0]
            a = sp.solveset(left.sides[0] - left.sides[1], variable, domain=_domain(left, variable))
            b = sp.solveset(right.sides[0] - right.sides[1], variable, domain=_domain(right, variable))
            equal = _set_equal(a, b)
        reason = "Exact real solution-set comparison"
    else:
        if variables:
            a = _domain(left, variables[0])
            b = _domain(right, variables[0])
            same_domain = _set_equal(a, b)
            if same_domain is not True:
                if same_domain is False:
                    return StepResult("INVALID", "Expression domains differ")
                raise Unsupported("Expression domain equivalence unresolved")
            if a.is_empty is True:
                raise Unsupported("Empty expression domain")
        difference = sp.simplify(left.sides[0] - right.sides[0])
        if difference == 0 or difference.is_zero is True:
            equal = True
        elif not variables:
            equal = difference.is_zero
        elif (a.is_FiniteSet is not True
              and all(v.is_rational_function(*variables) for v in left.sides + right.sides)):
            equal = sp.cancel(difference) == 0
        else:
            # No verdict from numerical sampling or a failed symbolic simplification.
            equal = None
        reason = "Exact expression identity with preserved domain"
    if equal is None:
        raise Unsupported("Symbolic result is inconclusive")
    return StepResult("VALID" if equal else "INVALID", reason)


def verify_step(step_i: str, step_next: str) -> StepResult:
    left, right = parse_latex(step_i), parse_latex(step_next)
    if left.status != "OK" or right.status != "OK":
        reasons = [p.reason for p in (left, right) if p.status != "OK"]
        return StepResult("UNSUPPORTED", "; ".join(reasons), "PARSE_FAILED")
    try:
        return _compare(left.value, right.value)
    except (Unsupported, NotImplementedError, ValueError, TypeError, RecursionError, ZeroDivisionError) as exc:
        return StepResult("UNSUPPORTED", str(exc))


def verify_solution(steps: list[str]) -> dict:
    """One-based destination step indexes. Unknown earlier steps block localization.

This evaluates a sequence of transformations, not correctness against orig_q.
All transitions must be supported for full coverage, even after a known error.
"""
    if not isinstance(steps, list) or any(not isinstance(step, str) or not step.strip() for step in steps):
        raise ValueError("Steps must be a list of nonempty LaTeX strings")
    if len(steps) == 1 or any(step.strip().startswith("=") or step.count("=") > 1
                              or any(marker in step for marker in (r"\begin", r"\text", r"\le", r"\ge", r"\tag", ";", ",", "<", ">")) for step in steps):
        from .structured import verify_written_solution
        return verify_written_solution(steps)
    parsed = [parse_latex(step) for step in steps]
    transitions = [dict(step=i + 2, **verify_step(a, b).to_dict())
                   for i, (a, b) in enumerate(zip(steps, steps[1:]))]
    errors = [t["step"] for t in transitions if t["status"] == "INVALID"]
    unknown = [t["step"] for t in transitions if t["status"] == "UNSUPPORTED"]
    unknown += [i for i, p in enumerate(parsed, 1) if p.status != "OK"]
    # A false constant equation is independently demonstrable, including step 1.
    for i, result in enumerate(parsed, 1):
        if result.value and result.value.is_equation and not result.value.symbols:
            if _constant_truth(result.value) is False:
                errors.append(i)
    first = min(errors) if errors else None
    localized = first if first and not any(i < first for i in unknown) else None
    covered = len(steps) >= 2 and all(p.status == "OK" for p in parsed) and not unknown
    status = ("INVALID" if errors else "VALID") if covered else "UNSUPPORTED"
    return {
        "status": status,
        "covered": covered,
        "has_error": True if errors else (False if covered else None),
        "first_error_step": localized,
        "parse_status": "OK" if parsed and all(p.status == "OK" for p in parsed) else "PARSE_FAILED",
        "parsed_steps": sum(p.status == "OK" for p in parsed),
        "total_steps": len(parsed),
        "transitions": transitions,
        "reason": "First symbolic step is a trusted premise; no check against the problem statement",
    }
