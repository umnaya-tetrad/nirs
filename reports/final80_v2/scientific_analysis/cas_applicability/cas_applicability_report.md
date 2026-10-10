# Эффективность нейросимвольной архитектуры в области её применимости

## Дизайн и ограничения

Анализ полностью офлайн: использованы frozen final-80 v2 raw-artifacts, canonical GT, CAS diagnostics и независимая доменная разметка. Никаких новых API/CAS-вызовов или изменений исходных результатов не было. Gemini monetary figures — provider-reported Polza usage; GigaChat — tariff estimate. Денежная стоимость локального CAS не измерялась и не включена.

## Доменные результаты

| Область | n | Gemini: coverage / selective accuracy / E2E | GigaChat: coverage / selective accuracy / E2E |
|---|---:|---|---|
| algebraic_expression | 12 | 5/12 (41.7%) / 80.0% / 8/12 (66.7%) | 4/12 (33.3%) / 75.0% / 8/12 (66.7%) |
| arithmetic | 10 | 3/10 (30.0%) / 100.0% / 9/10 (90.0%) | 5/10 (50.0%) / 60.0% / 7/10 (70.0%) |
| calculus | 8 | 1/8 (12.5%) / 100.0% / 6/8 (75.0%) | 1/8 (12.5%) / 100.0% / 4/8 (50.0%) |
| equation | 13 | 2/13 (15.4%) / 0.0% / 9/13 (69.2%) | 4/13 (30.8%) / 75.0% / 11/13 (84.6%) |
| function | 1 | 0/1 (0.0%) / — / 1/1 (100.0%) | 0/1 (0.0%) / — / 0/1 (0.0%) |
| geometry | 15 | 3/15 (20.0%) / 33.3% / 11/15 (73.3%) | 0/15 (0.0%) / — / 9/15 (60.0%) |
| inequality | 1 | 0/1 (0.0%) / — / 1/1 (100.0%) | 0/1 (0.0%) / — / 0/1 (0.0%) |
| linear_algebra | 12 | 2/12 (16.7%) / 50.0% / 8/12 (66.7%) | 1/12 (8.3%) / 100.0% / 4/12 (33.3%) |
| trigonometry | 8 | 1/8 (12.5%) / 0.0% / 6/8 (75.0%) | 1/8 (12.5%) / 0.0% / 1/8 (12.5%) |

Selective accuracy относится только к determinate CAS-выводам. Во всех выводах coverage считается по всем ID домена; domains n=1 остаются описательными.

## Парное сравнение на CAS-covered подмножестве

### gemini: n=17 (условная выборка)

- E2E: 11/17 (64.7%, Wilson [41.3%, 82.7%]); CAS: 10/17 (58.8%, Wilson [36.0%, 78.4%]).
- CAS correct / E2E wrong: 2; CAS wrong / E2E correct: 3; оба correct: 8; оба wrong: 4.
- First-error exact match среди GT incorrect: E2E 3/12, CAS 6/12. Это строгая проверка ID шага и чувствительна к различной сегментации.

### gigachat: n=16 (условная выборка)

- E2E: 13/16 (81.2%, Wilson [57.0%, 93.4%]); CAS: 11/16 (68.8%, Wilson [44.4%, 85.8%]).
- CAS correct / E2E wrong: 2; CAS wrong / E2E correct: 4; оба correct: 9; оба wrong: 1.
- First-error exact match среди GT incorrect: E2E 2/8, CAS 4/8. Это строгая проверка ID шага и чувствительна к различной сегментации.

## Эффективность времени и стоимости

- gemini / all_final80 (n=80): E2E median 14104 ms; Assisted pipeline median 15762 ms; mean paired difference pipeline−E2E 2409 ms; E2E API cost 0.822 ₽/image; Assisted VLM API cost 0.925 ₽/image (provider_reported; CAS local cost excluded).
- gemini / cas_determinate_subset (n=17): E2E median 12634 ms; Assisted pipeline median 14586 ms; mean paired difference pipeline−E2E 2375 ms; E2E API cost 0.663 ₽/image; Assisted VLM API cost 0.800 ₽/image (provider_reported; CAS local cost excluded).
- gigachat / all_final80 (n=80): E2E median 6863 ms; Assisted pipeline median 10593 ms; mean paired difference pipeline−E2E 4528 ms; E2E API cost 1.195 ₽/image; Assisted VLM API cost 1.246 ₽/image (tariff_estimate; CAS local cost excluded).
- gigachat / cas_determinate_subset (n=16): E2E median 6248 ms; Assisted pipeline median 9220 ms; mean paired difference pipeline−E2E 2772 ms; E2E API cost 1.117 ₽/image; Assisted VLM API cost 1.123 ₽/image (tariff_estimate; CAS local cost excluded).

Ни на all-final80, ни на determinate CAS subset не следует заявлять измеренное универсальное преимущество Assisted по latency: полный pipeline включает вызов VLM и CAS. Заявление о денежной экономии возможно только там, где это подтверждает case-level cost и с оговоркой о невключённом локальном CAS.

## Отказы CAS и перспектива расширения

- gemini: dependencies_or_branching: 2/63 (3.2%), parser_limitation: 44/63 (69.8%), task_formalization: 5/63 (7.9%), timeout: 3/63 (4.8%), unsupported_math: 9/63 (14.3%).
- gigachat: parser_limitation: 32/63 (50.8%), task_formalization: 23/63 (36.5%), timeout: 2/63 (3.2%), unsupported_math: 6/63 (9.5%).

`cas_failures_classified.csv` помечает 118/126 отказов `needs_manual_review`: в них H2 сохранил extraction mismatch, поэтому diagnostics не позволяют приписать отказ только CAS/parser. Классификация диагностическая, а не причинная. Только `unsupported_math` является кандидатом на расширение математических правил. `parser_limitation` требует улучшения формального парсинга; `task_formalization` и `dependencies_or_branching` — лучшего TaskSpec/структуры. Даже устранение отказа не гарантирует корректный будущий verdict.

## Вывод

На данных final-80 v2 есть локальные случаи высокой selective accuracy, но при малом coverage и широких Wilson-интервалах. Это демонстрирует область применимости текущего Assisted→Task-aware CAS, но не измеренное преимущество над Direct E2E на всей выборке. Для проверки конкурентоспособности расширенного подхода нужны заранее заданные доменные strata с достаточным n, независимый CAS holdout, измеренная стоимость локального исполнения и повторный фиксированный прогон без отбора по CAS outcome.
