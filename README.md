# NIRS — VLM, GT и CAS

Экспериментальная система проверяет рукописные школьные решения по математике. Канонические JSON-схемы находятся в `data_contracts/`:

- `MathCoreInput` — транскрипция VLM, передаваемая математическому ядру;
- `SolutionAnalysis` — единый результат E2E-VLM, GT и ветки VLM → CAS.

## Состав

- `nirs_llm/` — Gemini и GigaChat в режимах `e2e` и `extraction`.
- `nirs_cas/` — ограниченный LaTeX → SymPy verifier.
- `dataset/test_gt.json` и `dataset/test_gt_images/` — 20 размеченных dev-кейсов.
- `dataset/final_gt.json` — 80 размеченных final-кейсов. Final-набор не используется для настройки VLM-адаптеров или CAS.
- `dataset_scripts/selected.json` — manifest 100 уникальных FERMAT-ID. Сам `selected.parquet` с изображениями хранится вне Git.

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
