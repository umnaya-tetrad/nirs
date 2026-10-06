import glob
import json
import os

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "dataset")
SELECTED_PATH = os.path.join(SCRIPT_DIR, "selected.json")
OUTPUT_PATH = os.path.join(DATA_DIR, "selected.parquet")

with open(SELECTED_PATH, encoding="utf-8") as f:
    selected_ids = set(json.load(f)["new_custom_id"])

parquet_files = [
    p for p in sorted(glob.glob(os.path.join(DATA_DIR, "*.parquet")))
    if os.path.abspath(p) != os.path.abspath(OUTPUT_PATH)
]
if not parquet_files:
    raise FileNotFoundError(f"В папке {DATA_DIR} нет файлов *.parquet")

# Склеиваем все датасеты воедино
df = pd.concat([pd.read_parquet(p) for p in parquet_files], ignore_index=True)
print(f"Всего записей: {len(df)}, файлов: {len(parquet_files)}")

# Отбираем записи с new_custom_id из selected.json
mask = df["new_custom_id"].isin(selected_ids)
selected_df = df[mask].reset_index(drop=True)

missing = selected_ids - set(selected_df["new_custom_id"])
if missing:
    print(f"Не найдено {len(missing)} id: {sorted(missing)}")

selected_df.to_parquet(OUTPUT_PATH, index=False)
print(f"Сохранено записей: {len(selected_df)} -> {OUTPUT_PATH}")
