# NIRS — VLM, GT и CAS

Экспериментальная система проверяет рукописные школьные решения по математике. Канонические JSON-схемы находятся в `data_contracts/`:

- `MathCoreInput` — транскрипция VLM, передаваемая математическому ядру;
- `SolutionAnalysis` — единый результат E2E-VLM, GT и ветки VLM → CAS.

Поток работы: VLM либо сразу выдаёт `SolutionAnalysis` (режим `e2e`), либо сначала
транскрибирует изображение в `MathCoreInput` (режим `extraction`). Во втором режиме
CAS получает только канонический JSON и возвращает `SolutionAnalysis`. Он не должен
выдавать ложный вердикт для неподдерживаемой математики: в таких случаях результат —
`indeterminate`.

## Состав

- `nirs_llm/` — Gemini и GigaChat в режимах `e2e` и `extraction`.
- `nirs_cas/` — ограниченный LaTeX → SymPy verifier.
- `dataset/test_gt.json` и `dataset/test_gt_images/` — 20 размеченных dev-кейсов.
- `dataset/final_gt.json` — 80 размеченных final-кейсов. Final-набор не используется для настройки VLM-адаптеров или CAS.
- `dataset_scripts/selected.json` — manifest 100 уникальных FERMAT-ID. Сам `selected.parquet` с изображениями хранится вне Git.

## Локальные фотографии FERMAT

Изображения намеренно не хранятся в Git. Все приватные данные должны лежать в
`data/private/`: эта папка уже добавлена в `.gitignore`.

| Что нужно | Путь |
| --- | --- |
| 20 фото dev-набора | `dataset/test_gt_images/` — уже в репозитории |
| 80 фото final-набора в подготовленном рабочем окружении | `data/private/final_images/` |
| Архив для передачи коллегам, все 100 выбранных фото | `data/private/fermat_selected_100_images.zip` |

Коллеге достаточно положить архив в любое место и распаковать его в корень
`data/private/` проекта. После распаковки путь к фото будет таким:

```text
data/private/fermat_selected_100_images/<FERMAT_ID>.png
```

Например, `img_151_pert_4.3` будет находиться по пути
`data/private/fermat_selected_100_images/img_151_pert_4.3.png`. Имена файлов
совпадают с `id` в GT и с ID из `dataset_scripts/selected.json`.

Для запуска тестов и обработки только JSON эти изображения не нужны. Они требуются
для VLM-прогонов и ручной сверки разметки. Dev-набор можно использовать для настройки
промптов и адаптеров; final-80 предназначен только для финальной оценки.

## Установка и тесты

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install -e '.[test]'
pytest -q
```

Для VLM-прогонов скопируйте `.env.example` в `.env` и добавьте API-ключи. Сначала запускайте один кейс с `--fail-fast`; batch-артефакты пишутся в игнорируемый `outputs/`.

## Граница CAS

CAS получает и возвращает только объекты канонического контракта. Он проверяет ограниченный класс алгебраических переходов; при тексте, системах, неравенствах или неподдерживаемом LaTeX возвращает `indeterminate`, а не `incorrect`. Предварительный synthetic-20 отчёт не является результатом на FERMAT.
