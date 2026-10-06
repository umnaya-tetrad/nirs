# Умная тетрадь — предварительная проверка CAS

Общий строгий LaTeX → SymPy parser/normalizer и воспроизводимый эксперимент на 20
синтетических примерах. Единственный движок символьных вычислений — **SymPy**.
**Итоговый GO/NO-GO на FERMAT пока не получен: выбранной GT-выборки нет.**

## Запуск через Docker

Нужен запущенный Docker с Linux-контейнерами и Docker Compose. Команды выполняются
из корня репозитория. Локальный Python для этого варианта не требуется.

```powershell
New-Item -ItemType Directory -Force reports/local | Out-Null
docker compose build cas tests
docker compose run --rm tests
docker compose run --rm cas parse '\frac{x+1}{2}=3'
docker compose run --rm cas verify '2x+3=7' 'x=2'
docker compose run --rm cas
```

Последняя команда запускает эксперимент на 20 синтетических примерах. Результаты
сохраняются на компьютере в `reports/local/report.json`, `results.csv` и `report.md`.
Входные данные из `data/` доступны контейнеру только для чтения. Собственная выборка:

```powershell
docker compose run --rm cas benchmark /data/private/fermat_dev_20.json --output /reports/fermat
```

Это консольная утилита: контейнер завершает работу после команды. Порты и постоянно
работающий сервер не нужны. Во время вычислений сеть отключена; при сборке нужен
доступ к Docker Hub и PyPI. Тестовые зависимости находятся в отдельной стадии `test`.
Приватные данные, окружение `.venv`, Git и отчёты не попадают в контекст сборки.

На Linux/macOS вместо первой команды используйте `mkdir -p reports/local`.
На Linux для сохранения отчётов от своего пользователя перед командами Compose задайте:

```sh
export LOCAL_UID=$(id -u)
export LOCAL_GID=$(id -g)
```

Можно использовать и Docker без Compose:

```sh
docker build -t umnaya-tetrad-cas .
docker run --rm --network none umnaya-tetrad-cas parse '2x+3=7'
```

После изменения исходников пересоберите образы командой `docker compose build cas tests`.

## Локальный запуск без Docker

Нужны Python 3.10+ и зависимости из `pyproject.toml`. В Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[test]'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m nirs_cas parse '\frac{x+1}{2}=3'
.\.venv\Scripts\python.exe -m nirs_cas verify '2x+3=7' 'x=2'
.\.venv\Scripts\python.exe -m nirs_cas benchmark data\synthetic_20.json --output reports\local
```

В текущей рабочей копии `.venv` уже подготовлена. Повторная установка не нужна для запуска
через `python -m nirs_cas` из корня проекта. В Linux/macOS путь к Python — `.venv/bin/python`.

## API и поддерживаемый язык

```python
from nirs_cas import parse_latex, verify_step

parsed = parse_latex(r"\frac{x+1}{2}=3")
assert parsed.status == "OK"
print(parsed.to_dict())
print(verify_step("2x+3=7", "x=2").to_dict())
```

Один API предназначен для GT и распознанного LaTeX. Вход не исполняется как Python.
Поддержаны одно равенство `=`, `+ - * /`, неявное умножение `2x`, `xy`, `x(y+1)`,
круглые/квадратные скобки и группы `{}`, `\frac`/`\dfrac`/`\tfrac`, целые и простые
рациональные степени, `\sqrt{}` и `\sqrt[n]{}`, точные десятичные дроби, `\pi`,
однобуквенные латинские переменные и ряд греческих (`\alpha`, `\beta` и др.).
Все переменные действительные; нечётные корни понимаются как действительные.

Нормализуются обёртки `$…$`, `$$…$$`, `\(…\)`, `\[…\]`,
`\left`/`\right`, пробельные команды, `\cdot`/`\times`/`\div` и Unicode `− × ÷ ·`.
Дроби и корни требуют фигурных скобок. Составные/отрицательные/многозначные показатели
требуют `{}`: `x^{-2}`, `x^{12}`, `x^{1/2}`. Показатель с переменной не поддержан.

Буквы всегда обозначают отдельные переменные: `ab` — произведение, `f(x)` — `f*x`,
не вызов функции. Для устранения неоднозначности дробей используйте `\frac{a}{b}`,
а не `a/bc`. Системы, цепочки равенств, текст, единицы измерения, индексы и функции
вне выбранного языка не поддержаны. Неизвестные команды/символы дают `PARSE_FAILED`;
plain-text слова из латинских букв могут читаться как произведения — их нужно отделять
при сегментации математических шагов.

Лимиты: 2048 символов, 256 токенов, 24 уровня групп, 8 переменных, 12 цифр в числе,
числитель степени по модулю ≤20, знаменатель/индекс корня ≤12; бюджет вложенных степеней.
Для неподдерживаемого или неоднозначного результата verifier возвращает `UNSUPPORTED`.

## Результаты и границы

- [Отчёт предварительного прогона](reports/preliminary/report.md),
  [подробный JSON](reports/preliminary/report.json), [CSV](reports/preliminary/results.csv).
- [Протокол и формат будущих 20 dev-примеров FERMAT](docs/experiment.md).

Verifier добавлен в объёме, необходимом для пилота: сохранение множества решений или
тождества с областью определения. Он не проверяет решение относительно текста задачи,
считает первый символьный шаг доверенным и не заменяет будущий полноценный oracle/evaluator.
Ни гипотезы исследования, ни качество на FERMAT этим синтетическим прогоном не подтверждаются.
