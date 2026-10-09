"""Assisted dependency proofs, independent of ordinary linear checking.

Graph labels select a proof obligation; they are never proof themselves.
Unverified predecessors remain visible even when a final answer is exact.
"""

from __future__ import annotations
from dataclasses import replace
import re
import sympy as sp

from .answers import parse_answer, split_parts, strip_answer_label
from .assisted_rules import (
    inequality_set,
    task_roots,
    function_answers,
    constraint_domain,
)
from .context_rules import check_context
from .environment import bindings, substitute, equal_values
from .exact_math import math, equal_sets, RELATION, finite_restriction
from .parser import ParseError, normalize_latex
from .verifier import _compare, Unsupported


def _status(truth):
    return (
        "VALID" if truth is True else ("INVALID" if truth is False else "UNSUPPORTED")
    )


def _nonzero_constraints(raws):
    result = []
    for raw in raws:
        match = re.search(r"\\(?:neq|ne)(?![A-Za-z])|!=", raw)
        if not match:
            continue
        a, b = math(raw[: match.start()]), math(raw[match.end() :])
        if a.is_equation or b.is_equation:
            raise ParseError("Ambiguous nonzero constraint")
        result.append(("nonzero", a.sides[0] - b.sides[0]))
    return tuple(result)


def _identity(a, b, env, restrictions=()):
    if restrictions:
        a = replace(a, constraints=a.constraints + restrictions)
        b = replace(b, constraints=b.constraints + restrictions)
    # Substitutions act on parsed trees, so x=-2 in x^2 stays (-2)^2.
    left, right = substitute(a, env)[0], substitute(b, env)[0]
    symbols = left.free_symbols | right.free_symbols
    for _, constraint in a.constraints + b.constraints:
        symbols |= constraint.subs(env).free_symbols
    if isinstance(left, sp.MatrixBase) or isinstance(right, sp.MatrixBase):
        if not isinstance(left, sp.MatrixBase) or not isinstance(right, sp.MatrixBase):
            return "UNSUPPORTED"
        if left.shape != right.shape:
            return "INVALID"
        return _status(sp.simplify(left - right).is_zero_matrix)
    if not symbols:
        return _status(sp.simplify(left - right).is_zero)
    aa = replace(
        a,
        sides=(left,),
        symbols=tuple(sorted(symbols, key=str)),
        constraints=tuple((k, e.subs(env)) for k, e in a.constraints),
    )
    bb = replace(
        b,
        sides=(right,),
        symbols=tuple(sorted(symbols, key=str)),
        constraints=tuple((k, e.subs(env)) for k, e in b.constraints),
    )
    try:
        return _compare(aa, bb).status
    except (Unsupported, ValueError, TypeError, NotImplementedError):
        # Exact polynomial/trig identity can prove validity, never guess
        # invalid from failure to simplify a non-polynomial expression.
        diff = sp.trigsimp(left - right)
        restrictions_a = {(k, sp.simplify(e.subs(env))) for k, e in a.constraints}
        restrictions_b = {(k, sp.simplify(e.subs(env))) for k, e in b.constraints}
        return (
            "VALID" if diff == 0 and restrictions_a == restrictions_b else "UNSUPPORTED"
        )


def _statement(raw):
    if re.search(r"\\(?:leq|geq|le|ge)(?![A-Za-z])|[<>]", raw):
        value, x = inequality_set(raw)
        return ("relation", (value, x))
    if r"\in" not in raw and r"\pm" not in raw:
        try:
            return ("math", math(raw))
        except (ValueError, TypeError):
            pass
    answer = parse_answer(raw)
    if answer.value is not None:
        return ("set", answer.value)
    return ("math", math(raw))


def _equivalence(previous, current, env=None, restrictions=()):
    try:
        pa, pb = math(previous), math(current)
        if set(pb.symbols) - set(pa.symbols) - set(env or {}):
            return "UNSUPPORTED"
    except (ValueError, TypeError):
        pass
    if env:
        replacements = {
            key: value for key, value in env.items() if isinstance(key, sp.Symbol)
        }

        def render(raw):
            matches = list(RELATION.finditer(raw))
            if len(matches) == 1:
                m = matches[0]
                a, b = math(raw[: m.start()]), math(raw[m.end() :])
                for parsed in (a, b):
                    if any(
                        expr.subs(replacements).free_symbols
                        for _, expr in parsed.constraints
                    ):
                        raise ParseError(
                            "Substitution has unresolved symbolic domain restrictions"
                        )
                return (
                    sp.latex(substitute(a, replacements)[0])
                    + m[0]
                    + sp.latex(substitute(b, replacements)[0])
                )
            return raw

        try:
            previous = render(previous)
        except (ValueError, TypeError):
            pass
        try:
            current = render(current)
        except (ValueError, TypeError):
            pass
    try:
        a, b = _statement(previous), _statement(current)
    except (ValueError, TypeError, NotImplementedError):
        return "UNSUPPORTED"
    if a[0] == "math" and b[0] == "math":
        if restrictions:
            extra_symbols = set().union(
                *(expr.free_symbols for _, expr in restrictions)
            )
            a = (
                "math",
                replace(
                    a[1],
                    constraints=a[1].constraints + restrictions,
                    symbols=tuple(sorted(set(a[1].symbols) | extra_symbols, key=str)),
                ),
            )
            b = (
                "math",
                replace(
                    b[1],
                    constraints=b[1].constraints + restrictions,
                    symbols=tuple(sorted(set(b[1].symbols) | extra_symbols, key=str)),
                ),
            )
        if (
            a[1].is_equation
            and b[1].is_equation
            and a[1].constraints == b[1].constraints
        ):
            ar = sp.trigsimp(a[1].sides[0] - a[1].sides[1])
            br = sp.trigsimp(b[1].sides[0] - b[1].sides[1])
            if ar == br:
                return "VALID"
            if ar != 0:
                ratio = sp.trigsimp(br / ar)
                if not ratio.free_symbols and ratio.is_nonzero is True:
                    return "VALID"
        try:
            return _compare(a[1], b[1]).status
        except (Unsupported, ValueError, TypeError, NotImplementedError):
            if a[1].is_equation and b[1].is_equation:
                # Canonical trig families may replace an equation only after
                # its full set has been constructed; equivalent residuals
                # prove transformations without solving harder equations.
                ar = sp.trigsimp(a[1].sides[0] - a[1].sides[1])
                br = sp.trigsimp(b[1].sides[0] - b[1].sides[1])
                if ar != 0:
                    ratio = sp.trigsimp(br / ar)
                    if (
                        not ratio.free_symbols
                        and ratio.is_nonzero is True
                        and a[1].constraints == b[1].constraints
                    ):
                        return "VALID"
            try:
                return _status(
                    equal_sets(task_roots(previous)[0], task_roots(current)[0])
                )
            except (ValueError, TypeError, NotImplementedError):
                return "UNSUPPORTED"

    def as_set(statement, raw):
        if statement[0] == "set":
            return statement[1]
        if statement[0] == "relation":
            return statement[1][0]
        return task_roots(raw)[0]

    try:

        def variable(statement, raw):
            if statement[0] == "relation":
                return statement[1][1]
            if statement[0] == "math" and len(statement[1].symbols) == 1:
                return statement[1].symbols[0]
            m = re.match(r"\s*([A-Za-z])\s*(?:=|\\in)", raw)
            return sp.Symbol(m[1], real=True) if m else None

        x, y = variable(a, previous), variable(b, current)
        if x is not None and y is not None and x != y:
            return "UNSUPPORTED"
        return _status(equal_sets(as_set(a, previous), as_set(b, current)))
    except (ValueError, TypeError, NotImplementedError):
        return "UNSUPPORTED"


def _solution(raw):
    # Preserve relation variable names when comparing branches.
    if re.search(r"\\(?:leq|geq|le|ge)(?![A-Za-z])|[<>]", raw):
        return inequality_set(raw)
    try:
        return task_roots(raw)
    except (ValueError, TypeError, NotImplementedError):
        answer = parse_answer(raw)
        if answer.value is None:
            raise ParseError(answer.reason)
        match = re.match(r"\s*([A-Za-z])\s*(?:=|\\in)", raw)
        return answer.value, sp.Symbol(match[1], real=True) if match else None


def _branch_subset(previous, current):
    parent, x = _solution(previous)
    child, y = _solution(current)
    if x is not None and y is not None and x != y:
        return "UNSUPPORTED"
    if parent.has(sp.ImageSet) or child.has(sp.ImageSet):
        # Periodic subset claims require the stronger exact union rule.
        return "VALID" if equal_sets(parent, child) is True else "UNSUPPORTED"
    return _status(sp.Complement(child, parent).is_empty)


def _selection(previous, current, restrictions):
    family, x = _solution(previous)
    actual, y = _solution(current)
    if x is None or (y is not None and x != y):
        return "UNSUPPORTED"
    allowed = constraint_domain(restrictions, x)
    if allowed == sp.S.Reals:
        return "UNSUPPORTED"
    expected = (
        finite_restriction(family, allowed)
        if family.has(sp.ImageSet)
        else sp.Intersection(family, allowed)
    )
    return _status(equal_sets(expected, actual))


def _row(raw, env, previous=None, restrictions=()):
    raw = strip_answer_label(raw)
    if r"\text" in raw:
        raise ParseError("Prose/conditions are not a fully parsed mathematical step")
    text = (
        normalize_latex(raw)
        .replace(r"\{", "{")
        .replace(r"\}", "}")
        .strip()
        .rstrip(".,")
    )
    root_list = parse_answer(text)
    if root_list.value is not None and (
        text.startswith("{") or (";" in text and "=" in text)
    ):
        return text, text, []
    # Explicit mathematical implication is multiple checked statements; no
    # annotation/overset rewrite is attempted.
    statements = re.split(r"\\(?:Rightarrow|implies|Leftrightarrow)(?![A-Za-z])", text)
    checks = []
    anchor = None
    last = None
    fragment_count = 0
    for statement in statements:
        # Sets and inequalities must be consumed as a whole (commas can be
        # interval separators or an integer declaration).
        if re.search(r"\\(?:in|pm|leq|geq|le|ge)(?![A-Za-z])|[<>]", statement):
            _statement(statement)
            last = statement
            anchor = anchor or statement
            if len(statements) > 1 and previous is not None:
                checks.append(_equivalence(previous, statement))
            previous = statement
            continue
        for fragment in split_parts(statement, ",;"):
            fragment_count += 1
            leading = fragment.startswith("=")
            parts = split_parts(fragment[1:] if leading else fragment, "=")
            atoms = {
                key.name: value
                for key, value in env.items()
                if isinstance(key, sp.Symbol) and isinstance(value, sp.MatrixBase)
            }
            values = [math(p, atoms) for p in parts]
            if any(p.is_equation for p in values):
                raise ParseError("Unexpected equation fragment")
            if leading:
                if previous is None:
                    raise ParseError("Continuation requires one readable dependency")
                prev_parts = split_parts(previous, "=")
                checks.append(
                    _identity(math(prev_parts[-1], atoms), values[0], env, restrictions)
                )
            for i, (left, right) in enumerate(zip(values, values[1:])):
                if i == 0 and not leading and substitute(left, env)[0].free_symbols:
                    # This is an equation claim; the incoming edge below must
                    # establish it. Internal equalities still require proof.
                    identity = _identity(left, right, env, restrictions)
                    if identity == "VALID":
                        checks.append(identity)
                    elif fragment_count > 1:
                        checks.append("UNSUPPORTED")
                    continue
                checks.append(_identity(left, right, env, restrictions))
            if len(values) >= 2 and not leading:
                candidate = parts[0] + "=" + parts[1]
                anchor = anchor or candidate
                last = (
                    parts[0] + "=" + parts[-1]
                    if values[0].sides[0].free_symbols
                    else parts[-1]
                )
            else:
                anchor = anchor or parts[0]
                last = parts[-1]
            previous = last
    if not anchor:
        raise ParseError("No mathematical statement")
    return anchor, last, checks


def verify_graph(spec):
    steps = spec["steps"]
    ids = [s["step_id"] for s in steps]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate assisted step IDs")
    givens = {g["given_id"]: g["raw_latex"] for g in spec["task"].get("givens", [])}
    duplicate_givens = len(givens) != len(spec["task"].get("givens", []))
    nodes = {}
    reviews = []
    edges = []
    function_checks = {}
    if spec["compilation"]["task_class"] == "function_operation":
        try:
            function_checks = {
                step_id: (status, reason)
                for step_id, status, reason in function_answers(
                    list(givens.values()), steps
                )
            }
        except (ValueError, TypeError, NotImplementedError):
            pass
    for step in steps:
        sid = step["step_id"]
        refs = step.get("derives_from", [])
        used = step.get("uses_givens", [])
        status = "UNSUPPORTED"
        reason = "No exact proof for this node"
        anchor = last = None
        env = {}
        internal = []
        node_edges = []
        try:
            if duplicate_givens:
                raise ParseError("Duplicate given IDs")
            if step.get("exactness", "unknown") != "exact":
                raise ParseError("OCR exactness is not exact")
            if not re.fullmatch(
                r"(?:main|independent|plus_minus_[1-9][0-9]*)", step.get("branch", "")
            ):
                raise ParseError("Unknown assisted branch")
            if "derives_from" not in step:
                raise ParseError("Dependency is missing")
            if step.get("role") not in {
                "initial",
                "transformation",
                "substitution",
                "definition",
                "answer",
                "independent",
            }:
                raise ParseError("Unknown assisted role")
            if len(refs) != len(set(refs)) or any(r not in nodes for r in refs):
                raise ParseError("Dependency is missing, forward or cyclic")
            if len(used) != len(set(used)) or any(g not in givens for g in used):
                raise ParseError("Unknown or duplicate given reference")
            # Bindings travel only along proven ancestor edges. A sibling's
            # definition must not leak into another independent branch.
            env = bindings([givens[g] for g in used])
            restrictions = _nonzero_constraints(
                [c["raw_latex"] for c in spec["task"].get("constraints", [])]
                + [givens[g] for g in used]
            )
            if (
                spec["compilation"]["task_class"] == "matrix_system"
                and set(used) == set(givens)
                and len(givens) == 2
            ):
                from .context_extensions import matrix_bindings

                env.update(matrix_bindings(list(givens.values())))
            for ref in refs:
                if nodes[ref]["status"] == "VALID" and (
                    nodes[ref]["branch"] == step.get("branch", "main")
                    or nodes[ref]["branch"] == "main"
                ):
                    for name, value in nodes[ref]["environment"].items():
                        if name in env and equal_values(env[name], value) is not True:
                            raise ParseError("Conflicting dependency bindings")
                        env[name] = value
            if sid in function_checks:
                status, reason = function_checks[sid]
                anchor = last = step["latex"]
                for g in used:
                    node_edges.append((g, status, reason))
                if not used:
                    raise ParseError(
                        "Function branch requires explicit given references"
                    )
            else:
                previous = nodes[refs[0]]["last"] if len(refs) == 1 else None
                if (
                    spec["compilation"]["task_class"] == "determinant"
                    and r"\begin{vmatrix}" in step["latex"]
                ):
                    template = math(split_parts(normalize_latex(step["latex"]), "=")[0])
                    if template.symbols and not any(
                        math(raw).symbols for raw in givens.values()
                    ):
                        raise ParseError(
                            "Symbolic determinant template has no explicit entry bindings"
                        )
                anchor, last, internal = _row(
                    step["latex"], env, previous, restrictions
                )
                obligations = []
                if not refs and not used and step.get("role") == "initial":
                    for g, raw in givens.items():
                        proof = _equivalence(raw, anchor)
                        if proof == "VALID" or (
                            proof == "INVALID" and len(givens) == 1
                        ):
                            obligations.append(proof)
                            node_edges.append(
                                (
                                    g,
                                    proof,
                                    "Initial statement comparison with an explicit task given",
                                )
                            )
                # Definitions are legitimate introductions only if their
                # variable is fresh, or exactly equals an existing binding.
                declared = (
                    bindings([step["latex"]])
                    if step.get("role") == "definition"
                    else {}
                )
                if step.get("role") == "definition" and not declared:
                    definition = math(step["latex"])
                    if definition.is_equation:
                        name, value = definition.sides
                        if (
                            isinstance(name, sp.Symbol)
                            and name not in value.free_symbols
                            and (
                                (value.is_Pow and value.base.is_positive is True)
                                or value.is_polynomial(*value.free_symbols)
                            )
                            and len(value.free_symbols) == 1
                        ):
                            declared = {name: value}
                if declared:
                    task_bindings = bindings(list(givens.values()))
                    for key, value in declared.items():
                        obligations.append(
                            _status(equal_values((env | task_bindings)[key], value))
                            if key in env or key in task_bindings
                            else "VALID"
                        )
                        premises = [
                            nodes[r]["last"]
                            for r in refs
                            if nodes[r]["last"] is not None
                        ] + [givens[g] for g in used]
                        if not refs and not used:
                            premises += list(givens.values())
                        for premise in premises:
                            try:
                                parsed_premise = math(premise)
                            except (ValueError, TypeError):
                                continue
                            if (
                                key in parsed_premise.symbols
                                and parsed_premise.is_equation
                            ):
                                proof = (
                                    _branch_subset(premise, anchor)
                                    if step.get("branch", "main").startswith(
                                        "plus_minus_"
                                    )
                                    else _equivalence(premise, anchor)
                                )
                                obligations.append(proof)
                    for ref in refs:
                        node_edges.append(
                            (
                                ref,
                                "VALID",
                                "Explicit definition; predecessor retained in dependency graph",
                            )
                        )
                    env.update(declared)
                else:
                    selection = False
                    for ref in refs:
                        prior = nodes[ref]["last"]
                        proof = (
                            "UNSUPPORTED"
                            if prior is None
                            else _equivalence(prior, anchor, env, restrictions)
                        )
                        if step.get("role") == "definition" and proof == "INVALID":
                            # An auxiliary equation need not preserve the
                            # parent solution set. Its meaning must be
                            # supported explicitly before judging it wrong.
                            proof = "UNSUPPORTED"
                        if (
                            nodes[ref]["role"] == "definition"
                            and step.get("role") == "substitution"
                            and env
                        ):
                            # A definition contributes a binding, rather than
                            # an equivalent equation to the transformed task.
                            if (
                                internal and all(c == "VALID" for c in internal)
                            ) or any(nodes[r]["role"] != "definition" for r in refs):
                                proof = "VALID"
                        if (
                            prior is not None
                            and step.get("branch", "main").startswith("plus_minus_")
                            and nodes[ref]["branch"] != step.get("branch")
                        ):
                            proof = _branch_subset(prior, anchor)
                        if (
                            prior is not None
                            and step.get("role") == "answer"
                            and len(refs) > 1
                            and all(
                                nodes[r]["branch"].startswith("plus_minus_")
                                for r in refs
                            )
                        ):
                            parts = [_solution(nodes[r]["last"]) for r in refs]
                            final, var = _solution(anchor)
                            variables = {v for _, v in parts if v is not None}
                            if len(variables) > 1 or (
                                var is not None and variables and var not in variables
                            ):
                                proof = "UNSUPPORTED"
                            else:
                                proof = _status(
                                    equal_sets(sp.Union(*(v for v, _ in parts)), final)
                                )
                        restrictions = [
                            givens[g] for g in used if r"\in" in givens[g]
                        ] + [
                            c["raw_latex"] for c in spec["task"].get("constraints", [])
                        ]
                        if (
                            prior is not None
                            and step.get("role") == "answer"
                            and restrictions
                        ):
                            try:
                                selected = _selection(prior, anchor, restrictions)
                                if selected != "UNSUPPORTED":
                                    proof = selected
                                    selection = True
                            except (ValueError, TypeError, NotImplementedError):
                                pass
                        # A pure evaluation/substitution can bridge a
                        # definition and its expression through the exact env.
                        if (
                            proof == "UNSUPPORTED"
                            and step.get("role") == "substitution"
                            and env
                            and internal
                            and all(c == "VALID" for c in internal)
                        ):
                            proof = "VALID"
                        if (
                            spec["compilation"]["task_class"] == "matrix_system"
                            and any(isinstance(v, sp.MatrixBase) for v in env.values())
                            and internal
                            and all(c == "VALID" for c in internal)
                        ):
                            proof = "VALID"
                        node_edges.append(
                            (ref, proof, "Exact dependency statement comparison")
                        )
                    for g in used:
                        proof = _equivalence(givens[g], anchor, env, restrictions)
                        if selection and r"\in" in givens[g]:
                            proof = "VALID"
                        if (
                            proof == "UNSUPPORTED"
                            and internal
                            and all(c == "VALID" for c in internal)
                        ):
                            given = math(givens[g])
                            claim = math(anchor)
                            if not given.is_equation and claim.is_equation:
                                proof = _identity(
                                    given, replace(claim, sides=(claim.sides[0],)), env
                                )
                        if (
                            proof == "UNSUPPORTED"
                            and spec["compilation"]["task_class"] == "matrix_system"
                            and internal
                            and all(c == "VALID" for c in internal)
                        ):
                            proof = "VALID"
                        if (
                            proof == "UNSUPPORTED"
                            and env
                            and internal
                            and all(c == "VALID" for c in internal)
                        ):
                            proof = "VALID"
                        node_edges.append(
                            (g, proof, "Exact given statement comparison")
                        )
                    obligations.extend(e[1] for e in node_edges)
                # Multiple dependencies can supply bindings rather than
                # equivalent statements; all their proof obligations remain.
                if step.get("role") == "answer" and not refs:
                    single = {**spec, "steps": [step]}
                    ctx = check_context(single)
                    if ctx.status != "UNSUPPORTED":
                        obligations.append(ctx.status)
                obligations.extend(internal)
                if (
                    not refs
                    and not used
                    and not declared
                    and not internal
                    and not obligations
                ):
                    raise ParseError("Unanchored mathematical statement")
                status = (
                    "INVALID"
                    if "INVALID" in obligations
                    else (
                        "VALID"
                        if obligations and all(c == "VALID" for c in obligations)
                        else "UNSUPPORTED"
                    )
                )
                reason = (
                    "Exact node and dependency checks"
                    if status != "UNSUPPORTED"
                    else "At least one node/edge proof is unresolved"
                )
                # Reject a fresh, unrelated equation even if it had a true
                # internal tail, e.g. x=7=7 without a condition for x.
                if not refs and not used and not declared and not node_edges:
                    parsed = math(anchor)
                    if parsed.is_equation and parsed.symbols:
                        ident = _identity(
                            replace(parsed, sides=(parsed.sides[0],)),
                            replace(parsed, sides=(parsed.sides[1],)),
                            env,
                        )
                        if ident != "VALID" and step.get("role") != "answer":
                            status = "UNSUPPORTED"
                            reason = "Symbolic claim has no given/dependency anchor"
            if status == "VALID":
                # Only exactly proved derived bindings can reach descendants.
                for key, value in bindings([last or ""]).items():
                    if key not in env:
                        env[key] = value
        except (
            ValueError,
            TypeError,
            NotImplementedError,
            RecursionError,
            ZeroDivisionError,
        ) as exc:
            reason = str(exc)
            status = "UNSUPPORTED"
            # Invalid internal equalities are evidence even if another
            # fragment is unsupported; localization still respects ancestors.
        for ref, proof, why in node_edges:
            edges.append({"from": ref, "to": sid, "status": proof, "reason": why})
        for ref in refs + used:
            if not any(e["from"] == ref and e["to"] == sid for e in edges):
                edges.append(
                    {"from": ref, "to": sid, "status": "UNSUPPORTED", "reason": reason}
                )
        nodes[sid] = {
            "status": status,
            "last": last,
            "role": step.get("role"),
            "branch": step.get("branch", "main"),
            "environment": env if status == "VALID" else {},
            "ancestors": set(refs).union(
                *(nodes[r]["ancestors"] for r in refs if r in nodes)
            ),
        }
        reviews.append(
            {
                "step_id": sid,
                "status": status,
                "reason": reason,
                "role": step.get("role"),
                "branch": step.get("branch", "main"),
            }
        )
    errors = [r["step_id"] for r in reviews if r["status"] == "INVALID"]
    unknown = [r["step_id"] for r in reviews if r["status"] == "UNSUPPORTED"]
    # First error is in reading order. An earlier unresolved independent
    # branch can contain an earlier mistake too, so it also blocks firstness.
    first = errors[0] if errors else None
    blocked = bool(first and any(ids.index(u) < ids.index(first) for u in unknown))
    return {
        "covered": all(r["status"] != "UNSUPPORTED" for r in reviews)
        and all(e["status"] != "UNSUPPORTED" for e in edges),
        "first_error_step": None if blocked else first,
        "localization_blocked": blocked,
        "invalid_steps": errors,
        "unsupported_steps": unknown,
        "nodes": reviews,
        "edges": edges,
    }
