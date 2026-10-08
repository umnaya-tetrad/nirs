import json
from pathlib import Path

import pytest

from evaluator import evaluator
from nirs_cas import analyze_contract, verify_solution
from nirs_cas import oracle


def _write(path, records):
    path.write_text(json.dumps(records), encoding='utf-8')
    return path


def _case(identifier, latex, verdict, first=None):
    return {'id': identifier, 'steps': [{'step_id': f's{i}', 'latex': step} for i, step in enumerate(latex, 1)],
            'verdict': verdict, 'first_error_step': first}


def test_multiple_gt_files_reject_cross_file_duplicate_ids(tmp_path):
    case = _case('case', ['x=1'], 'correct')
    a = _write(tmp_path / 'a.json', [case])
    b = _write(tmp_path / 'b.json', [case])
    with pytest.raises(evaluator.EvaluationInputError, match='duplicate GT id'):
        evaluator.load_gt([a, b])


def test_malformed_prediction_record_does_not_crash_loader(tmp_path):
    path = _write(tmp_path / 'predictions.json', [None, 4, [], 'bad', {}])
    valid, invalid, count = evaluator.load_predictions(path)
    assert valid == {}
    assert len(invalid) == count == 5


def test_oracle_array_is_consumable_by_evaluator_with_two_gt_files(tmp_path, monkeypatch):
    cases = [_case('good', ['2x=4', 'x=2'], 'correct'),
             _case('bad', ['2x=4', 'x=3'], 'incorrect', 's2')]
    a = _write(tmp_path / 'dev.json', [cases[0]])
    b = _write(tmp_path / 'final.json', [cases[1]])
    seen = []
    def check(latex, timeout):
        seen.append(latex)
        return dict(verify_solution(latex), latency_ms=0, wall_ms=0)
    monkeypatch.setattr(oracle, 'run_isolated', check)
    monkeypatch.setattr(evaluator, 'run_isolated', check)
    output = tmp_path / 'oracle'
    oracle.run_oracle([a, b], output, workers=1)
    report = evaluator.evaluate([a, b], output / 'predictions.json')
    assert report['summary']['solution']['verdict_accuracy'] == 1
    assert report['summary']['first_error']['first_error_accuracy'] == 1
    assert report['summary']['cas']['coverage'] == 1
    assert report['predictions']['evaluated'] == 2
    assert len(report['gt']['sources']) == 2
    assert seen == [['2x=4', 'x=2'], ['2x=4', 'x=3']] * 2


def test_missing_and_indeterminate_answers_remain_in_denominator(tmp_path, monkeypatch):
    cases = [_case('missing', ['x=1'], 'correct'),
             _case('unknown', [r'\unknown{x}'], 'incorrect', 's1')]
    gt = _write(tmp_path / 'gt.json', cases)
    prediction = analyze_contract(cases[1], timeout=None)
    path = _write(tmp_path / 'predictions.json', [prediction])
    monkeypatch.setattr(evaluator, 'run_isolated', lambda latex, timeout: verify_solution(latex))
    report = evaluator.evaluate(gt, path)
    assert report['summary']['solution']['verdict_accuracy'] == 0
    assert report['summary']['first_error']['indeterminate'] == 1
    assert [row['status'] for row in report['cases']] == ['missing', 'ok']
