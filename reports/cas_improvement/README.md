# Проверка доработок CAS на GT и сохранённом OCR

Модели и prompts не менялись; новые VLM-запросы не запускались. Ordinary остаётся режимом по умолчанию.

| Вход / режим | Полное покрытие | Вынесен вердикт | Вердикт совпал с GT, от всех | Первая ошибка, только GT incorrect | Сигналы ошибки на GT correct |
|---|---:|---:|---:|---:|---:|
| ordinary_gt100 | 42.0% | 63.0% | 51.0% | 51.4% (70 ошибочных GT) | 10 |
| exact_gt100 | 45.0% | 58.0% | 50.0% | 54.3% (70 ошибочных GT) | 6 |
| exact_gt_dev20 | 40.0% | 45.0% | 40.0% | 55.6% (9 ошибочных GT) | 2 |
| exact_ocr_dev20 | 35.0% | 40.0% | 40.0% | 22.2% (9 ошибочных GT) | 3 |

Проверяется согласованность написанной математики относительно начальной предпосылки. Условие задачи в GT не передано: полнота ответа и пропущенные условия не доказаны.
Сигнал ошибки (`has_error=true`) может существовать без установленной первой ошибки. Канонический вердикт тогда остаётся indeterminate; доказанные шаги доступны отдельно в known_error_step_ids.
Совпадение со всеми GT-метками не гарантируется. Например, пропущенная подстановка или выбор положительного корня может требовать отсутствующего условия задачи. Расхождения нужно разбирать по доказательству, а не исправлять по метке.
Все 100 использовались для исследовательской разработки. Для независимой оценки нужна новая выборка. Строгая метрика первой ошибки зависит от разбиения строк и сравнивает исходные step_id.

Изменения по примерам и причины отказа находятся в comparison.json; полные проверки — в ordinary_gt100.json и exact_gt100.json.

| Изменившийся пример | GT | Вердикт до → после | Полное покрытие до → после |
|---|---|---|---|
| img_96_pert_2.1 | incorrect | incorrect → indeterminate | False → False |
| img_136_pert_2.2 | incorrect | indeterminate → indeterminate | False → False |
| img_19_pert_5.1 | correct | indeterminate → indeterminate | False → False |
| img_494_pert_5.1 | correct | incorrect → correct | False → True |
| img_387_pert_5.1 | correct | incorrect → indeterminate | False → False |
| img_22_pert_5.1 | correct | indeterminate → indeterminate | False → False |
| img_494_pert_3.1 | incorrect | incorrect → incorrect | False → True |
| img_172_pert_3.2 | incorrect | correct → indeterminate | True → False |
| img_35_pert_2.5 | incorrect | incorrect → indeterminate | False → False |
| img_395_pert_2.5 | incorrect | incorrect → indeterminate | False → False |
| img_494_pert_2.5 | incorrect | incorrect → incorrect | False → True |
| img_463_pert_1.3 | incorrect | incorrect → incorrect | False → True |
| img_96_pert_1.4 | incorrect | incorrect → indeterminate | False → False |
| img_176_pert_4.3 | correct | indeterminate → correct | False → True |
| img_112_pert_4.4 | incorrect | indeterminate → incorrect | False → False |
| img_529_pert_4.5 | incorrect | correct → indeterminate | True → False |
| img_194_pert_1.5 | incorrect | incorrect → incorrect | False → False |

## Assisted regression and mixed engineering set

Assisted dev-20: полное покрытие 45%, точность verdict 55%, первая ошибка 11.1%. Результаты метрик не изменились относительно backlog.
Mixed-20: полное покрытие 30%; проверка ответа по условию 70% (было 50%). Ответы 4 из 7 тригонометрических задач теперь проверяются, все их промежуточные шаги по-прежнему не покрыты.
Mixed-20 не имеет GT-оценок: 70% — покрытие проверки ответа, а не точность.
Подробности: [assisted dev-20](assisted_dev20/comparison.md), [mixed-20](mixed20/mixed_coverage.md), [validation.json](validation.json).
GT-100: точность verdict среди вынесенных оценок выросла с 81.0% до 86.2%, но доля вынесенных оценок упала с 63% до 58%. Точность verdict на всех — 51% → 50%. Новый режим остаётся opt-in.
