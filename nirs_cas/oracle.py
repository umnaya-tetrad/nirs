"""Process-isolated GT oracle and saved OCR→CAS runs, with abstentions in totals."""
import csv
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import statistics

import sympy

from .adapter import extract_step_latex
from .benchmark import run_isolated
from .contracts import analyze_contract


def load_records(paths):
    records, sources, ids = [], [], set()
    for path in paths:
        path = Path(path)
        raw = path.read_bytes()
        data = json.loads(raw.decode('utf-8-sig'))
        items = data if isinstance(data, list) else data['items'] if isinstance(data, dict) and isinstance(data.get('items'), list) else [data]
        sources.append({'path': path.as_posix(), 'sha256': hashlib.sha256(raw).hexdigest()})
        for item in items:
            extract_step_latex(item)
            identifier = item.get('contract', item).get('id')
            if not isinstance(identifier, str) or not identifier or identifier in ids:
                raise ValueError('Every input must have a unique, nonempty id')
            ids.add(identifier)
            records.append(item.get('contract', item))
    return records, sources


def summarize(rows):
    total = len(rows)
    covered = [r for r in rows if r['covered']]
    decidable = [r for r in rows if r['has_error'] is not None]
    labelled = [r for r in rows if 'expected_has_error' in r]
    labelled_covered = [r for r in labelled if r['covered']]
    labelled_decidable = [r for r in labelled if r['has_error'] is not None]
    def accuracy(selected, field, expected):
        return sum(r[field] == r[expected] for r in selected) / len(selected) if selected else None
    def first_accuracy(selected):
        return sum(r['has_error'] == r['expected_has_error'] and r['first_error_step_id'] == r['expected_first_error_step'] for r in selected) / len(selected) if selected else None
    times = [r['latency_ms'] for r in rows if r.get('latency_ms') is not None]
    confusion = Counter((str(r['expected_has_error']), str(r['has_error'])) for r in labelled)
    reasons = Counter(t['reason'] for r in rows for t in r['transitions'] if t['status'] == 'UNSUPPORTED')
    errors = [r for r in labelled if r['expected_has_error']]
    return {'examples': total, 'covered_examples': len(covered), 'coverage': len(covered) / total if total else 0,
            'decidable_has_error_examples': len(decidable),
            'parseable_examples': sum(r['parse_status'] == 'OK' for r in rows),
            'parsed_steps': sum(r.get('parsed_steps') or 0 for r in rows),
            'total_steps': sum(r['total_steps'] for r in rows),
            'has_error_accuracy_all': accuracy(labelled, 'has_error', 'expected_has_error'),
            'has_error_accuracy_on_covered': accuracy(labelled_covered, 'has_error', 'expected_has_error'),
            'has_error_accuracy_on_decidable': accuracy(labelled_decidable, 'has_error', 'expected_has_error'),
            'first_error_accuracy_all': first_accuracy(labelled),
            'first_error_accuracy_on_incorrect': first_accuracy(errors),
            'first_error_accuracy_on_covered': first_accuracy(labelled_covered),
            'canonical_verdict_accuracy_all': accuracy(labelled, 'verdict', 'expected_verdict'),
            'confusion_has_error': {f'gt={a},cas={b}': count for (a, b), count in sorted(confusion.items())},
            'timeouts_or_worker_errors': sum(r['parse_status'] == 'NOT_MEASURED' for r in rows),
            'mean_latency_ms': statistics.mean(times) if times else None,
            'unsupported_reasons': dict(reasons.most_common())}


def run_oracle(paths, output, *, timeout=10, workers=4, split_name='exploratory_gt', mode='ordinary'):
    if mode not in {'ordinary', 'exact'}:
        raise ValueError('mode must be ordinary or exact')
    if workers < 1 or workers > 16:
        raise ValueError('workers must be between 1 and 16')
    if timeout <= 0:
        raise ValueError('timeout must be positive')
    records, sources = load_records(paths)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'predictions').mkdir(exist_ok=True)
    def check(item):
        if mode == 'exact':
            from .written_exact import run_exact_isolated
            result = run_exact_isolated(extract_step_latex(item), timeout)
        else:
            result = run_isolated(extract_step_latex(item), timeout)
        if mode == 'exact':
            from .contracts import analyze_exact_contract
            canonical = analyze_exact_contract(item, result=result)
        else:
            canonical = analyze_contract(item, result=result)
        step_ids = [s.get('step_id', f's{i}') for i, s in enumerate(item['steps'], 1)]
        first = result['first_error_step']
        row = {'id': item['id'], **result, 'verdict': canonical['verdict'],
               'first_error_step_id': step_ids[first - 1] if first is not None else None}
        # Reference labels are accessed strictly after the CAS result exists.
        if item.get('verdict') in {'correct', 'incorrect'}:
            row.update(expected_verdict=item['verdict'], expected_has_error=item['verdict'] == 'incorrect',
                       expected_first_error_step=item.get('first_error_step'))
        return row, canonical
    with ThreadPoolExecutor(max_workers=workers) as executor:
        checked = list(executor.map(check, records))
    rows = [row for row, _ in checked]
    # Fixed numbered paths avoid interpreting user-provided IDs as filesystem paths.
    for index, (_, canonical) in enumerate(checked, 1):
        (output / 'predictions' / f'{index:04}.json').write_text(json.dumps(canonical, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'predictions.json').write_text(json.dumps([canonical for _, canonical in checked], ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    report = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'backend': 'sympy',
              'sympy_version': sympy.__version__, 'python_version': platform.python_version(),
              'evaluation': split_name, 'mode': mode, 'sources': sources, 'timeout_seconds': timeout, 'workers': workers,
              'input_projection': 'steps[].latex only, original order', 'summary': summarize(rows), 'results': rows}
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    columns = ['id', 'status', 'covered', 'parse_status', 'has_error', 'verdict', 'first_error_step_id', 'expected_verdict', 'expected_first_error_step', 'parsed_steps', 'total_steps', 'latency_ms', 'wall_ms']
    with (output / 'results.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    summary = report['summary']
    def percent(value):
        return '—' if value is None else f'{value:.1%}'
    lines = ['# CAS на эталонном распознавании', '', f"Режим: {split_name}. Только `steps[].latex`; GT labels используются после проверки.", '',
             f"Полное покрытие: {summary['covered_examples']}/{len(rows)} ({percent(summary['coverage'])}).",
             f"Разобрано шагов: {summary['parsed_steps']}/{summary['total_steps']}; все шаги разобраны у {summary['parseable_examples']} решений.",
             f"Точность has_error на всех: {percent(summary['has_error_accuracy_all'])}; на покрытых: {percent(summary['has_error_accuracy_on_covered'])}.",
             f"Точность first_error_step на всех: {percent(summary['first_error_accuracy_all'])}; только на ошибочных GT: {percent(summary['first_error_accuracy_on_incorrect'])}.", '',
             'Отказы и таймауты остаются в знаменателе. Независимое свидетельство ошибки не означает полного покрытия. При неизвестном более раннем шаге первая ошибка не локализуется.',
             'Проверяется согласованность записанной математики. Условие задачи, пропущенные подстановки, выбор ветви и полнота ответа не поступают в CAS.',
             'После доработок по этим 100 примерам результат является исследовательским прогоном, а не независимым holdout.', '',
             '| ID | CAS | Coverage | GT | Первая ошибка CAS | Первая ошибка GT |', '|---|---|---|---|---|---|']
    lines.extend(f"| {r['id']} | {r['verdict']} | {r['covered']} | {r.get('expected_verdict', '—')} | {r['first_error_step_id']} | {r.get('expected_first_error_step', '—')} |" for r in rows)
    (output / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return report
