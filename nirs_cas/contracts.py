"""Canonical output adapter; only written LaTeX is passed to the verifier."""
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

import sympy as sp

from .adapter import extract_step_latex
from .benchmark import run_isolated
from .verifier import verify_solution
from .task_spec import compile_task_spec
from .parser import parse_latex
from .context_rules import check_context


def _context_verdict(spec):
    """Return an exact task-level result or a documented abstention.

    The rules are deliberately small.  They certify only an equality that is
    completely parsed by SymPy; textual answers, trig families and matrices
    without a complete exact parser remain abstentions.
    """
    if spec['compilation']['status'] != 'supported':
        return None, '; '.join(spec['compilation']['reasons'])
    if spec['compilation']['task_class'] not in {'equation', 'expression'}:
        return None, f"{spec['compilation']['task_class']} checker needs a more specific exact parser"
    parsed_givens = [g['parse'] for g in spec['task']['givens']]
    usable = [g['value'] for g in parsed_givens if g['status'] == 'OK']
    if len(usable) != 1:
        return None, 'requires exactly one exact parsed given'
    given = usable[0]
    try:
        left, right = [sp.sympify(value) for value in given['sides']]
    except Exception:
        return None, 'could not reconstruct exact SymPy given'
    symbols = sorted((left - right).free_symbols, key=str)
    # Find a wholly parseable recorded equality whose right side is a claimed
    # answer.  This does not reinterpret prose or repair OCR.
    candidate = None
    for step in reversed(spec['steps']):
        parsed = parse_latex(step['latex'])
        if parsed.status == 'OK' and parsed.value and parsed.value.is_equation:
            candidate = (step['step_id'], parsed.value)
            break
    if candidate is None:
        return None, 'no exact answer equality in recorded steps'
    step_id, answer = candidate
    if symbols and len(symbols) == 1:
        variable = symbols[0]
        if answer.sides[0] != variable and answer.sides[1] != variable:
            return None, 'answer equality does not isolate the task variable'
        claimed = answer.sides[1] if answer.sides[0] == variable else answer.sides[0]
        residual = sp.simplify((left - right).subs(variable, claimed))
        return (False, step_id, 'candidate does not satisfy the exact task equation') if residual != 0 else (True, step_id, 'candidate satisfies the exact task equation')
    if not symbols:
        # A numerical evaluation is certified only if the last equality has
        # the exact task expression on one side and its exact value on other.
        if sp.simplify(answer.sides[0] - left) == 0 and sp.simplify(answer.sides[1] - right) == 0:
            return True, step_id, 'exact evaluation matches the task expression'
        return None, 'recorded equality is not an exact restatement of task evaluation'
    return None, 'multiple task variables are unsupported by the first contour'


def analyze_contract(input_contract, repo_root=None, *, timeout=10, result=None):
    """Accept GT SolutionAnalysis, OCR MathCoreInput or a runner artifact.

    Verdict, kinds/graph, hints and corrections cannot influence the check.
    IDs map output to the input order. timeout=None is for trusted local tests.
    """
    latex = extract_step_latex(input_contract)
    source = input_contract.get('contract', input_contract)
    identifiers = [s.get('step_id', f's{i}') for i, s in enumerate(source['steps'], 1)]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError('Duplicate step IDs')
    steps = [{k: v for k, v in step.items() if k in {'step_id', 'kind', 'latex', 'derives_from'}} for step in source['steps']]
    for i, step in enumerate(steps):
        step.setdefault('step_id', identifiers[i])
        step.setdefault('kind', 'initial' if i == 0 else 'step')
    started = perf_counter()
    if result is None:
        result = run_isolated(latex, timeout) if timeout is not None else verify_solution(latex)
    duration = round((perf_counter() - started) * 1000)
    first = result['first_error_step']
    # The canonical incorrect contract requires a localized first error.
    verdict = 'incorrect' if result['has_error'] is True and first is not None else ('correct' if result['covered'] and result['has_error'] is False else 'indeterminate')
    transitions = {t['step']: t for t in result['transitions']}
    findings, reviewed = [], []
    for index, (step_id, text) in enumerate(zip(identifiers, latex), 1):
        transition = transitions.get(index)
        status = transition['status'] if transition else ('INVALID' if first == index else ('VALID' if result['covered'] else 'UNSUPPORTED'))
        reason = transition['reason'] if transition else result['reason']
        if status == 'INVALID' and verdict == 'indeterminate':
            reviewed.append({'step_id': step_id, 'verdict': 'indeterminate', 'note': 'Найдено неверное равенство, но первая ошибка не установлена: ' + reason})
        elif status == 'INVALID':
            finding_id = f'f{len(findings) + 1}'
            findings.append({'finding_id': finding_id, 'step_id': step_id, 'error_code': 'algebra', 'severity': 'error',
                             'message': 'Символьная проверка обнаружила неверное равенство или переход.',
                             'explanation': reason, 'confidence': 1.0, 'detected_by': 'math_core',
                             'evidence': {'check': reason, 'actual_latex': text, 'engine': 'sympy'}})
            reviewed.append({'step_id': step_id, 'verdict': 'error', 'finding_ids': [finding_id]})
        elif status == 'UNSUPPORTED':
            reviewed.append({'step_id': step_id, 'verdict': 'indeterminate', 'note': reason})
        else:
            reviewed.append({'step_id': step_id, 'verdict': 'correct', 'note': reason})
    output = {'schema_version': '1.0', 'id': source['id'], 'steps': steps,
              'pipeline': {'approach': 'llm_ocr_plus_math_core', 'stages': [
                  {'name': 'transcribe', 'backend': source.get('meta', {}).get('model', 'ground-truth'), 'status': 'ok'},
                  {'name': 'verify', 'backend': f'sympy@{sp.__version__}', 'status': 'ok', 'duration_ms': duration}]},
              'verdict': verdict, 'is_correct': None if verdict == 'indeterminate' else verdict == 'correct',
              'first_error_step': identifiers[first - 1] if first is not None and verdict == 'incorrect' else None,
              'last_correct_step': identifiers[first - 2] if first is not None and first > 1 and verdict == 'incorrect' else None,
              'findings': findings, 'steps_reviewed': reviewed,
              'meta': {'run_id': f'cas-{uuid4()}', 'approach': 'llm_ocr_plus_math_core', 'stage': 'verify',
                       'model': f'sympy@{sp.__version__}', 'duration_ms': duration,
                       'created_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), 'tool_versions': {'sympy': sp.__version__}}}
    if repo_root is not None:
        from nirs_llm.contracts import validate_contract
        validate_contract(output, 'solution_analysis', repo_root)
    return output


def analyze_assisted_contract(input_contract, repo_root=None, *, timeout=10, result=None):
    """CAS analysis with an explicit TaskSpec context branch.

    This is intentionally not a replacement for :func:`analyze_contract`.
    Local symbolic transition checks are reused verbatim; the context only
    permits extra validation where TaskSpec compiled an exact task.  When it
    did not, the run abstains instead of manufacturing a mathematical label.
    """
    source = input_contract.get("contract", input_contract)
    spec = compile_task_spec(source)
    local = analyze_contract(source, repo_root=None, timeout=timeout, result=result)
    task_class = spec["compilation"]["task_class"]
    reasons = list(spec["compilation"]["reasons"])
    task_class = spec["compilation"]["task_class"]
    if task_class in {"matrix_system", "determinant", "definite_integral", "inequality", "trigonometric", "function_operation", "expression"}:
        context = check_context(spec)
        contextual = {"VALID": True, "INVALID": False, "UNSUPPORTED": None}[context.status]
        step_id, context_reason, rule = context.step_id, context.reason, context.rule
    else:
        contextual, context_reason = _context_verdict(spec)
        step_id, rule = None, task_class
    prior_unknown = False
    if step_id:
        position = [s['step_id'] for s in local['steps']].index(step_id)
        prior_unknown = any(review.get('verdict') == 'indeterminate' for review in local['steps_reviewed'][:position])
    if contextual is False and local["verdict"] != "incorrect" and step_id and not prior_unknown:
        local["verdict"] = "incorrect"
        local["is_correct"] = False
        local["first_error_step"] = step_id
        position = [s['step_id'] for s in local['steps']].index(step_id)
        local["last_correct_step"] = local['steps'][position - 1]['step_id'] if position else None
        finding_id = f"f{len(local['findings']) + 1}"
        local['findings'].append({'finding_id': finding_id, 'step_id': step_id, 'error_code': 'task_context', 'severity': 'error',
                                  'message': 'Ответ не удовлетворяет точно распознанному условию.', 'explanation': context_reason,
                                  'confidence': 1.0, 'detected_by': 'math_core', 'evidence': {'check': context_reason, 'rule': rule, 'engine': 'sympy'}})
    elif contextual is True and local["verdict"] == "indeterminate" and all(step.get("role") == "answer" for step in source["steps"]):
        # Independent answer branches (for example f±g, fg and f/g) do not
        # form a linear equality chain. If every branch is exactly checked
        # against the task, the graph itself is a complete proof.
        local["verdict"] = "correct"
        local["is_correct"] = True
        local["first_error_step"] = None
        local["last_correct_step"] = source["steps"][-1]["step_id"]
        local["steps_reviewed"] = [{"step_id": step["step_id"], "verdict": "correct", "note": f"exact assisted graph rule: {rule}"} for step in source["steps"]]
    elif contextual is None or (contextual is False and prior_unknown):
        # Context is additive evidence, not a stricter replacement for the
        # legacy local verifier. An unavailable exact task rule must never
        # turn an otherwise established local result into indeterminate.
        note = context_reason or "; ".join(reasons) or "TaskSpec has no exact context rule"
        local["steps_reviewed"].append({"step_id": source["steps"][-1]["step_id"], "verdict": "indeterminate", "note": f"assisted context unavailable: {note}"})
    context_status = "valid" if contextual is True else ("invalid" if contextual is False else "unsupported")
    local["problem"] = {"task_spec": spec, "context_check": {"status": context_status, "rule": rule, "reason": context_reason, "step_id": step_id, "localization_blocked": prior_unknown}}
    approach = "llm_assisted_extraction_plus_math_core"
    local["pipeline"] = {"approach": approach, "stages": [
        {"name": "extract_context", "backend": source.get("meta", {}).get("model", "gemini"), "status": "ok"},
        {"name": "compile_task_spec", "backend": "nirs_cas.task_spec@1.0", "status": "ok"},
        {"name": "verify", "backend": f"sympy@{sp.__version__}", "status": "ok"},
    ]}
    local["meta"]["approach"] = approach
    local["meta"]["stage"] = "verify"
    if repo_root is not None:
        from nirs_llm.contracts import validate_contract
        validate_contract(local, "solution_analysis", repo_root)
    return local
