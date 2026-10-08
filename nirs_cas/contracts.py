"""Canonical output adapter; only written LaTeX is passed to the verifier."""
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

import sympy as sp

from .adapter import extract_step_latex
from .benchmark import run_isolated
from .verifier import verify_solution


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
