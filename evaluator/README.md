# Evaluator

Сравнивает системные выходы `SolutionAnalysis` с эталоном (`dataset/test_gt.json`) и выгружает метрики в JSON и CSV.

В пакете два инструмента: пофайловый `cases` (ниже) и эксперимент `experiment`
(H1/H2/H3 по `evaluator_task.md`, см. раздел «Эксперимент»).

## Вход

- `--gt` — один или несколько файлов с JSON-массивами `SolutionAnalysis` (по умолчанию `dataset/test_gt.json`); вердикты только `correct`/`incorrect`. ID должны быть уникальны во всех файлах.
- `--predictions` — JSON-массив `SolutionAnalysis` с выводом системы (обязательный аргумент).

Записи сопоставляются по `id`. Запись без корректного `verdict` (например, `MathCoreInput` из режима extraction) помечается `invalid`, отсутствующий `id` — `missing`; обе ситуации входят в знаменатели accuracy как несовпадение. `id` из GT отсутствуют в predictions → `extra` перечисляются в отчёте и не влияют на метрики.

## Запуск (`cases`)

Единая точка входа для обоих инструментов — `python -m evaluator {cases,experiment}`:

```sh
python -m evaluator cases --predictions outputs/run.json
python -m evaluator cases --predictions outputs/run.json --gt dataset/test_gt.json \
    --output-dir reports/evaluation --timeout 10
python -m evaluator cases --gt dataset/test_gt.json dataset/final_gt.json \
    --predictions reports/cas_gt_100/predictions.json --output-dir reports/local/evaluation
```

Те же вызовы доступны напрямую: `python evaluator/evaluator.py ...` или
`python -m evaluator.evaluator ...`.

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

## Эксперимент (H1–H3)

Отдельный, manifest-driven инструмент сравнивает несколько заморожённых прогонов
(`e2e`, `extraction_cas`, `assisted_cas`) на одном наборе ID и считает гипотезы:

- **H1** — парное сравнение сквозного `e2e` и `extraction→CAS` для одного провайдера: accuracy,
  coverage, selective risk, confusion, McNemar exact и парный bootstrap-доверительный интервал; строго проверяется совпадение наборов ID в паре.
- **H2** — качество OCR и его влияние: нормализация LaTeX, выравнивание шагов (difflib),
  token edit distance и таксономия ошибок (`digit`, `sign`, `exponent`, `variable`, `operator`, `structure`, `missed_line`, `extra_line`, `segmentation`, `ambiguous`); сравнение CAS на OCR-шагах с baseline CAS на GT-шагах.
- **H3** — selective automation: политики `e2e_only`, `cas_only`, `disagreement_routing`
  (совпали — автоматизируем, разошлись или отказ — в ручную), accuracy/automation и risk-coverage.

Ошибки `api_failed`, `invalid_contract` и отсутствующие записи всегда остаются в знаменателе
и никогда не считаются верными; `indeterminate` — явный отказ системы. Провенанс (sha256 файлов,
`prompt_sha256` через `nirs_llm.prompts`, `git_commit`, `contract_sha256` бандлов) проверяется до расчётов.

```sh
PYTHONPATH=. python -m evaluator experiment \
    --manifest evaluator/manifests/dev20_demo.json \
    --output-dir reports/evaluation_dev20_demo
```

Или напрямую: `from evaluator.experiment import run_experiment`.

### Манифест

`manifest_version`, `experiment_id`, `evaluation_note` (`exploratory`/`final`), `dataset`
(`split`, `gt_paths`, `ids`, необязательный `cas_on_gt`), `error_policy`, `runs` и `h1_pairs`.
Каждый run: `run_id`, `system` (`e2e`/`extraction_cas`/`assisted_cas`), `provider`, `mode`, `model`,
`prompt_version`, `prompt_sha256`, `git_commit`, `timestamp`, `simulated`, `source`
(`kind`: `runner_artifacts` / `solution_analysis_array` / `bundle` / `json_key`, `path`, `key`),
необязательные `extraction_artifacts` (бандл MathCoreInput для H2) и `pricing`. Пути — относительно корня репозитория.

`evaluator/manifests/dev20_demo.json` — демонстрационный манифест: реальные extraction→CAS
(из `reports/assisted_cas/dev20/comparison.json`), baseline `reports/cas_gt_100/predictions.json`
и **симулированный** e2e (`evaluator/fixtures/e2e_simulated_dev_20.json`, флаг `simulated: true`,
регенерируется `python evaluator/fixtures/simulate_e2e.py`) для провайдера gemini.

Каждый source и связанный extraction-бандл обязаны содержать **ровно полный набор ID** из
`dataset.ids` manifest. Неполный запуск не может быть случайно выдан за парный эксперимент.
`evaluation_note: "final"` запрещает simulated runs; exploratory-отчёт с ними получает явную
пометку, что он не готов для научного результата.

Для extraction→CAS latency разложена на `mean_vlm_latency_ms`, `mean_cas_latency_ms` и
`mean_pipeline_latency_ms` (сумма компонентов). H3 считает agreement только среди двух
decidable verdicts: `UNSUPPORTED`/timeout/indeterminate CAS направляются в ручную очередь, но
не считаются содержательным disagreement. В отчёт добавлены error-rate ручной очереди и recall
захваченных ошибочных E2E-решений.

### Выходные файлы

`report.json` (полный отчёт с провенансом), `cases.csv`, `h1_paired.csv`, `h2_ocr.csv`,
`h3_routing.csv`, `report.md`. Прогон на dev-20 исследовательский: CAS и промпты настраивались
на всех 100 GT, поэтому это не независимый holdout.
