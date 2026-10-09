"""Exact class rules for answers, domains and assisted graph edges."""

from __future__ import annotations
import re
import sympy as sp

from .answers import parse_answer, split_parts
from .exact_math import (
    math,
    domain,
    resolved,
    equal_sets,
    finite_restriction,
    RELATION,
    OPS,
)
from .parser import ParseError


def constraint_domain(raws, variable):
    result = sp.S.Reals
    for raw in raws:
        answer = parse_answer(raw, variable)
        if answer.value is None:
            raise ParseError("Unsupported explicit constraint: " + str(answer.reason))
        # Do not apply restrictions of another variable to this task.
        match = re.match(r"\s*([A-Za-z])", raw)
        if match and match[1] != variable.name:
            raise ParseError("Constraint references another variable")
        result = resolved(sp.Intersection(result, answer.value))
    return result


def _inequality_parts(raw):
    matches = list(RELATION.finditer(raw))
    if len(matches) != 1 or matches[0][0] in ("=", "!=", r"\neq", r"\ne"):
        raise ParseError("Requires one explicit inequality")
    m = matches[0]
    a, b = math(raw[: m.start()]), math(raw[m.end() :])
    if a.is_equation or b.is_equation:
        raise ParseError("Unexpected equation side")
    variables = set(a.symbols + b.symbols)
    if len(variables) != 1:
        raise ParseError("Requires one real variable")
    variable = next(iter(variables))
    allowed = resolved(sp.Intersection(domain(a, variable), domain(b, variable)))
    return sp.expand(a.sides[0] - b.sides[0]), OPS[m[0]], variable, allowed


def inequality_set(raw, constraints=()):
    expr, op, x, allowed = _inequality_parts(raw)
    allowed = resolved(sp.Intersection(allowed, constraint_domain(constraints, x)))
    logs = expr.atoms(sp.log)
    if logs:
        # A common exact logarithm scale: sum c_i ln(A_i) + C. All A_i
        # are positive on the source domain, so exponentiation is reversible.
        terms, constant = [], expr
        variable_logs = [log for log in logs if log.free_symbols]
        for log in variable_logs:
            coefficient = sp.simplify(expr.coeff(log))
            if coefficient == 0 or coefficient.free_symbols:
                raise ParseError("Nonlinear logarithmic inequality")
            terms.append((coefficient, log.args[0]))
            constant -= coefficient * log
        constant = sp.simplify(constant)
        if not terms or constant.free_symbols:
            raise ParseError("Unsupported logarithm combination")
        scale = terms[0][0]
        if scale.is_positive is not True and scale.is_negative is not True:
            raise ParseError("Logarithm monotonicity is unresolved")
        ratios = [sp.simplify(c / scale) for c, _ in terms]
        if not all(r.is_Rational for r in ratios):
            raise ParseError("Logarithms do not have a common exact rational scale")
        multiple = sp.ilcm(*[r.q for r in ratios], 1)
        product = sp.S.One
        for (_, argument), ratio in zip(terms, ratios):
            power = ratio * multiple
            if abs(power) > 12:
                raise ParseError("Logarithm power exceeds budget")
            product *= argument**power
        threshold = sp.simplify(sp.exp(-constant * multiple / scale))
        if threshold.free_symbols:
            raise ParseError("Logarithm threshold is unresolved")
        if scale.is_negative:
            op = {sp.Lt: sp.Gt, sp.Le: sp.Ge, sp.Gt: sp.Lt, sp.Ge: sp.Le}[op]
        expr = sp.cancel(product) - threshold
    powers = [p for p in expr.atoms(sp.Pow) if p.exp.has(x) and not p.base.has(x)]
    if powers:
        # Reduce a^x (including compatible bases) to a positive t, solve the
        # rational inequality exactly, then invert a strictly monotone map.
        base = powers[0].base
        if base.is_positive is not True or (base - 1).is_zero is not False:
            raise ParseError("Exponential base is unresolved")
        t = sp.Symbol("CAS_t", positive=True)
        replacements = {}
        for p in powers:
            exponent = sp.expand(p.exp * sp.log(p.base) / sp.log(base))
            a = sp.simplify(exponent.coeff(x))
            b = sp.simplify(exponent.subs(x, 0))
            if (
                not a.is_Integer
                or abs(a) > 12
                or b.free_symbols
                or sp.simplify(exponent - a * x - b) != 0
            ):
                raise ParseError(
                    "Exponential powers are not a bounded affine common-base family"
                )
            replacements[p] = base**b * t**a
        transformed = sp.cancel(expr.xreplace(replacements))
        if transformed.has(x) or not transformed.is_rational_function(t):
            raise ParseError(
                "Exponential substitution did not yield a rational inequality"
            )
        tset = resolved(
            sp.Intersection(
                sp.solve_univariate_inequality(op(transformed, 0), t, relational=False),
                sp.Interval.open(0, sp.oo),
            )
        )

        # Recover poles of the original source before simplification as well.
        def inverse(value):
            if value == 0:
                return -sp.oo if (base - 1).is_positive else sp.oo
            if value == sp.oo:
                return sp.oo if (base - 1).is_positive else -sp.oo
            return sp.simplify(sp.log(value) / sp.log(base))

        def invert(value):
            if value == sp.S.EmptySet:
                return value
            if isinstance(value, sp.Union):
                return sp.Union(*(invert(part) for part in value.args))
            if isinstance(value, sp.FiniteSet):
                return sp.FiniteSet(*(inverse(p) for p in value))
            if isinstance(value, sp.Interval):
                a, b = inverse(value.start), inverse(value.end)
                return (
                    sp.Interval(a, b, value.left_open, value.right_open)
                    if (base - 1).is_positive
                    else sp.Interval(b, a, value.right_open, value.left_open)
                )
            raise ParseError(
                "Exponential solution set is not explicit intervals/points"
            )

        solution = invert(tset)
    else:
        if not expr.is_rational_function(x):
            raise ParseError(
                "Only rational, monotone exponential and common-scale logarithmic inequalities are supported"
            )
        solution = sp.solve_univariate_inequality(op(expr, 0), x, relational=False)
    return resolved(sp.Intersection(solution, allowed)), x


def trig_solutions(raw, interval=None):
    parsed = math(raw)
    if not parsed.is_equation or len(parsed.symbols) != 1:
        raise ParseError("Requires one real trigonometric equation")
    x = parsed.symbols[0]
    residual = sp.trigsimp(parsed.sides[0] - parsed.sides[1])
    if not residual.free_symbols:
        if residual.is_zero is None:
            raise ParseError("Constant trigonometric residual is unresolved")
        result = sp.S.Reals if residual.is_zero else sp.S.EmptySet
        return (sp.Intersection(result, interval) if interval is not None else result), x
    # A bounded polynomial in one sin/cos of an affine argument. No finite
    # root sampling: solve every polynomial root, then construct full families.
    atoms = list(residual.atoms(sp.sin, sp.cos))
    if len(atoms) != 1:
        expanded = sp.expand(sp.expand_trig(residual))
        # Exact double-angle/Pythagorean reduction, only when it produces a
        # polynomial in one function. Mixed sin*cos remains unsupported.
        for old, replacement in ((sp.cos(x)**2, 1-sp.sin(x)**2), (sp.sin(x)**2, 1-sp.cos(x)**2)):
            candidate = sp.expand(expanded.subs(old, replacement))
            candidate_atoms = list(candidate.atoms(sp.sin, sp.cos))
            if len(candidate_atoms) == 1:
                residual, atoms = candidate, candidate_atoms
                break
    if len(atoms) != 1:
        raise ParseError("Requires a polynomial in one sin/cos function")
    trig = atoms[0]
    argument = sp.expand(trig.args[0])
    slope = sp.simplify(sp.diff(argument, x))
    shift = sp.simplify(argument.subs(x, 0))
    if slope.free_symbols or slope.is_real is not True or slope.is_zero is not False or shift.free_symbols or shift.is_real is not True or sp.simplify(argument - slope*x - shift) != 0:
        raise ParseError("Requires a resolved affine trigonometric argument")
    t = sp.Dummy("trig", real=True)
    polynomial = sp.Poly(residual.xreplace({trig: t}), t)
    if not 1 <= polynomial.degree() <= 4 or polynomial.as_expr().free_symbols - {t}:
        raise ParseError("Trig polynomial must have degree 1 to 4 and constant coefficients")
    roots = resolved(sp.solveset(polynomial.as_expr(), t, domain=sp.Interval(-1, 1)))
    if not isinstance(roots, sp.FiniteSet) and roots != sp.S.EmptySet:
        raise ParseError("Trig polynomial roots are not an exact finite set")
    families = []
    k = sp.Symbol("k", integer=True)
    for c in roots:
        c = sp.simplify(c)
        if (1 - c**2).is_nonnegative is not True:
            raise ParseError("Trig value range is unresolved")
        if trig.func == sp.sin:
            angle = sp.asin(c)
            offsets = (angle, sp.pi - angle)
        else:
            angle = sp.acos(c)
            offsets = (angle, -angle)
        for offset in offsets:
            families.append(sp.ImageSet(sp.Lambda(k, sp.simplify((offset-shift)/slope) + 2*sp.pi/abs(slope)*k), sp.S.Integers))
    result = sp.Union(*families)
    if interval is not None:
        if isinstance(interval, sp.FiniteSet):
            result = resolved(sp.Intersection(result, interval))
        elif interval != sp.S.EmptySet:
            result = finite_restriction(result, interval)
        else:
            result = sp.S.EmptySet
    return result, x


def task_roots(raw, constraints=()):
    parsed = math(raw)
    if not parsed.is_equation or len(parsed.symbols) != 1:
        raise ParseError("Requires one task equation")
    x = parsed.symbols[0]
    allowed = resolved(
        sp.Intersection(domain(parsed, x), constraint_domain(constraints, x))
    )
    if any(expr.has(sp.sin, sp.cos) for expr in parsed.sides):
        return trig_solutions(raw, None if allowed == sp.S.Reals else allowed)
    result = resolved(sp.solveset(parsed.sides[0] - parsed.sides[1], x, domain=allowed))
    if result.has(sp.ImageSet):
        raise ParseError("Noncanonical infinite equation is unsupported")
    return result, x


def answer_candidate(steps, variable=None):
    # Last answer is authoritative; an unreadable final must not silently
    # fall back to an earlier parseable intermediate.
    candidates = [s for s in steps if s.get("role") == "answer"] or steps[-1:]
    if not candidates:
        raise ParseError("No answer step")
    last = candidates[-1]
    answer = parse_answer(last["latex"], variable)
    if answer.value is None:
        raise ParseError(answer.reason)
    return last["step_id"], answer.value


def rhs_chain(source):
    # Terminal punctuation is allowed; decimal points within numbers survive.
    source = source.strip().rstrip(".,")
    pieces = split_parts(source, "=")
    if len(pieces) < 2:
        raise ParseError("A written answer equality is required")
    return [math(p).sides[0] for p in pieces if p]


def function_answers(givens, steps):
    functions = {}
    for raw in givens:
        m = re.fullmatch(r"\s*([fg])\(([A-Za-z])\)\s*=\s*(.+)", raw, re.S)
        if m:
            functions[m[1]] = (sp.Symbol(m[2], real=True), math(m[3]))
    if set(functions) != {"f", "g"}:
        raise ParseError("Two explicit f and g definitions are required")
    x = functions["f"][0]
    f = functions["f"][1]
    g = functions["g"][1]
    if functions["g"][0] != x or set(f.symbols + g.symbols) - {x}:
        raise ParseError("Function parameters must agree and have no unbound constants")
    source_domain = sp.Intersection(domain(f, x), domain(g, x))
    fv, gv = f.sides[0], g.sides[0]
    expected = {"f+g": fv + gv, "f-g": fv - gv, "fg": fv * gv, "f/g": fv / gv}
    checks = []
    seen = set()
    for step in steps:
        text = normalize_function(step["latex"])
        m = re.fullmatch(r"\((f\+g|f-g|fg|f/g)\)\(([A-Za-z])\)\s*=\s*(.+)", text, re.S)
        if not m:
            raise ParseError("Unsupported function answer branch")
        name, var, rhs = m.groups()
        if name in seen:
            raise ParseError("Duplicate function answer branch")
        seen.add(name)
        pieces = split_parts(rhs, ",;")
        chain = rhs_chain("0=" + pieces[0])[1:]
        parsed_chain = [math(part) for part in split_parts(pieces[0], "=")]
        y = sp.Symbol(var, real=True)
        actual = chain[-1].subs(y, x)
        if actual.free_symbols - {x}:
            raise ParseError("Unbound function answer parameter")
        written = math(split_parts(pieces[0], "=")[-1])
        answer_domain = domain(written, y).subs(y, x)
        for restriction in pieces[1:]:
            if not restriction.strip():
                continue
            parsed = parse_answer(restriction, y)
            if parsed.value is None:
                raise ParseError(parsed.reason)
            answer_domain = sp.Intersection(answer_domain, parsed.value.subs(y, x))
        wanted_domain = source_domain
        if name == "f/g":
            wanted_domain = sp.Complement(
                source_domain, resolved(sp.solveset(gv, x, domain=source_domain))
            )
        if wanted_domain.is_empty is True:
            raise ParseError("Function operation has an empty domain")
        difference = sp.cancel(expected[name] - actual)
        equal = (
            True
            if difference == 0
            else (False if difference.is_rational_function(x) else None)
        )
        same_domain = equal_sets(wanted_domain, answer_domain)
        status = (
            "INVALID"
            if equal is False or same_domain is False
            else ("VALID" if equal is True and same_domain is True else "UNSUPPORTED")
        )
        # Every written equality, not only the last RHS, must be an identity.
        for index, (left, right) in enumerate(zip(chain, chain[1:])):
            equal_domain = equal_sets(
                domain(parsed_chain[index], y), domain(parsed_chain[index + 1], y)
            )
            if equal_domain is not True:
                status = "INVALID" if equal_domain is False else "UNSUPPORTED"
                break
            diff = sp.simplify(left - right)
            if diff == 0:
                continue
            status = "INVALID" if diff.is_rational_function(y) else "UNSUPPORTED"
            break
        checks.append(
            (step["step_id"], status, "Exact function value and domain comparison")
        )
    if seen != set(expected):
        raise ParseError("All four distinct function operations are required")
    return checks


def normalize_function(text):
    from .parser import normalize_latex

    return normalize_latex(text).replace(r"\frac{f}{g}", "f/g").strip().rstrip(".,")
