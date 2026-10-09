# Gemini dev-20: ordinary OCR→CAS vs assisted context→TaskSpec→CAS

| Режим | Verified solution coverage | Indeterminate | Verdict accuracy | First-error accuracy |
|---|---:|---:|---:|---:|
| ordinary | 40% | 45% | 50% | 22% |
| assisted | 45% | 45% | 55% | 11% |

Task-aware coverage assisted: 55% (9 exact-valid, 2 exact-invalid, 9 unsupported).
Verified solution coverage означает проверку всех записанных шагов и рёбер. Частично покрытое решение с локализованной ошибкой может получить incorrect и не войти в coverage.
First-error accuracy считается только на GT incorrect; отказ не считается правильной локализацией. Сравнение ID строгое и зависит от совпадения сегментации OCR и GT.
Ordinary local verdict сохраняется отдельно. Context unavailable не отменяет локальное доказательство; корректный финал не доказывает неподдержанные шаги.
Только FERMAT dev-20. Mixed-20 — инженерный набор без GT-оценки. final-80 для этих правил не запускался.

| Task class | Examples | Assisted verified coverage | Task-aware coverage |
|---|---:|---:|---:|
| definite_integral | 1 | 0% | 100% |
| determinant | 3 | 67% | 100% |
| equation | 3 | 33% | 33% |
| expression | 7 | 43% | 43% |
| function_operation | 2 | 100% | 100% |
| inequality | 1 | 0% | 0% |
| matrix_system | 1 | 100% | 100% |
| trigonometric | 2 | 0% | 0% |

Причины indeterminate (один пример может иметь несколько):
- At least one node/edge proof is unresolved: 4
- Task has no explicit mathematical target: 2
- Prose/conditions are not a fully parsed mathematical step: 5
- Symbolic determinant template has no explicit entry bindings: 1
- Continuation requires one readable dependency: 2
- Unsupported token '\\int': 1
- Unsupported input at character 0: 1
- Unsupported token '\\dots': 1
- Quadrant prose is not an explicit mathematical constraint: 1
- Unsupported token '\\pm': 2
- Unanchored mathematical statement: 1
- Unsupported token '\\text': 1
- Differential notation needs a calculus verifier: 1
- Requires one task equation: 1
- Unsupported input at character 8: 1
