# Предварительная проверка CAS

Набор: 20 handcrafted school-algebra smoke cases; NOT FERMAT (synthetic).
Решение: **PRELIMINARY_ONLY**.

Проверены: 17/20; coverage: 85%.
Разобраны все шаги: 17/20. Порог: 14/20 (70%).

Синтетический прогон проверяет реализацию. Итоговый GO/NO-GO требует 20 заранее выбранных dev-примеров FERMAT.
Первое символьное равенство считается доверенным условием; правильность относительно текста задачи не проверяется.

| ID | Разбор | Проверка | Первый ошибочный шаг |
|---|---|---|---|
| s01-arithmetic | OK | VALID | None |
| s02-decimal | OK | VALID | None |
| s03-linear | OK | VALID | None |
| s04-linear-error | OK | INVALID | 3 |
| s05-fractions | OK | VALID | None |
| s06-distribution | OK | VALID | None |
| s07-square | OK | VALID | None |
| s08-factor-equation | OK | VALID | None |
| s09-lost-root | OK | INVALID | 2 |
| s10-multiple-variables | OK | VALID | None |
| s11-multivariate-equation | OK | VALID | None |
| s12-square-root | OK | VALID | None |
| s13-radical-equation | OK | VALID | None |
| s14-cube-root | OK | VALID | None |
| s15-domain-loss | OK | INVALID | 2 |
| s16-rational-equation | OK | VALID | None |
| s17-false-first-equation | OK | INVALID | 1 |
| s18-unsupported-trigonometry | PARSE_FAILED | UNSUPPORTED | None |
| s19-unsupported-inequality | PARSE_FAILED | UNSUPPORTED | None |
| s20-unsupported-prose | PARSE_FAILED | UNSUPPORTED | None |
