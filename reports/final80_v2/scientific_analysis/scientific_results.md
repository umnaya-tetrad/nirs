# Результаты экспериментального исследования: final-80 v2

## Статус и источники

Анализ выполнен офлайн по canonical GT, frozen VLM artifacts, CAS diagnostics и итоговому evaluator report. Новые API-вызовы, изменения CAS, GT, prompts и состава final-80 v2 не выполнялись. Эксперимент остаётся PARTIAL: `img_488_pert_5.1` не имеет валидного GigaChat Assisted-контракта и учитывается как technical missing, а не как CAS abstention.

## Основное сравнение маршрутов

| Маршрут | Валидные VLM | Correct determinate / 80 | Coverage | Selective accuracy |
|---|---:|---:|---:|---:|
| Gemini E2E | 80/80 | 73.8% | 100.0% | 73.8% |
| Gemini Assisted → Task-aware CAS | 80/80 | 12.5% | 21.2% | 58.8% |
| GigaChat E2E | 80/80 | 55.0% | 100.0% | 55.0% |
| GigaChat Assisted → Task-aware CAS | 79/80 | 13.8% | 20.0% | 68.8% |

Direct E2E имеет более высокую all-ID эффективность: Gemini 73.8% против 12.5% у Assisted→CAS, GigaChat 55.0% против 13.8%. Это не следует трактовать как доказательство математической ненадёжности каждого indeterminate случая: основное ограничение Assisted-маршрута — coverage около 20–21%, а не низкая selective accuracy на покрытых случаях.

## H1 — разбор исходов Assisted→CAS

### gemini

| Исход CAS | Число | E2E верен |
|---|---:|---:|
| CAS correct determinate | 10 | 8 |
| CAS wrong determinate | 7 | 3 |
| CAS indeterminate | 63 | 48 |
| API/contract missing | 0 | 0 |

Содержательное совпадение двух определённых вердиктов: 12/17 (70.6%). Показатель correctness-outcome agreement over all IDs (33.8%) — другая GT-зависимая величина и не используется как agreement для H3.

### gigachat

| Исход CAS | Число | E2E верен |
|---|---:|---:|
| CAS correct determinate | 11 | 9 |
| CAS wrong determinate | 5 | 4 |
| CAS indeterminate | 63 | 30 |
| API/contract missing | 1 | 1 |

Содержательное совпадение двух определённых вердиктов: 10/16 (62.5%). Показатель correctness-outcome agreement over all IDs (53.8%) — другая GT-зависимая величина и не используется как agreement для H3.

## H2 — ошибки извлечения и границы CAS

Частоты extraction-классов и CAS diagnostics доступны в CSV. Причина конкретного неверного CAS-вердикта не назначается автоматически: совпадение OCR-класса и отказа CAS — диагностический сигнал, а не доказательство причинности. Например, точная транскрипция может оставаться indeterminate из-за интегралов, дифференцирования, незафиксированной цели или timeout.

### gemini: распределение ошибок Assisted Extraction

| Класс | Случаев | Доля | Финальный CAS-вердикт неверен/неопределён |
|---|---:|---:|---:|
| extra_line | 30 | 37.5% | 86.7% |
| segmentation | 17 | 21.2% | 88.2% |
| missed_line | 12 | 15.0% | 100.0% |
| exact | 10 | 12.5% | 70.0% |
| ambiguous | 5 | 6.2% | 100.0% |
| variable | 3 | 3.8% | 100.0% |
| operator | 2 | 2.5% | 50.0% |
| digit | 1 | 1.2% | 100.0% |

Частоты диагностических причин среди indeterminate (один ID учитывается не более одного раза для одной причины):

| Причина | Случаев |
|---|---:|
| Prose/conditions are not a fully parsed mathematical step | 44 |
| At least one node/edge proof is unresolved | 29 |
| Task has no explicit mathematical target | 16 |
| Continuation requires one readable dependency | 9 |
| Unanchored mathematical statement | 6 |
| requires two explicit X/Y matrix equations | 6 |
| Bare word is not an exact mathematical token | 5 |
| Requires one task equation | 5 |
| A written answer equality is required | 4 |
| Requires one explicit inequality | 4 |

### gigachat: распределение ошибок Assisted Extraction

| Класс | Случаев | Доля | Финальный CAS-вердикт неверен/неопределён |
|---|---:|---:|---:|
| extra_line | 35 | 43.8% | 85.7% |
| segmentation | 28 | 35.0% | 89.3% |
| missed_line | 8 | 10.0% | 87.5% |
| ambiguous | 3 | 3.8% | 100.0% |
| exact | 2 | 2.5% | 50.0% |
| variable | 2 | 2.5% | 100.0% |
| operator | 1 | 1.2% | 0.0% |
| transcription_error | 1 | 1.2% | 100.0% |

Частоты диагностических причин среди indeterminate (один ID учитывается не более одного раза для одной причины):

| Причина | Случаев |
|---|---:|
| Unanchored mathematical statement | 27 |
| At least one node/edge proof is unresolved | 23 |
| Task has no explicit mathematical target | 20 |
| Bare word is not an exact mathematical token | 16 |
| Prose/conditions are not a fully parsed mathematical step | 12 |
| goal is unknown | 12 |
| Continuation requires one readable dependency | 8 |
| requires two explicit X/Y matrix equations | 8 |
| OCR exactness is not exact | 6 |
| Requires one explicit inequality | 5 |

### Наиболее показательные случаи

#### gemini — `img_455_pert_5.1`

- Категория: CAS wrong determinate; GT `correct`, E2E `correct`, CAS `incorrect`.
- GT: `2A-B=2\begin{bmatrix}1&2&3\\2&3&1\end{bmatrix}-\begin{bmatrix}3&-1&3\\-1&0&2\end{bmatrix} | =X\begin{bmatrix}1&2&3\\2&3&1\end{bmatrix}+\begin{bmatrix}-3&1&-3\\1&0&-2\end{bmatrix} | =\begin{bmatrix}a-3&4+1&6-3\\4+1&6+0&2-2\end{bmatrix} | =\begin{bmatrix}-1&5&3\\5&6&0\end{bmatrix}`
- Assisted steps: `2A-B = 2\begin{bmatrix} 1 & 2 & 3 \\ 2 & 3 & 1 \end{bmatrix} - \begin{bmatrix} 3 & -1 & 3 \\ -1 & 0 & 2 \end{bmatrix} | = \begin{bmatrix} 1 & 2 & 3 \\ 2 & 3 & 1 \end{bmatrix} + \begin{bmatrix} -3 & 1 & -3 \\ 1 & 0 & -2 \end{bmatrix} | = \begin{bmatrix} 2-3 & 4+1 & 6-3 \\ 4+1 & 6+0 & 2-2 \end{bmatrix} | = \begin{bmatrix} -1 & 5 & 3 \\ 5 & 6 & 0 \end{bmatrix}`
- TaskSpec: `{"visibility": "visible", "raw_latex": "\\text{Question: If } A = \\begin{bmatrix} 1 & 2 & 3 \\\\ 2 & 3 & 1 \\end{bmatrix} \\text{ and } B = \\begin{bmatrix} 3 & -1 & 3 \\\\ -1 & 0 & 2 \\end{bmatrix}. \\text{ Then find } 2A-B.", "givens": [{"given_id": "g1", "latex": "A = \\begin{bmatrix} 1 & 2 & 3 \\\\ 2 & 3 & 1 \\end{bmatrix}"}, {"given_id": "g2", "latex": "B = \\begin{bmatrix} 3 & -1 & 3 \\\\ -1 & 0 & 2 \\end{bma…`
- OCR/TaskSpec class: `segmentation` / `reported_structured`.
- CAS diagnostics: `Requires explicit X+Y and X-Y matrix givens | Continuation requires one readable dependency | Continuation requires one readable dependency | Continuation requires one readable dependency | requires two explicit X/Y matrix equations`
- Интерпретация: Ложный определённый CAS-вердикт. Saved extraction и canonical GT расходятся в промежуточном элементе матрицы; CAS также фиксирует недостающие matrix bindings. Это показывает mismatch представления/проверки, но для отнесения причины к OCR, GT или CAS требуется проверка фотографии.

#### gemini — `img_108_pert_1.4`

- Категория: CAS wrong determinate; GT `incorrect`, E2E `correct`, CAS `correct`.
- GT: `\sin \frac{31\pi}{3} = \sin\left(10\pi + \frac{\pi}{3}\right) = \sin \left( \pi - \frac{\pi}{3} \right) = \sin \left( \frac{2\pi}{3} \right) = \frac{\sqrt{3}}{2}.`
- Assisted steps: `\sin\frac{31\pi}{3} = \sin\left(10\pi + \frac{\pi}{3}\right) = \sin\left(\pi - \frac{\pi}{3}\right) | = \sin\left(\frac{2\pi}{3}\right) = \frac{\sqrt{3}}{2}`
- TaskSpec: `{"visibility": "visible", "raw_latex": "\\text{Question : Find the value of }\\sin\\frac{31\\pi}{3}.", "goal": {"type": "evaluate", "target_latex": "\\sin\\frac{31\\pi}{3}"}}`
- OCR/TaskSpec class: `extra_line` / `reported_structured`.
- CAS diagnostics: `—`
- Интерпретация: Ложный определённый CAS-вердикт. Тригонометрическая цепочка имеет тот же финальный результат, что GT, но GT помечает решение как incorrect. Артефакты не позволяют отделить принятие неверного перехода CAS от проблемы GT/фото; нужна ручная проверка.

#### gemini — `img_529_pert_4.5`

- Категория: CAS wrong determinate; GT `incorrect`, E2E `incorrect`, CAS `correct`.
- GT: `y + 1 = 3 \quad \text{and} \quad x - 2 = 1. | y = 2 \quad \text{and} \quad x = 3.`
- Assisted steps: `y+1=3 \text{ and } x-2=1 | y=2 \text{ and } x=3`
- TaskSpec: `{"visibility": "visible", "raw_latex": "\\text{Question: If }(x+1, y-2)=(3,1), \\text{ Find the values of }x\\text{ and }y.", "givens": [{"given_id": "g1", "latex": "(x+1, y-2)=(3,1)"}], "goal": {"type": "solve", "target_latex": "x, y"}}`
- OCR/TaskSpec class: `segmentation` / `reported_structured`.
- CAS diagnostics: `Prose/conditions are not a fully parsed mathematical step | Prose/conditions are not a fully parsed mathematical step | Unsupported input at character 4`
- Интерпретация: Ложный определённый CAS-вердикт. Задача с упорядоченной парой извлечена в те же два уравнения, что canonical GT, но CAS даёт correct при GT=incorrect. Это семантическое расхождение TaskSpec/проверки, а не доказанная OCR-причина.

#### gemini — `img_77_pert_5.1`

- Категория: CAS wrong determinate; GT `correct`, E2E `correct`, CAS `incorrect`.
- GT: `R=\frac{9.8}{2}=4.9 | \pi R^2=\frac{22}{7}(4.9)^2=\frac{22}{7}\times4.9\times4.9=75.46`
- Assisted steps: `\text{Diameter, } D = 9.8\text{ m . Therefore, radius } R = \frac{9.8}{2} = 4.9\text{ m} | \text{Area of the circle} = \pi R^2 = \frac{22}{7} \times (4.9)^2\text{ m}^2 = \frac{22}{7} \times 4.9 \times 4.9\text{ m}^2 | = 75.46\text{ m}^2`
- TaskSpec: `{"visibility": "visible", "raw_latex": "\\text{Question : Diameter of a circular garden is } 9.8\\text{ m . Find its area.}", "givens": [{"given_id": "g1", "latex": "D = 9.8\\text{ m}"}], "goal": {"type": "evaluate", "target_latex": "\\text{Area}"}}`
- OCR/TaskSpec class: `missed_line` / `reported_structured`.
- CAS diagnostics: `Prose/conditions are not a fully parsed mathematical step | Prose/conditions are not a fully parsed mathematical step | Prose/conditions are not a fully parsed mathematical step | Unsupported token '\\text'`
- Интерпретация: Ложный определённый CAS-вердикт. Extraction разворачивает запись в строки с прозой и имеет класс missed-line. Diagnostics содержат ошибки разбора прозы; единственную причину неверного финального вердикта без просмотра изображения назначать нельзя.

#### gemini — `img_78_pert_5.1`

- Категория: CAS wrong determinate; GT `correct`, E2E `incorrect`, CAS `incorrect`.
- GT: `4\pi a^2=4\times\frac{22}{7}\times a\times a=616`
- Assisted steps: `4\pi a^2 = 4 \times \frac{22}{7} \times a \times a\text{ cm}^2 = 616\text{ cm}^2`
- TaskSpec: `{"visibility": "visible", "raw_latex": "\\text{Question : Find the surface area of a sphere of radius } 7\\text{ cm.}", "givens": [{"given_id": "g1", "latex": "r = 7\\text{ cm}"}], "goal": {"type": "evaluate", "target_latex": "\\text{surface area of a sphere}"}}`
- OCR/TaskSpec class: `missed_line` / `reported_structured`.
- CAS diagnostics: `Prose/conditions are not a fully parsed mathematical step | Unsupported token '\\text'`
- Интерпретация: Ложный определённый CAS-вердикт с missed-line extraction и unsupported-text diagnostics. Он совместим с влиянием recognition/normalisation на проверку, но данные не доказывают, что это единственная причина вердикта.

#### gemini — `img_400_pert_5.1`

- Категория: CAS indeterminate; GT `correct`, E2E `correct`, CAS `indeterminate`.
- GT: `\log z = x \log a | \frac{1}{z} \frac{dz}{dx} = \log a | \frac{dz}{dx} = z \log a | \frac{d}{dx}(a^x) = a^x \log a`
- Assisted steps: `z = a^x | \log z = x \log a | \frac{1}{z} \frac{dz}{dx} = \log a | \frac{dz}{dx} = z \log a | \frac{d}{dx}(a^x) = a^x \log a`
- TaskSpec: `{"visibility": "visible", "raw_latex": "\\text{Question: Differentiate } a^x \\text{ w.r.t. } x\\text{, where } a \\text{ is a positive constant.}", "goal": {"type": "compute_function", "target_latex": "\\frac{d}{dx}(a^x)"}, "constraints": ["a > 0"]}`
- OCR/TaskSpec class: `extra_line` / `reported_structured`.
- CAS diagnostics: `Symbolic exponent requires a constant positive base | At least one node/edge proof is unresolved | Differential notation needs a calculus verifier | Differential notation needs a calculus verifier | Differential notation needs a calculus verifier | Differential notation needs a calculus verifier`
- Интерпретация: Indeterminate при структурированном TaskSpec: diagnostics явно требуют постоянное положительное основание и оставляют граф зависимостей неразрешённым. Это подтверждённое ограничение области/предпосылок CAS, а не свидетельство ошибки ученика.

#### gemini — `img_374_pert_5.1`

- Категория: CAS indeterminate; GT `correct`, E2E `correct`, CAS `indeterminate`.
- GT: `I = \int_0^{\pi} \frac{u \sin u}{1 + \cos^2 u} \, du. | I = \int_0^{\pi} \frac{(\pi - u) \sin(\pi - u)}{1 + \cos^2(\pi - u)} \, du | = \int_0^{\pi} \frac{(\pi - u) \sin u}{1 + \cos^2 u} \, du = \pi \int_0^{\pi} \frac{\sin u}{1 + \cos^2 u} \, du - I. | 2I = \pi \int_0^{\pi} \frac{\sin u}{1 + \cos^2 u} \, du | I = \frac{\pi}{2} \int_0^{\pi} \frac{\sin u}{1 + \cos^2 u} \, du. | I = \frac{\pi}{2} \int_{-1}^{1} \frac{dt}{1 + t^2} = \frac{\pi}{2} \cdot \frac{\pi}{2} = \frac{\pi^2}{4}.`
- Assisted steps: `I = \int_{0}^{\pi} \frac{u \sin u}{1 + \cos^2 u} \, du | I = \int_{0}^{\pi} \frac{(\pi - u) \sin(\pi - u)}{1 + \cos^2(\pi - u)} \, du | = \int_{0}^{\pi} \frac{(\pi - u) \sin u}{1 + \cos^2 u} \, du = \pi \int_{0}^{\pi} \frac{\sin u}{1 + \cos^2 u} \, du - I | 2I = \pi \int_{0}^{\pi} \frac{\sin u}{1 + \cos^2 u} \, du | I = \frac{\pi}{2} \int_{0}^{\pi} \frac{\sin u}{1 + \cos^2 u} \, du | \text{Put } \cos u = t \text{ so that } -\sin u \, du = dt. \text{ when } u=0, t=1 \text{ and when } u=\pi, t=-1. \text{ Therefore, we get} | I = \frac{\pi}{2} \int_{-1}^{1} \frac{dt}{1 + t^2} = \frac{\pi}{2} \cdot \frac{\pi}{2} = \frac{\pi^2}{4}`
- TaskSpec: `{"visibility": "visible", "raw_latex": "\\text{Question: Evaluate } I = \\int_{0}^{\\pi} \\frac{x \\sin x}{1 + \\cos^2 x} \\, dx.", "givens": [{"given_id": "g1", "latex": "I = \\int_{0}^{\\pi} \\frac{x \\sin x}{1 + \\cos^2 x} \\, dx"}], "goal": {"type": "evaluate", "target_latex": "I"}}`
- OCR/TaskSpec class: `extra_line` / `reported_structured`.
- CAS diagnostics: `Unsupported token '\\int' | Unsupported token '\\int' | Unsupported token '\\int' | Unsupported token '\\int' | Unsupported token '\\int' | Prose/conditions are not a fully parsed mathematical step | Differential notation needs a calculus verifier | definite integral with explicit bounds was not found`
- Интерпретация: Indeterminate при почти полной extraction определённого интеграла. Diagnostics явно не поддерживают интегральную нотацию; это ограничение области CAS, а не наблюдаемая ошибка транскрипции.

#### gemini — `img_98_pert_2.1`

- Категория: CAS indeterminate; GT `incorrect`, E2E `incorrect`, CAS `indeterminate`.
- GT: `\cos^2 A + \sin^2 A = 1, | \cos^2 A = 1 - \sin^2 A, \text{ i.e., } \cos A = \pm (1 - \sin^2 A) | \cos A = 1 - \sin^2 A. | \tan A = \frac{\sin A}{\cos A} = \frac{\sin A}{1 - \sin^2 A} | \sec A = \frac{1}{\cos A} = \frac{1}{1 - \sin^2 A}.`
- Assisted steps: `\cos^2 A + \sin^2 A = 1 | \cos^2 A = 1 - \sin^2 A, \text{ i.e., } \cos A = \pm(1 - \sin^2 A) | \cos A = 1 - \sin^2 A | \tan A = \frac{\sin A}{\cos A} = \frac{\sin A}{1 - \sin^2 A} | \sec A = \frac{1}{\cos A} = \frac{1}{1 - \sin^2 A}`
- TaskSpec: `{"visibility": "visible", "raw_latex": "\\text{Question :- Express the ratios } \\cos A, \\tan A, \\text{ and } \\sec A \\text{ in terms of } \\sin A.", "goal": {"type": "simplify", "target_latex": "\\cos A, \\tan A, \\sec A"}}`
- OCR/TaskSpec class: `exact` / `reported_structured`.
- CAS diagnostics: `TIMEOUT_OR_WORKER_EXIT | TIMEOUT_OR_WORKER_EXIT | TIMEOUT_OR_WORKER_EXIT | TIMEOUT_OR_WORKER_EXIT | TIMEOUT_OR_WORKER_EXIT | TIMEOUT_OR_WORKER_EXIT`
- Интерпретация: Exact extraction, но indeterminate из-за сохранённых diagnostics TIMEOUT_OR_WORKER_EXIT. Кейс показывает, что точный LaTeX сам по себе не гарантирует CAS coverage.

#### gigachat — `img_190_pert_3.2`

- Категория: CAS wrong determinate; GT `incorrect`, E2E `incorrect`, CAS `correct`.
- GT: `\frac{4.2 \times 3.8 \times 7.6}{3} = 5.2.`
- Assisted steps: `\frac{4.2 + 3.8 + 7.6}{3} | \frac{15.6}{3} | 5.2`
- TaskSpec: `{"visibility": "visible", "raw_latex": "Find the average of 4.2, 3.8 and 7.6.", "goal": {"type": "compute_function", "target_latex": "\\operatorname{average}"}}`
- OCR/TaskSpec class: `extra_line` / `reported_structured`.
- CAS diagnostics: `Unanchored mathematical statement | A written answer equality is required`
- Интерпретация: Сильный пример влияния recognition: GT содержит произведение в расчёте среднего, а extraction использует сумму и получает 5.2. CAS принимает извлечённую цепочку, хотя GT помечает исходное решение incorrect. Фото может подтвердить исходную нотацию.

#### gigachat — `img_387_pert_5.1`

- Категория: CAS indeterminate; GT `correct`, E2E `incorrect`, CAS `indeterminate`.
- GT: `\frac{dz}{du} = 3u^2 + \sec^2 u | \frac{d^2 z}{du^2} = \frac{d}{du} (3u^2 + \sec^2 u) = 6u + 2 \sec u \tan u`
- Assisted steps: `\frac{dy}{du}=3u^2+sec^2 u | \frac{d^2x}{du^2}=\frac{d}{(3u^2+sec^2 u)}=6u+2 sec u tan u`
- TaskSpec: `{"visibility": "visible", "raw_latex": "Find \\frac{d^2y}{dx^2}, if y = x^3 + tan x."}`
- OCR/TaskSpec class: `segmentation` / `missing_goal`.
- CAS diagnostics: `Differential notation needs a calculus verifier | Differential notation needs a calculus verifier | goal is unknown`
- Интерпретация: Indeterminate с TaskSpec класса missing_goal и diagnostics, требующими calculus verifier. Наблюдаются и структурная неполнота, и неподдерживаемая математическая область; их индивидуальный вклад неразделим.

#### gigachat — `img_65_pert_5.1`

- Категория: CAS indeterminate; GT `correct`, E2E `correct`, CAS `indeterminate`.
- GT: `\sqrt{(u-3)^2+(v-4)^2+(w+5)^2}=\sqrt{(u+2)^2+(v-1)^2+(w-4)^2} | (u-3)^2+(v-4)^2+(w+5)^2=(u+2)^2+(v-1)^2+(w-4)^2 | 10u+6v-18w-29=0`
- Assisted steps: `\sqrt{(u-3)^2+(v-4)^2+(w+5)^2}= \sqrt{(u+2)^2+(v-1)^2+(w-4)^2} | ( u - 3 ) ^ 2 + ( v - 4 ) ^ 2 + ( w + 5 ) ^ 2 = ( u + 2 ) ^ 2 + ( v - 1 ) ^ 2 + ( w - 4 ) ^ 2 | 10u + 6v - 18w - 29 = 0`
- TaskSpec: `{"visibility": "visible", "raw_latex": "Find the equation of the set of points P such that its distances from the point A ( 3 , 4 , − 5 ) and B ( − 2 , 1 , 4 ) are equal.", "goal": {"type": "unknown"}}`
- OCR/TaskSpec class: `exact` / `reported_structured`.
- CAS diagnostics: `Unanchored mathematical statement | At least one node/edge proof is unresolved | goal is unknown`
- Интерпретация: Exact step transcription, но indeterminate. Diagnostics фиксируют unanchored statement/unknown goal: это ограничение привязки TaskSpec даже без найденного step-level OCR mismatch.

#### gigachat — `img_488_pert_5.1`

- Категория: API/contract missing; GT `correct`, E2E `correct`, CAS `missing_or_failed`.
- GT: `z+2y=3 | z=3-2y | 7(3-2y)-15y=2 | 21-14y-15y=2 | 21-29y=2 | -29y=-19 | y=\frac{19}{29} | z=3-2\left(\frac{19}{29}\right)=\frac{49}{29} | z=\frac{49}{29},\quad y=\frac{19}{29}`
- Assisted steps: `— (contract missing)`
- TaskSpec: `null`
- OCR/TaskSpec class: `transcription_error` / `missing_extraction`.
- CAS diagnostics: `—`
- Интерпретация: Технический contract failure, а не математический abstention: повторный output содержал пустое обязательное поле target_latex. Он остаётся missing в all-denominator metrics и не считается CAS indeterminate.

#### gigachat — `img_592_pert_5.1`

- Категория: CAS wrong determinate; GT `correct`, E2E `correct`, CAS `incorrect`.
- GT: `y^2+7y+10=(y+2)(y+5) | y+2=0\ \text{or}\ y+5=0,\quad y=-2\ \text{or}\ y=-5 | -2+(-5)=-7=-\frac{7}{1} | (-2)(-5)=10=\frac{10}{1}`
- Assisted steps: `y^2+7y+10=(y+2)(y+5) | (y+2)(y+5)=0 | y=-2 \lor y=-5 | \text{Sum of zeros}=-2+(-5)=-7=-rac{	ext{Coefficient of }y}{	ext{Coefficient of }y^2} | \text{Product of zeros}=(-2)\times (-5)=10=\frac{	ext{Constant term}}{	ext{Coefficient of }y^2}`
- TaskSpec: `{"visibility": "visible", "raw_latex": "Question: Find the roots of the quadratic polynomial x^2 + 7x + 10 and verify the relationship between the zeros and the coefficients.", "goal": {"type": "solve", "target_latex": "x"}}`
- OCR/TaskSpec class: `segmentation` / `reported_structured`.
- CAS diagnostics: `Unsupported token '\\lor' | Prose/conditions are not a fully parsed mathematical step | Prose/conditions are not a fully parsed mathematical step | Bare word is not an exact mathematical token`
- Интерпретация: Ложный определённый CAS-вердикт с segmentation error и unsupported logical/prose diagnostics. Артефакты подтверждают mismatch представления, но для установления первопричины нужна визуальная проверка.

## H3 — нейросимвольная маршрутизация

| Провайдер | Политика | Автоматически | Вручную | Accuracy авто | Ошибки E2E: авто | Ошибки E2E: вручную | Captured error recall |
|---|---|---:|---:|---:|---:|---:|---:|
| gemini | disagreement_only | 75/80 (93.8%) | 5/80 | 74.7% | 19 | 2 | 9.5% |
| gemini | disagreement_or_cas_indeterminate | 12/80 (15.0%) | 68/80 | 66.7% | 4 | 17 | 81.0% |
| gigachat | disagreement_only | 74/80 (92.5%) | 6/80 | 54.1% | 34 | 2 | 5.6% |
| gigachat | disagreement_or_cas_indeterminate | 10/80 (12.5%) | 70/80 | 90.0% | 1 | 35 | 97.2% |

Для GigaChat missing Assisted output маршрутизируется в ручную очередь политикой `disagreement_or_cas_indeterminate`; он не становится математическим CAS abstention. Политика `disagreement_only` не отправляет обычные CAS abstentions человеку, поэтому обладает высокой автоматизацией, но низкой долей захваченных ошибок E2E.

## Выводы для НИРС

1. На данном final-80 Direct E2E превосходит текущий Assisted→Task-aware CAS по all-ID эффективности у обоих провайдеров; это статистически подтверждено парным McNemar тестом в frozen evaluator report.
2. Assisted→CAS имеет умеренную/высокую accuracy среди покрытых решений, но покрывает лишь около одной пятой набора; поэтому selective accuracy нельзя выдавать за accuracy всей системы.
3. Большая доля indeterminate документирует ограничения поддерживаемого CAS-подмножества и TaskSpec anchoring, а не автоматически ошибки ученика или OCR.
4. Есть подтверждённый пример распознавания, способный изменить проверку (`img_190_pert_3.2`); для большинства других несоответствий доступных данных недостаточно, чтобы отделить OCR, GT и CAS как единственную причину.
5. H3 поддерживает использование CAS-indeterminate как триггера для ручной проверки: строгая политика захватывает 81.0% Gemini и 97.2% GigaChat ошибок E2E, но снижает автоматизацию до 15.0% и 12.5% соответственно.
6. При 16–17 определённых CAS-вердиктах интервальные и class-conditional оценки нестабильны; результаты о balanced accuracy/F1 CAS следует подавать как описательные, а не как широкое сравнение математических областей.
7. H1 поддерживает преимущество E2E в текущем контуре; H2 частично поддерживается диагностически; H3 поддерживается как trade-off coverage/risk, а не как доказательство причинной надёжности disagreement без ручной верификации.

## Воспроизводимость

Все строки этой записки выводимы из `main_comparison.csv`, `h1_cas_outcomes.csv`, `assisted_extraction_errors.csv`, `cas_indeterminate_reasons.csv`, `h3_policy_details.csv`, `diagnostic_cases.csv` и frozen report/raw artifacts. Исходный экспериментальный архив не изменялся.

## Анализ эффективности методов по математическим областям

Это дополнительный **exploratory analysis**, выполненный постфактум по независимой sidecar-разметке. Разметка не использовалась при выборе final-80 v2, в VLM/CAS не передавалась и не меняет frozen raw-эксперимент.

| Область | n | GT correct / incorrect | Gemini E2E | Gemini CAS coverage; selective accuracy | GigaChat E2E | GigaChat CAS coverage; selective accuracy |
|---|---:|---:|---:|---:|---:|---:|
| algebraic_expression | 12 | 4 / 8 | 66.7% (8/12) | 41.7% (5/12); 80.0% | 66.7% (8/12) | 33.3% (4/12); 75.0% |
| arithmetic | 10 | 3 / 7 | 90.0% (9/10) | 30.0% (3/10); 100.0% | 70.0% (7/10) | 50.0% (5/10); 60.0% |
| calculus | 8 | 4 / 4 | 75.0% (6/8) | 12.5% (1/8); 100.0% | 50.0% (4/8) | 12.5% (1/8); 100.0% |
| equation | 13 | 10 / 3 | 69.2% (9/13) | 15.4% (2/13); 0.0% | 84.6% (11/13) | 30.8% (4/13); 75.0% |
| function | 1 | 0 / 1 | 100.0% (1/1) | 0.0% (0/1); — | 0.0% (0/1) | 0.0% (0/1); — |
| geometry | 15 | 11 / 4 | 73.3% (11/15) | 20.0% (3/15); 33.3% | 60.0% (9/15) | 0.0% (0/15); — |
| inequality | 1 | 1 / 0 | 100.0% (1/1) | 0.0% (0/1); — | 0.0% (0/1) | 0.0% (0/1); — |
| linear_algebra | 12 | 6 / 6 | 66.7% (8/12) | 16.7% (2/12); 50.0% | 33.3% (4/12) | 8.3% (1/12); 100.0% |
| trigonometry | 8 | 0 / 8 | 75.0% (6/8) | 12.5% (1/8); 0.0% | 12.5% (1/8) | 12.5% (1/8); 0.0% |

`function` and `inequality` each have n=1, so their percentages are descriptive only.

### Наблюдения

- Gemini Assisted CAS имеет наибольшее coverage в `algebraic_expression` (5/12, 41.7%) и `arithmetic` (3/10, 30.0%); GigaChat — в `arithmetic` (5/10, 50.0%) и `algebraic_expression` (4/12, 33.3%). Это наблюдаемая связь, не доказательство, что именно домен вызывает coverage.
- На `geometry` GigaChat Assisted не дал ни одного определённого вердикта (0/15), Gemini дал 3/15; на `calculus` и `trigonometry` оба провайдера дали по 1/8 или меньше. Диагностика связывает многие отказы с unsupported notation, unresolved dependencies и отсутствующей явной целью, а не только с доменом.
- При достаточном количестве определённых ответов selective accuracy может быть высокой (например, Gemini arithmetic 3/3), но знаменатель мал и не заменяет coverage. В `equation` Gemini имеет 2/13 coverage и 0/2 selective accuracy; поэтому нельзя говорить о приемлемой совместной эффективности этого маршрута.
- Direct E2E превосходит Assisted correct-determinate/all во всех многокейсных доменах данного набора. Разница особенно заметна в geometry/calculus/trigonometry, однако доменные группы малы и пересекаются с особенностями записи и TaskSpec.
- Feature-level таблица `domain_feature_extraction_errors.csv` показывает совместное распределение классов extraction и фичей. Дроби, матрицы, интегралы и тригонометрические функции часто сосуществуют с indeterminate, но по этим observational данным нельзя приписывать им причинность: одна и та же запись может иметь несколько features и структурную проблему TaskSpec.

Основные причины fallback по каждому domain/provider и конкретные ID приведены в `domain_cas_failure_reasons.csv`; это позволяет проверить каждое обобщение на case-level artifacts.
