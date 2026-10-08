# Evaluator

Сравнивает системные выходы `SolutionAnalysis` с эталоном (`dataset/test_gt.json`) и выгружает метрики в JSON и CSV.

## Вход

- `--gt` — один или несколько файлов с JSON-массивами `SolutionAnalysis` (по умолчанию `dataset/test_gt.json`); вердикты только `correct`/`incorrect`. ID должны быть уникальны во всех файлах.
- `--predictions` — JSON-массив `SolutionAnalysis` с выводом системы (обязательный аргумент).

Записи сопоставляются по `id`. Запись без корректного `verdict` (например, `MathCoreInput` из режима extraction) помечается `invalid`, отсутствующий `id` — `missing`; обе ситуации входят в знаменатели accuracy как несовпадение. `id` из GT отсутствуют в predictions → `extra` перечисляются в отчёте и не влияют на метрики.

## Запуск

```sh
python evaluator/evaluator.py --predictions outputs/run.json
python evaluator/evaluator.py --predictions outputs/run.json --gt dataset/test_gt.json \
    --output-dir reports/evaluation --timeout 10
python -m evaluator.evaluator --gt dataset/test_gt.json dataset/final_gt.json \
    --predictions reports/cas_gt_100/predictions.json --output-dir reports/local/evaluation
```

| Параметр | По умолчанию | Смысл |
|---|---|---|
| `--predictions` | обязателен | файл с выходами системы |
| `--gt` | `dataset/test_gt.json` | эталон |
| `--output-dir` | `reports/evaluation` | куда писать отчёт |
| `--timeout` | `10` | таймаут процесса CAS на кейс, сек |

Тот же код доступен как модуль: `from evaluator.evaluator import evaluate, write_outputs`.

## Метрики

- **verdict accuracy** — доля совпадений `verdict` системы и GT по всем GT-кейсам (`verdict_accuracy_on_evaluated` — только по успешно выгруженным записям).
- **step accuracy** — попунктное сравнение `steps_reviewed` по `step_id`: на каждой паре шагов (union обоих наборов) считается совпадение вердикта; по всем кейсам, где у обеих сторон есть `steps_reviewed` (отсутствие ответа системы даёт 0). Записи без `steps_reviewed` исключаются.
- **solution accuracy** — строгое совпадение: одинаковый `verdict` **и** все пошаговые вердикты идентичны (признак `solution_match`).
- **first error accuracy** — по GT-кейсам `incorrect`: `first_error_step` системы равен эталону; отдельно считаются причины промаха: `wrong_index`, `no_error_reported`, `indeterminate`, `missing_or_invalid`.
- **CAS coverage / parse rate** — `verify_solution` из `nirs_cas` прогоняется на **шагах системы** (изолированный процесс, таймаут `--timeout`); coverage — доля кейсов, полностью разобранных и проверенных; parse rate — доля кейсов, у которых все шаги разобраны. Кейсы без валидного ответа остаются в знаменателе (`NOT_RUN`/`NOT_MEASURED`).
- **confusion matrix** — строки GT (`correct`, `incorrect`) × столбцы система (`correct`, `incorrect`, `indeterminate`, `missing`); `missing` объединяет отсутствующие и невалидные записи.

## Выходные файлы

В `--output-dir` создаются три файла:

- `report.json` — полный отчёт: метаданные входов (пути, SHA-256), версия SymPy, таймаут, `summary` со всеми метриками и матрицей путаницы, построчные `cases`.
- `results.csv` — по одному ряду на GT-кейс: `id, status, note, gt_verdict, gt_first_error_step, pred_verdict, pred_first_error_step, verdict_match, step_agreements, step_union, step_accuracy, solution_match, first_error_match, first_error_category, cas_status, cas_covered, cas_parse_status, cas_parsed_steps, cas_total_steps`.
- `confusion_matrix.csv` — та же матрица в виде таблицы `gt \ system`.

Краткая сводка (accuracy, coverage, пути файлов) печатается в stdout.
