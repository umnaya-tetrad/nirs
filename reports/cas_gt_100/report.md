# CAS на эталонном распознавании

Режим: exploratory_gt. Только `steps[].latex`; GT labels используются после проверки.

Полное покрытие: 42/100 (42.0%).
Разобрано шагов: 292/367; все шаги разобраны у 68 решений.
Точность has_error на всех: 56.0%; на покрытых: 81.0%.
Точность first_error_step на всех: 44.0%; только на ошибочных GT: 52.2%.

Отказы и таймауты остаются в знаменателе. Независимое свидетельство ошибки не означает полного покрытия. При неизвестном более раннем шаге первая ошибка не локализуется.
Проверяется согласованность записанной математики. Условие задачи, пропущенные подстановки, выбор ветви и полнота ответа не поступают в CAS.
После доработок по этим 100 примерам результат является исследовательским прогоном, а не независимым holdout.

| ID | CAS | Coverage | GT | Первая ошибка CAS | Первая ошибка GT |
|---|---|---|---|---|---|
| img_509_pert_5.1 | indeterminate | False | correct | None | None |
| img_554_pert_5.1 | indeterminate | False | correct | None | None |
| img_471_pert_5.1 | indeterminate | False | correct | None | None |
| img_462_pert_5.1 | incorrect | True | correct | s2 | None |
| img_494_pert_5.2 | correct | True | correct | None | None |
| img_452_pert_5.2 | indeterminate | False | correct | None | None |
| img_471_pert_5.2 | correct | True | correct | None | None |
| img_373_pert_5.2 | indeterminate | False | correct | None | None |
| img_221_pert_5.3 | indeterminate | False | correct | None | None |
| img_151_pert_5.3 | correct | True | correct | None | None |
| img_509_pert_3.1 | indeterminate | False | correct | None | None |
| img_157_pert_3.2 | incorrect | True | incorrect | s2 | s2 |
| img_480_pert_2.5 | incorrect | False | incorrect | s2 | s2 |
| img_110_pert_1.3 | incorrect | True | incorrect | s2 | s2 |
| img_96_pert_2.1 | incorrect | False | incorrect | s2 | s9 |
| img_136_pert_2.2 | indeterminate | False | incorrect | None | s2 |
| img_203_pert_4.3 | indeterminate | False | correct | None | None |
| img_398_pert_4.4 | indeterminate | False | incorrect | None | s7 |
| img_225_pert_2.4 | incorrect | True | incorrect | s2 | s2 |
| img_128_pert_1.5 | incorrect | True | incorrect | s2 | s2 |
| img_400_pert_5.1 | indeterminate | False | correct | None | None |
| img_374_pert_5.1 | indeterminate | False | correct | None | None |
| img_480_pert_5.1 | correct | True | correct | None | None |
| img_19_pert_5.1 | indeterminate | False | correct | None | None |
| img_494_pert_5.1 | incorrect | False | correct | s3 | None |
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
| img_568_pert_3.1 | incorrect | True | incorrect | s1 | s1 |
| img_494_pert_3.1 | incorrect | False | incorrect | s3 | s4 |
| img_466_pert_3.1 | incorrect | False | incorrect | s10 | s10 |
| img_542_pert_3.1 | incorrect | False | incorrect | s1 | s1 |
| img_462_pert_3.1 | incorrect | True | incorrect | s1 | s1 |
| img_108_pert_3.1 | incorrect | True | incorrect | s1 | s1 |
| img_89_pert_3.1 | incorrect | True | incorrect | s2 | s2 |
| img_559_pert_3.1 | incorrect | True | incorrect | s1 | s1 |
| img_99_pert_3.1 | indeterminate | False | incorrect | None | s3 |
| img_233_pert_3.2 | incorrect | True | incorrect | s1 | s1 |
| img_190_pert_3.2 | incorrect | True | incorrect | s1 | s1 |
| img_559_pert_3.2 | incorrect | True | incorrect | s1 | s1 |
| img_172_pert_3.2 | correct | True | incorrect | None | s2 |
| img_151_pert_3.2 | incorrect | True | incorrect | s1 | s1 |
| img_586_pert_3.2 | incorrect | True | incorrect | s2 | s2 |
| img_448_pert_3.2 | indeterminate | False | incorrect | None | s5 |
| img_471_pert_3.2 | correct | True | incorrect | None | s1 |
| img_462_pert_2.5 | incorrect | True | incorrect | s1 | s1 |
| img_173_pert_2.5 | incorrect | True | incorrect | s1 | s1 |
| img_35_pert_2.5 | incorrect | False | incorrect | s1 | s2 |
| img_375_pert_2.5 | indeterminate | False | incorrect | None | s4 |
| img_574_pert_2.5 | indeterminate | False | incorrect | None | s6 |
| img_395_pert_2.5 | incorrect | False | incorrect | s2 | s2 |
| img_494_pert_2.5 | incorrect | False | incorrect | s3 | s4 |
| img_68_pert_2.5 | incorrect | True | incorrect | s1 | s1 |
| img_111_pert_1.3 | incorrect | False | incorrect | s2 | s2 |
| img_463_pert_1.3 | incorrect | False | incorrect | s2 | s2 |
| img_465_pert_1.3 | indeterminate | False | incorrect | None | s7 |
| img_108_pert_1.4 | correct | True | incorrect | None | s1 |
| img_427_pert_1.4 | indeterminate | False | incorrect | None | s2 |
| img_472_pert_1.4 | indeterminate | False | incorrect | None | s2 |
| img_96_pert_1.4 | incorrect | False | incorrect | s2 | s8 |
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
| img_151_pert_4.3 | correct | True | incorrect | None | s1 |
| img_92_pert_4.3 | incorrect | False | correct | s1 | None |
| img_91_pert_2.3 | indeterminate | False | incorrect | None | s6 |
| img_373_pert_2.3 | incorrect | False | incorrect | s1 | s3 |
| img_112_pert_4.4 | incorrect | False | incorrect | s3 | s4 |
| img_115_pert_4.4 | correct | True | incorrect | None | s1 |
| img_529_pert_4.5 | correct | True | incorrect | None | s1 |
| img_157_pert_2.4 | incorrect | True | incorrect | s2 | s2 |
| img_398_pert_2.4 | indeterminate | False | incorrect | None | s5 |
| img_160_pert_2.4 | incorrect | True | incorrect | s1 | s1 |
| img_157_pert_1.5 | incorrect | True | incorrect | s1 | s1 |
| img_225_pert_1.5 | incorrect | True | incorrect | s1 | s1 |
| img_560_pert_1.5 | indeterminate | False | incorrect | None | s3 |
| img_465_pert_1.5 | indeterminate | False | incorrect | None | s2 |
| img_540_pert_1.5 | indeterminate | False | incorrect | None | s3 |
| img_153_pert_1.5 | incorrect | True | incorrect | s1 | s1 |
| img_194_pert_1.5 | incorrect | False | incorrect | s1 | s2 |
| img_220_pert_1.5 | incorrect | True | incorrect | s1 | s1 |
| img_220_pert_4.6 | indeterminate | False | incorrect | None | s1 |
