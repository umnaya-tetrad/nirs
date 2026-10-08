from copy import deepcopy
import pytest

from nirs_cas import extract_step_latex, verify_solution, analyze_contract
from nirs_cas.oracle import summarize


def test_only_step_latex_is_projected_and_order_preserved():
    record = {'id': 'case', 'steps': [
        {'step_id': 's2', 'latex': '2x=4', 'kind': 'note'},
        {'step_id': 's1', 'latex': 'x=3', 'transformation': {'rule_hint': 'x=2'}}],
        'verdict': 'correct', 'findings': [{'latex': 'x=2'}], 'corrected_solution': [{'latex': 'x=2'}]}
    assert extract_step_latex(record) == ['2x=4', 'x=3']
    assert extract_step_latex({'contract': record}) == ['2x=4', 'x=3']
    assert analyze_contract(record, timeout=None)['first_error_step'] == 's1'


def test_gt_labels_hints_and_step_graph_cannot_leak_into_verification():
    record = {'id': 'case', 'steps': [{'step_id': 's1', 'latex': '2x=4'}, {'step_id': 's2', 'latex': 'x=3'}],
              'verdict': 'incorrect', 'first_error_step': 's2'}
    changed = deepcopy(record)
    changed.update(id='unrelated', verdict='correct', is_correct=True, first_error_step=None,
                   findings=[{'message': 'Correct'}], corrected_solution=[{'latex': 'x=2'}],
                   reading={'ambiguous_step_ids': ['s1']})
    for step in changed['steps']:
        step.update(kind='note', derives_from=[], transformation={'rule_hint': 'assume x=3'})
    assert verify_solution(extract_step_latex(record)) == verify_solution(extract_step_latex(changed))


@pytest.mark.parametrize('record', [None, [], {}, {'steps': []}, {'steps': ['x=1']}, {'steps': [{'latex': ''}]}, {'steps': [{'latex': None}]}])
def test_bad_steps_are_rejected_instead_of_silently_filtered(record):
    with pytest.raises(ValueError):
        extract_step_latex(record)


def test_abstentions_stay_in_accuracy_denominator():
    rows = [dict(covered=False, has_error=None, parse_status='PARSE_FAILED', parsed_steps=0, total_steps=1,
                 transitions=[], verdict='indeterminate', first_error_step_id=None,
                 expected_verdict='correct', expected_has_error=False, expected_first_error_step=None)]
    summary = summarize(rows)
    assert summary['coverage'] == 0
    assert summary['has_error_accuracy_all'] == 0
    assert summary['has_error_accuracy_on_covered'] is None
