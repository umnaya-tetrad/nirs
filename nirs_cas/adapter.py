"""One label-free projection shared by GT, E2E and OCR outputs."""
from typing import Any


def extract_step_latex(contract: dict[str, Any]) -> list[str]:
    """Read only steps[].latex, in original order; never GT labels or corrections.

    Runner artifacts may wrap the canonical contract under ``contract``.
    """
    if not isinstance(contract, dict):
        raise ValueError('Expected a JSON object')
    if 'contract' in contract:
        contract = contract['contract']
    if not isinstance(contract, dict) or not isinstance(contract.get('steps'), list) or not contract['steps']:
        raise ValueError('Expected a nonempty steps array')
    result = []
    for index, step in enumerate(contract['steps']):
        if not isinstance(step, dict) or not isinstance(step.get('latex'), str) or not step['latex'].strip():
            raise ValueError(f'steps[{index}].latex must be a nonempty string')
        result.append(step['latex'])
    return result
