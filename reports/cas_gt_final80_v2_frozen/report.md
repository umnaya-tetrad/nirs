# CAS на эталонном распознавании

Режим: final80_v2_gt_frozen. Только `steps[].latex`; GT labels используются после проверки.

Полное покрытие: 27/80 (33.8%).
Разобрано шагов: 223/292; все шаги разобраны у 52 решений.
Точность has_error на всех: 42.5%; на покрытых: 74.1%.
Точность first_error_step на всех: 33.8%; только на ошибочных GT: 46.3%.

Отказы и таймауты остаются в знаменателе. Независимое свидетельство ошибки не означает полного покрытия. При неизвестном более раннем шаге первая ошибка не локализуется.
Проверяется согласованность записанной математики. Условие задачи, пропущенные подстановки, выбор ветви и полнота ответа не поступают в CAS.
После доработок по этим 100 примерам результат является исследовательским прогоном, а не независимым holdout.

| ID | CAS | Coverage | GT | Первая ошибка CAS | Первая ошибка GT |
|---|---|---|---|---|---|
| img_400_pert_5.1 | indeterminate | False | correct | None | None |
| img_374_pert_5.1 | indeterminate | False | correct | None | None |
| img_19_pert_5.1 | indeterminate | False | correct | None | None |
| img_559_pert_5.1 | correct | True | correct | None | None |
| img_464_pert_5.1 | correct | True | correct | None | None |
| img_387_pert_5.1 | incorrect | False | correct | s2 | None |
| img_22_pert_5.1 | indeterminate | False | correct | None | None |
| img_568_pert_5.2 | incorrect | True | correct | s1 | None |
| img_482_pert_5.2 | indeterminate | False | correct | None | None |
| img_559_pert_5.2 | indeterminate | False | correct | None | None |
| img_448_pert_5.2 | indeterminate | False | correct | None | None |
| img_173_pert_5.3 | correct | True | correct | None | None |
| img_165_pert_5.3 | incorrect | False | correct | s3 | None |
| img_193_pert_5.3 | correct | True | correct | None | None |
| img_375_pert_5.3 | indeterminate | False | correct | None | None |
| img_233_pert_3.2 | incorrect | True | incorrect | s1 | s1 |
| img_190_pert_3.2 | incorrect | True | incorrect | s1 | s1 |
| img_559_pert_3.2 | incorrect | True | incorrect | s1 | s1 |
| img_172_pert_3.2 | correct | True | incorrect | None | s2 |
| img_586_pert_3.2 | incorrect | True | incorrect | s2 | s2 |
| img_448_pert_3.2 | indeterminate | False | incorrect | None | s5 |
| img_173_pert_2.5 | incorrect | True | incorrect | s1 | s1 |
| img_35_pert_2.5 | incorrect | False | incorrect | s1 | s2 |
| img_375_pert_2.5 | indeterminate | False | incorrect | None | s4 |
| img_574_pert_2.5 | indeterminate | False | incorrect | None | s6 |
| img_395_pert_2.5 | incorrect | False | incorrect | s2 | s2 |
| img_68_pert_2.5 | incorrect | True | incorrect | s1 | s1 |
| img_111_pert_1.3 | incorrect | False | incorrect | s2 | s2 |
| img_463_pert_1.3 | incorrect | False | incorrect | s2 | s2 |
| img_465_pert_1.3 | indeterminate | False | incorrect | None | s7 |
| img_108_pert_1.4 | correct | True | incorrect | None | s1 |
| img_427_pert_1.4 | indeterminate | False | incorrect | None | s2 |
| img_472_pert_1.4 | indeterminate | False | incorrect | None | s2 |
| img_503_pert_1.4 | incorrect | False | incorrect | s1 | s1 |
| img_466_pert_1.4 | incorrect | False | incorrect | s4 | s4 |
| img_111_pert_2.1 | incorrect | False | incorrect | s2 | s2 |
| img_98_pert_2.1 | indeterminate | False | incorrect | None | s2 |
| img_372_pert_2.1 | indeterminate | False | incorrect | None | s2 |
| img_109_pert_2.1 | incorrect | False | incorrect | s1 | s1 |
| img_223_pert_2.2 | incorrect | True | incorrect | s1 | s1 |
| img_465_pert_2.2 | indeterminate | False | incorrect | None | s4 |
| img_529_pert_2.2 | indeterminate | False | incorrect | None | s1 |
| img_573_pert_2.2 | incorrect | True | incorrect | s2 | s2 |
| img_226_pert_2.2 | incorrect | True | incorrect | s1 | s1 |
| img_176_pert_4.3 | indeterminate | False | correct | None | None |
| img_92_pert_4.3 | incorrect | False | correct | s1 | None |
| img_91_pert_2.3 | indeterminate | False | incorrect | None | s6 |
| img_112_pert_4.4 | incorrect | False | incorrect | s3 | s4 |
| img_115_pert_4.4 | correct | True | incorrect | None | s1 |
| img_529_pert_4.5 | correct | True | incorrect | None | s1 |
| img_160_pert_2.4 | incorrect | True | incorrect | s1 | s1 |
| img_560_pert_1.5 | indeterminate | False | incorrect | None | s3 |
| img_465_pert_1.5 | indeterminate | False | incorrect | None | s2 |
| img_540_pert_1.5 | indeterminate | False | incorrect | None | s3 |
| img_153_pert_1.5 | incorrect | True | incorrect | s1 | s1 |
| img_194_pert_1.5 | incorrect | False | incorrect | s1 | s2 |
| img_220_pert_1.5 | incorrect | True | incorrect | s1 | s1 |
| img_220_pert_4.6 | indeterminate | False | incorrect | None | s1 |
| img_476_pert_5.1 | indeterminate | False | correct | None | None |
| img_579_pert_5.1 | indeterminate | False | correct | None | None |
| img_578_pert_5.1 | indeterminate | False | correct | None | None |
| img_489_pert_5.1 | correct | True | correct | None | None |
| img_490_pert_5.1 | correct | True | correct | None | None |
| img_483_pert_5.1 | correct | True | correct | None | None |
| img_592_pert_5.1 | incorrect | False | correct | s2 | None |
| img_456_pert_5.1 | indeterminate | False | correct | None | None |
| img_455_pert_5.1 | indeterminate | False | correct | None | None |
| img_458_pert_5.1 | incorrect | False | correct | s1 | None |
| img_566_pert_5.1 | incorrect | False | correct | s2 | None |
| img_572_pert_5.1 | indeterminate | False | correct | None | None |
| img_65_pert_5.1 | indeterminate | False | correct | None | None |
| img_27_pert_5.1 | correct | True | correct | None | None |
| img_14_pert_5.1 | indeterminate | False | correct | None | None |
| img_49_pert_5.1 | incorrect | False | correct | s1 | None |
| img_77_pert_5.1 | incorrect | True | correct | s2 | None |
| img_78_pert_5.1 | incorrect | True | correct | s1 | None |
| img_37_pert_5.1 | indeterminate | False | correct | None | None |
| img_20_pert_5.1 | indeterminate | False | correct | None | None |
| img_492_pert_5.1 | indeterminate | False | correct | None | None |
| img_488_pert_5.1 | indeterminate | False | correct | None | None |
