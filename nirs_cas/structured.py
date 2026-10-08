"""Check written equality chains without using task IDs or annotation labels.

Missing substitutions, unsupported prose and separate subproblems remain explicit
unknowns. A false, independently evaluable equality is still an error witness.
"""
from dataclasses import replace
import re

import sympy as sp

from .parser import ParsedMath, normalize_latex, parse_latex
from .verifier import StepResult, Unsupported, _compare


def split_top(text: str, separators: str) -> list[str]:
    stack, start, pieces = [], 0, []
    closing = {')': '(', '}': '{', ']': '['}
    for index, char in enumerate(text):
        if char in '({[':
            stack.append(char)
        elif char in closing:
            if not stack or stack.pop() != closing[char]:
                # Interval notation is intentionally not accepted as a group.
                raise ValueError('Unbalanced delimiters')
        elif char in separators and not stack:
            pieces.append(text[start:index].strip())
            start = index + 1
    if stack:
        raise ValueError('Unbalanced delimiters')
    pieces.append(text[start:].strip())
    return pieces


def fragments(source: str) -> tuple[list[str], list[str]]:
    text = normalize_latex(source)
    unknown = []
    # A vertical subtraction layout states the sum of the rows above the line.
    array = re.fullmatch(r'\\begin\{array\}\{[rlc]\}(.*?)\\end\{array\}', text, re.S)
    if array and r'\hline' in array[1]:
        above, below = array[1].split(r'\hline', 1)
        rows = [r.strip() for r in above.split(r'\\') if r.strip()]
        result = below.replace(r'\\', '').strip()
        text = '+'.join('(' + row + ')' for row in rows) + '=' + result
    text = re.sub(r'\\(?:begin|end)\{(?:enumerate|itemize)\}', '', text)
    text = re.sub(r'\\item(?:\[[^]]*\])?', ';', text)
    text = text.replace(r'\(', '').replace(r'\)', '').replace('$', '')
    text = re.sub(r'\\tag\{[^{}]*\}', '', text)
    text = re.sub(r'\\(?:cdots|ldots)\s*\(\d+\)', '', text)
    text = text.replace(r'\{', '{').replace(r'\}', '}')
    def annotation(match):
        content = match[1].strip()
        if content.lower() in {'and', 'or', 'i.e.,', 'i.e.'}:
            if content.lower() == 'or':
                unknown.append('Disjunction needs a branch context')
            return ';'
        if content in {'L.H.S.', 'R.H.S.'}:
            return r'\label'
        # Explanatory comments are ignored only when they do not supply a
        # condition/substitution. Units require a dimensional verifier.
        if content.lower().startswith(('subtracting ', 'using commutativity')):
            return ''
        unknown.append('Text/units/conditions are outside the symbolic grammar: ' + content)
        return ''
    text = re.sub(r'\\text\{([^{}]*)\}', annotation, text)
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'\\(?:Rightarrow|implies)', ';', text)
    parts = [p.strip().rstrip('.,') for p in split_top(text, ';,') if p.strip().rstrip('.,')]
    return parts, unknown


def expression_compare(left: ParsedMath, right: ParsedMath) -> StepResult:
    if any(isinstance(v, sp.MatrixBase) for v in left.sides + right.sides):
        a, b = left.sides[0], right.sides[0]
        if not isinstance(a, sp.MatrixBase) or not isinstance(b, sp.MatrixBase):
            raise Unsupported('Scalar/matrix type mismatch')
        if a.shape != b.shape:
            return StepResult('INVALID', 'Matrix dimensions differ')
        differences = [sp.simplify(x - y) for x, y in zip(a, b)]
        if all(d.is_zero is True for d in differences):
            return StepResult('VALID', 'Exact matrix entry comparison')
        if any(d.is_zero is False for d in differences):
            return StepResult('INVALID', 'Matrix entries differ')
        raise Unsupported('Matrix equality is inconclusive')
    return _compare(left, right)


def _check_expressions(left, right):
    try:
        return expression_compare(left, right)
    except (Unsupported, NotImplementedError, ValueError, TypeError, RecursionError, ZeroDivisionError) as error:
        # A symbolic proof can establish an identity; one exact counterexample
        # can refute it. No floating-point tolerances or random sampling.
        values = left.sides + right.sides
        if not any(isinstance(v, sp.MatrixBase) for v in values):
            difference = sp.trigsimp(left.sides[0] - right.sides[0])
            constraints_a = {(kind, sp.simplify(expr)) for kind, expr in left.constraints if expr.free_symbols}
            constraints_b = {(kind, sp.simplify(expr)) for kind, expr in right.constraints if expr.free_symbols}
            if difference == 0 and constraints_a == constraints_b:
                return StepResult('VALID', 'Symbolic identity with identical source restrictions')
            variables = sorted(set(left.symbols + right.symbols), key=str)
            if len(variables) <= 2:
                for point in (0, 1, -1, 2, -2, sp.pi / 6, sp.pi / 4):
                    substitutions = {variable: point for variable in variables}
                    def admissible(constraints):
                        for kind, expr in constraints:
                            value = sp.simplify(expr.subs(substitutions))
                            valid = value.is_nonzero if kind == 'nonzero' else (value.is_positive if kind == 'positive' else value.is_nonnegative)
                            if valid is not True:
                                return False
                        return True
                    if admissible(left.constraints + right.constraints):
                        witness = sp.simplify(difference.subs(substitutions))
                        if not witness.free_symbols and witness.is_zero is False and not witness.has(sp.nan, sp.zoo, sp.oo, -sp.oo):
                            return StepResult('INVALID', f'Exact counterexample at {substitutions}: difference={witness}')
        return StepResult('UNSUPPORTED', str(error))


def _relation(source):
    match = re.search(r'\\(?:leq|geq|le|ge)(?![A-Za-z])|[<>]', source)
    if not match:
        return None
    a, b = parse_latex(source[:match.start()]), parse_latex(source[match.end():])
    if not a.value or not b.value or a.value.is_equation or b.value.is_equation:
        raise Unsupported('Inequality sides could not be parsed')
    if any(expr.free_symbols for _, expr in a.value.constraints + b.value.constraints):
        raise Unsupported('Inequality domain restrictions need explicit handling')
    symbols = set(a.value.symbols + b.value.symbols)
    if len(symbols) != 1:
        raise Unsupported('Only univariate inequalities are supported')
    operator = {'<': sp.Lt, '>': sp.Gt, r'\leq': sp.Le, r'\le': sp.Le, r'\geq': sp.Ge, r'\ge': sp.Ge}[match[0]]
    relation = operator(a.value.sides[0], b.value.sides[0])
    return sp.solve_univariate_inequality(relation, next(iter(symbols)), relational=False)


def verify_written_solution(steps: list[str]) -> dict:
    from .verifier import _set_equal
    checks, errors, unknown, parsed_count, previous, previous_relation = [], [], [], 0, None, None
    bindings = {}
    for number, source in enumerate(steps, 1):
        row_checks, parsed_ok, anchors, relations = [], True, [], []
        try:
            parts, notes = fragments(source)
            row_checks.extend(StepResult('UNSUPPORTED', note) for note in notes)
            if not parts:
                raise Unsupported('No mathematical expression in the step')
            for part in parts:
                relation = _relation(part)
                if relation is not None:
                    relations.append(relation)
                    if previous_relation is not None:
                        equal = _set_equal(previous_relation, relation)
                        row_checks.append(StepResult('VALID' if equal else 'INVALID', 'Exact inequality solution-set comparison') if equal is not None else StepResult('UNSUPPORTED', 'Inequality comparison is inconclusive'))
                    previous_relation = relation
                    continue
                leading = part.startswith('=')
                sides = split_top(part[1:] if leading else part, '=')
                label_left = sides[0] == r'\label'
                label_right = sides[-1] == r'\label'
                if label_left:
                    sides = sides[1:]
                if label_right:
                    sides = sides[:-1]
                values = [parse_latex(s) for s in sides]
                if not values or any(not value.value or value.value.is_equation for value in values):
                    parsed_ok = False
                    reasons = '; '.join(value.reason or 'Expected expression' for value in values if not value.value or value.value.is_equation)
                    row_checks.append(StepResult('UNSUPPORTED', reasons or 'Empty chain', 'PARSE_FAILED'))
                    # Never lose the rest of the independently readable equalities.
                good = [value.value for value in values]
                if leading and previous is not None and good and good[0] is not None:
                    prior = replace(previous, sides=(previous.sides[-1],))
                    row_checks.append(_check_expressions(prior, good[0]))
                elif leading and number > 1:
                    row_checks.append(StepResult('UNSUPPORTED', 'Continuation has no readable predecessor'))
                internal = []
                for index, (left, right) in enumerate(zip(good, good[1:])):
                    if left is None or right is None:
                        continue
                    # The first pair of a non-continuation row can state a
                    # premise/definition. Subsequent equal signs claim identity.
                    a, b = left.sides[0], right.sides[0]
                    if index == 0 and not leading and a.free_symbols:
                        if a in bindings:
                            substituted = replace(left, sides=(bindings[a],))
                            check = _check_expressions(substituted, right)
                        else:
                            check = _check_expressions(left, right)
                            identity_claim = r'\begin{array}' in source
                            if check.status != 'VALID' and not identity_claim:
                                check = StepResult('VALID', 'Symbolic equation is a premise; checked against previous equation when applicable')
                    else:
                        check = _check_expressions(left, right)
                    internal.append(check)
                row_checks.extend(internal)
                if all(good):
                    first, last = good[0], good[-1]
                    if len(good) >= 2 and not leading and not label_left:
                        equation = replace(first, sides=(first.sides[0], last.sides[0]),
                                           constraints=tuple(c for v in good for c in v.constraints),
                                           symbols=tuple(sorted(set(s for v in good for s in v.symbols), key=str)))
                        # Repeated definitions must remain equal. Ordinary
                        # algebraic equations preserve their solution set.
                        if previous is not None and previous.is_equation and equation.symbols and set(previous.symbols) == set(equation.symbols) and len(parts) == 1:
                            try:
                                if sp.simplify(previous.sides[0] - previous.sides[1]) == 0 and sp.simplify(equation.sides[0] - equation.sides[1]) != 0:
                                    row_checks.append(StepResult('UNSUPPORTED', 'Identity to substituted value needs an explicit substitution'))
                                else:
                                    row_checks.append(_compare(previous, equation))
                            except (Unsupported, NotImplementedError, ValueError, TypeError) as error:
                                row_checks.append(StepResult('UNSUPPORTED', str(error)))
                        elif number > 1 and equation.symbols and not isinstance(first.sides[0], sp.Symbol):
                            if _check_expressions(first, last).status != 'VALID':
                                row_checks.append(StepResult('UNSUPPORTED', 'Separate equation/substitution requires task context'))
                        anchors.append(equation)
                        if isinstance(first.sides[0], sp.Symbol) and first.sides[0] not in last.sides[0].free_symbols and all(c.status == 'VALID' for c in internal):
                            bindings[first.sides[0]] = last.sides[0]
                    else:
                        anchors.append(last)
                        if len(good) == 1 and not leading and previous is not None and not previous.is_equation:
                            row_checks.append(_check_expressions(previous, last))
            if not row_checks and number > 1:
                row_checks.append(StepResult('UNSUPPORTED', 'No checkable transition'))
            if len(steps) == 1 and not any(c.reason != 'Symbolic equation is a premise; checked against previous equation when applicable' for c in row_checks):
                row_checks.append(StepResult('UNSUPPORTED', 'Only an unverified symbolic premise'))
        except (Unsupported, ValueError, TypeError, NotImplementedError, RecursionError, ZeroDivisionError) as error:
            row_checks.append(StepResult('UNSUPPORTED', str(error), 'PARSE_FAILED'))
            parsed_ok = False
        if parsed_ok:
            parsed_count += 1
        if any(check.status == 'INVALID' for check in row_checks):
            errors.append(number)
        if any(check.status == 'UNSUPPORTED' for check in row_checks):
            unknown.append(number)
        checks.append({'step': number, 'status': 'INVALID' if number in errors else ('UNSUPPORTED' if number in unknown else 'VALID'),
                       'parse_status': 'OK' if parsed_ok else 'PARSE_FAILED',
                       'reason': '; '.join(dict.fromkeys(c.reason for c in row_checks)) or 'Trusted initial expression',
                       'checks': [c.to_dict() for c in row_checks]})
        previous = anchors[-1] if len(anchors) == 1 else None
    covered = bool(steps) and not unknown and parsed_count == len(steps)
    first = min(errors) if errors else None
    localized = first if first is not None and not any(i < first for i in unknown) else None
    return {'status': ('INVALID' if errors else 'VALID') if covered else 'UNSUPPORTED', 'covered': covered,
            'has_error': True if errors else (False if covered else None), 'first_error_step': localized,
            'parse_status': 'OK' if parsed_count == len(steps) else 'PARSE_FAILED',
            'parsed_steps': parsed_count, 'total_steps': len(steps), 'transitions': checks,
            'reason': 'Checks only written mathematics; symbolic premises, problem statement and omitted conditions are not verified'}
