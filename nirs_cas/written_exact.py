"""Opt-in, label-free exact checking of written mathematics.

The first symbolic equation is a premise. Missing task context is never
reconstructed from GT labels, step kinds, hints or a plausible numeric value.
"""

import multiprocessing as mp
import re
from time import perf_counter

import sympy as sp

from .answers import split_parts
from .environment import substitute
from .exact_math import math, RELATION
from .graph_verifier import _equivalence, _identity, _nonzero_constraints
from .parser import ParseError
from .written_layout import written_layout


def _check(status, rule, reason=None):
    return {"status": status, "rule": rule, "reason": reason or rule}


def _restriction(raw):
    matches = list(RELATION.finditer(raw))
    return len(matches) == 1 and matches[0][0] in (r"\neq", r"\ne", "!=")


def _identity_check(a, b, env, restrictions=()):
    status = _identity(a, b, env, restrictions)
    if status != "UNSUPPORTED":
        return _check(status, "exact_identity_and_domain")
    # A fully exact admissible witness can refute an identity. Passing a
    # collection of numeric points never establishes validity.
    left, right = substitute(a, env)[0], substitute(b, env)[0]
    if isinstance(left, sp.MatrixBase) or isinstance(right, sp.MatrixBase):
        return _check(status, "exact_matrix_identity")
    variables = sorted(left.free_symbols | right.free_symbols, key=str)
    if len(variables) <= 2:
        for point in (sp.S.Zero, sp.S.One, -sp.S.One, sp.S(2), sp.pi / 6, sp.pi / 4):
            at = {x: point for x in variables}
            valid = True
            for kind, expr in a.constraints + b.constraints + tuple(restrictions):
                value = sp.simplify(expr.subs(env).subs(at))
                truth = (
                    value.is_nonzero
                    if kind == "nonzero"
                    else value.is_positive
                    if kind == "positive"
                    else value.is_nonnegative
                )
                valid &= truth is True
            difference = sp.simplify((left - right).subs(at)) if valid else None
            if (
                difference is not None
                and difference.is_zero is False
                and not difference.has(sp.nan, sp.zoo, sp.oo, -sp.oo)
            ):
                return _check(
                    "INVALID",
                    "exact_counterexample",
                    f"Exact witness {at}: difference={difference}",
                )
    return _check("UNSUPPORTED", "identity_unresolved")


def verify_exact_written(steps):
    if (
        not isinstance(steps, list)
        or not steps
        or any(not isinstance(s, str) or not s.strip() for s in steps)
    ):
        raise ValueError("Steps must be a nonempty list of LaTeX strings")
    reviews, previous, previous_kind = [], None, None
    env = {}
    for number, raw in enumerate(steps, 1):
        checks, anchors, parsed_ok = [], [], True
        next_env = dict(env)
        try:
            layout = written_layout(raw)
            checks.extend(_check("UNSUPPORTED", "prose", r) for r in layout.unsupported)
            if not layout.fragments:
                raise ParseError("No mathematical statement")
            restrictions = _nonzero_constraints(
                [f for f in layout.fragments if _restriction(f)]
            )
            mathematical = [f for f in layout.fragments if not _restriction(f)]
            row_previous = previous
            for fragment in mathematical:
                try:
                    leading = fragment.startswith("=")
                    parts = split_parts(fragment[1:] if leading else fragment, "=")
                    # Inequalities and root lists need set semantics, not
                    # equality-chain splitting or implicit multiplication.
                    is_set = bool(
                        re.search(
                            r"\\(?:in|pm|leq|geq|le|ge)(?![A-Za-z])|[<>]", fragment
                        )
                    )
                    if is_set:
                        from .graph_verifier import _statement

                        _statement(fragment)
                        if row_previous is None:
                            checks.append(
                                _check(
                                    "VALID" if number == 1 else "UNSUPPORTED",
                                    "initial_relation",
                                )
                            )
                        else:
                            checks.append(
                                _check(
                                    _equivalence(row_previous, fragment),
                                    "exact_solution_set",
                                )
                            )
                        if r"\pm" in fragment or r"\in" in fragment:
                            match = re.match(r"\s*([A-Za-z])\s*(?:=|\\in)", fragment)
                            variable = sp.Symbol(match[1], real=True) if match else None
                            if variable in env:
                                from .graph_verifier import _solution
                                from .exact_math import equal_sets

                                actual, _ = _solution(fragment)
                                equal = equal_sets(sp.FiniteSet(env[variable]), actual)
                                checks.append(
                                    _check(
                                        "VALID"
                                        if equal is True
                                        else "INVALID"
                                        if equal is False
                                        else "UNSUPPORTED",
                                        "preserve_proven_binding",
                                    )
                                )
                        anchors.append((fragment, "relation"))
                        row_previous = fragment
                        continue
                    values = []
                    for part in parts:
                        try:
                            values.append(math(part))
                        except (ValueError, TypeError, NotImplementedError) as exc:
                            values.append(None)
                            parsed_ok = False
                            checks.append(_check("UNSUPPORTED", "parse", str(exc)))
                    if not any(v is not None for v in values):
                        continue
                    # Unsupported differential/function labels must not erase
                    # independently readable arithmetic in the rest of a row.
                    first = values[0]
                    equation = (
                        len(values) >= 2 and first is not None and values[1] is not None
                    )
                    start = 0
                    named = False
                    if equation and not leading:
                        a, b = first.sides[0], values[1].sides[0]
                        identity = _identity(first, values[1], env, restrictions)
                        symbols = (
                            substitute(first, env)[0].free_symbols
                            | substitute(values[1], env)[0].free_symbols
                        )
                        if identity == "VALID" or not symbols:
                            checks.append(
                                _identity_check(first, values[1], env, restrictions)
                            )
                        elif r"\begin{array}" in raw and r"\hline" in raw:
                            # A vertical arithmetic layout claims an identity,
                            # not a new equation assumed true as a premise.
                            checks.append(
                                _identity_check(first, values[1], env, restrictions)
                            )
                        elif (
                            isinstance(a, sp.Symbol)
                            and a not in b.free_symbols
                            and a not in env
                        ):
                            # Written definitions introduce a fresh scalar only
                            # when the RHS is an exact constant. Otherwise they
                            # remain symbolic premises requiring an anchor.
                            if not b.free_symbols:
                                named = True
                                if previous is None or (
                                    math(previous).symbols
                                    and a not in math(previous).symbols
                                ):
                                    checks.append(
                                        _check("VALID", "explicit_numeric_definition")
                                    )
                                else:
                                    checks.append(
                                        _check(
                                            _equivalence(
                                                previous, parts[0] + "=" + parts[1]
                                            ),
                                            "equation_transition",
                                        )
                                    )
                            elif number == 1:
                                checks.append(
                                    _check("VALID", "trusted_initial_equation")
                                )
                            else:
                                checks.append(
                                    _check("UNSUPPORTED", "unanchored_definition")
                                )
                        elif row_previous is not None and previous_kind == "identity":
                            checks.append(
                                _check("UNSUPPORTED", "missing_explicit_substitution")
                            )
                        elif row_previous is not None and previous_kind != "expression":
                            checks.append(
                                _check(
                                    _equivalence(
                                        row_previous, parts[0] + "=" + parts[1]
                                    ),
                                    "equation_transition",
                                )
                            )
                        elif number == 1:
                            checks.append(_check("VALID", "trusted_initial_equation"))
                        else:
                            checks.append(
                                _check(
                                    "UNSUPPORTED",
                                    "missing_substitution_or_equation_anchor",
                                )
                            )
                        start = 1
                    if leading:
                        if row_previous is None:
                            checks.append(
                                _check(
                                    "VALID" if number == 1 else "UNSUPPORTED",
                                    "trusted_initial_expression"
                                    if number == 1
                                    else "missing_continuation",
                                )
                            )
                        elif first is not None:
                            tail = split_parts(row_previous, "=")[-1]
                            checks.append(
                                _identity_check(math(tail), first, env, restrictions)
                            )
                    for a, b in zip(values[start:], values[start + 1 :]):
                        if a is None or b is None:
                            continue
                        proof = _identity_check(a, b, env, restrictions)
                        left, right = substitute(a, env)[0], substitute(b, env)[0]
                        if (
                            left.free_symbols
                            and not right.free_symbols
                            and proof["status"] != "VALID"
                        ):
                            # A hidden evaluation point is not evidence of an
                            # invalid identity. It is missing input context.
                            proof = _check(
                                "UNSUPPORTED", "missing_explicit_substitution"
                            )
                        checks.append(proof)
                    if len(values) == 1 and first is not None and not leading:
                        if row_previous is not None and previous_kind == "expression":
                            checks.append(
                                _identity_check(
                                    math(split_parts(row_previous, "=")[-1]),
                                    first,
                                    env,
                                    restrictions,
                                )
                            )
                        elif number == 1:
                            checks.append(_check("VALID", "trusted_initial_expression"))
                        else:
                            checks.append(
                                _check(
                                    "UNSUPPORTED", "separate_expression_without_context"
                                )
                            )
                    if all(v is not None for v in values):
                        if equation and not leading and not named:
                            anchor = parts[0] + "=" + parts[-1]
                            kind = (
                                "identity"
                                if _identity(first, values[-1], env, restrictions)
                                == "VALID"
                                else "equation"
                            )
                        else:
                            anchor, kind = parts[-1], "expression"
                        anchors.append((anchor, kind))
                        row_previous = anchor
                        if (
                            equation
                            and isinstance(first.sides[0], sp.Symbol)
                            and all(c["status"] == "VALID" for c in checks)
                        ):
                            bound = sp.simplify(substitute(values[-1], env)[0])
                            if not bound.free_symbols:
                                next_env[first.sides[0]] = bound
                except (
                    ValueError,
                    TypeError,
                    NotImplementedError,
                    ZeroDivisionError,
                ) as exc:
                    checks.append(_check("UNSUPPORTED", "parse_or_rule", str(exc)))
                    parsed_ok = False
            if not checks:
                checks.append(_check("UNSUPPORTED", "no_proof_obligation"))
        except (ValueError, TypeError, NotImplementedError, ZeroDivisionError) as exc:
            checks.append(_check("UNSUPPORTED", "layout", str(exc)))
            parsed_ok = False
        status = (
            "INVALID"
            if any(c["status"] == "INVALID" for c in checks)
            else "UNSUPPORTED"
            if any(c["status"] == "UNSUPPORTED" for c in checks)
            else "VALID"
        )
        reviews.append(
            {
                "step": number,
                "status": status,
                "parse_status": "OK" if parsed_ok else "PARSE_FAILED",
                "reason": "; ".join(dict.fromkeys(c["reason"] for c in checks)),
                "checks": checks,
            }
        )
        previous, previous_kind = anchors[-1] if len(anchors) == 1 else (None, None)
        if status == "VALID":
            env = next_env
    premise_rules = {
        "trusted_initial_equation",
        "trusted_initial_expression",
        "initial_relation",
        "explicit_numeric_definition",
    }
    if all(c["rule"] in premise_rules for r in reviews for c in r["checks"]):
        # Reading a premise or a standalone final expression is not a proof.
        # At least one actual identity/transition must have been checked.
        reviews[-1]["checks"].append(_check("UNSUPPORTED", "only_unverified_premises"))
        reviews[-1]["status"] = "UNSUPPORTED"
        reviews[-1]["reason"] += "; only_unverified_premises"
    errors = [
        r["step"] for r in reviews if any(c["status"] == "INVALID" for c in r["checks"])
    ]
    unknown = [
        r["step"]
        for r in reviews
        if any(c["status"] == "UNSUPPORTED" for c in r["checks"])
    ]
    first = errors[0] if errors else None
    localized = (
        first if first is not None and not any(u < first for u in unknown) else None
    )
    covered = not unknown
    return {
        "status": ("INVALID" if errors else "VALID") if covered else "UNSUPPORTED",
        "covered": covered,
        "has_error": True if errors else False if covered else None,
        "first_error_step": localized,
        "parse_status": "OK"
        if all(r["parse_status"] == "OK" for r in reviews)
        else "PARSE_FAILED",
        "parsed_steps": sum(r["parse_status"] == "OK" for r in reviews),
        "total_steps": len(steps),
        "transitions": reviews,
        "known_error_steps": errors,
        "unsupported_steps": unknown,
        "reason": "Only written LaTeX; initial premise trusted; task context and completeness not established",
    }


def _worker(steps, connection):
    try:
        started = perf_counter()
        result = verify_exact_written(steps)
        result["latency_ms"] = round((perf_counter() - started) * 1000, 3)
        connection.send(result)
    except Exception as exc:
        connection.send({"error": f"{type(exc).__name__}: {exc}"})
    finally:
        connection.close()


def run_exact_isolated(steps, timeout=10):
    if timeout <= 0:
        raise ValueError("Timeout must be positive")
    context = mp.get_context("spawn")
    read, write = context.Pipe(duplex=False)
    process = context.Process(target=_worker, args=(steps, write))
    started = perf_counter()
    process.start()
    write.close()
    result = None
    try:
        if read.poll(timeout):
            try:
                result = read.recv()
            except EOFError:
                pass
    finally:
        if process.is_alive():
            process.terminate()
        process.join()
        process.close()
        read.close()
    if not isinstance(result, dict) or "error" in result:
        result = {
            "status": "UNSUPPORTED",
            "covered": False,
            "has_error": None,
            "first_error_step": None,
            "parse_status": "NOT_MEASURED",
            "parsed_steps": None,
            "total_steps": len(steps),
            "transitions": [],
            "known_error_steps": [],
            "reason": f"WORKER_ERROR: {result['error']}"
            if result
            else "TIMEOUT_OR_WORKER_EXIT",
            "latency_ms": None,
        }
    result["wall_ms"] = round((perf_counter() - started) * 1000, 3)
    return result
