# Dev-20: четыре VLM-прогона

| Провайдер | Режим | Prompt | Валидные контракты | Что можно сравнивать с GT |
|---|---|---:|---:|---|
| Gemini | E2E | v2 | 20/20 | verdict и последовательность шагов `SolutionAnalysis` |
| Gemini | extraction | v1 | 18/20 | структура `MathCoreInput`, транскрипция шагов вручную/по проекции GT |
| GigaChat | E2E | v1 | 19/20 | verdict и последовательность шагов `SolutionAnalysis` |
| GigaChat | extraction | v2 | 14/20 | структура `MathCoreInput`, транскрипция шагов вручную/по проекции GT |

## E2E-метки

`dataset/test_gt.json` — полноценный `SolutionAnalysis`: в нём есть вердикт,
первый ошибочный шаг, эталонные шаги и findings. Поэтому E2E можно измерять
автоматически по verdict, а `first_error_step` сопоставлять вторично с учётом
различной сегментации строк.

## Extraction-метки

Отдельного канонического файла `MathCoreInput` для dev-20 нет. В `test_gt.json`
есть шаги решения, но отсутствуют некоторые поля extraction-контракта — например,
явные `problem.kind`, `problem.equations[].relation` и `goal.type`. Поэтому
нельзя честно заявлять точную extraction accuracy; текущая автоматическая метрика
здесь — валидность контракта. Для строгой оценки extraction нужно заранее создать
отдельный `test_extraction_gt.json` либо зафиксировать детерминированную проекцию
из FERMAT-полей и проверить её вручную.

## Ошибки контрактов extraction

- Gemini: `img_462_pert_5.1` вернул `relation="none"`,
  `img_221_pert_5.3` — `relation="unknown"`; оба значения отсутствуют в
  допустимом enum канонического контракта.
- GigaChat: пять раз использовал `goal.type="evaluate"` или `"show"` вместо
  одного из допустимых значений, ещё раз вернул `relation="leq"` вместо `"le"`.

Все API/контрактные ошибки сохранены локально в ignored `outputs/`, не заменены
искусственными verdict'ами.
