import glob
import os

import gradio as gr
from datasets import load_dataset

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Ищем папку с parquet-файлами (dataset или datasets) рядом со скриптом
DATA_DIR = None
for name in ("dataset", "datasets"):
    candidate = os.path.join(SCRIPT_DIR, "..", name)
    if os.path.isdir(candidate):
        DATA_DIR = candidate
        break

if DATA_DIR is None:
    raise FileNotFoundError("Не найдена папка dataset/ или datasets/ рядом со скриптом")

parquet_files = sorted(glob.glob(os.path.join(DATA_DIR, "*.parquet")))
if not parquet_files:
    raise FileNotFoundError(f"В папке {DATA_DIR} нет файлов *.parquet")

# Склеиваем все parquet-файлы в один датасет
ds = load_dataset("parquet", data_files=parquet_files)["train"]

# Преобразуем данные в Pandas DataFrame для таблицы (без колонки с картинкой)
df_all = ds.to_pandas()
text_columns = [col for col in df_all.columns if col != "image"]
df_text = df_all[text_columns].reset_index(drop=True)
df_text.insert(0, "#", range(len(df_text)))

# Сколько строк показывать в таблице (все могут быть очень тяжёлыми)
TABLE_LIMIT = 1000


def show_details(evt: gr.SelectData):
    row_idx = evt.index[0]  # Индекс выбранной строки в таблице
    row = ds[row_idx]

    image = row.get("image")
    metadata = {k: v for k, v in row.items() if k != "image"}

    return image, metadata, f"Выбрана строка #{row_idx} из {len(ds)}"


with gr.Blocks(title="Parquet Explorer") as demo:
    gr.Markdown(f"## Просмотр датасета: {len(ds)} записей из {len(parquet_files)} файлов")

    with gr.Row():
        # Левая колонка: Таблица с текстом
        with gr.Column(scale=2):
            dataframe = gr.Dataframe(
                value=df_text.head(TABLE_LIMIT),
                interactive=False,
                label="Список записей (нажмите на строку для просмотра)",
            )

        # Правая колонка: Просмотр картинки и метаданных выбранной строки
        with gr.Column(scale=1):
            status_text = gr.Markdown("### Нажмите на любую строку в таблице")
            image_output = gr.Image(label="Изображение", height=300)
            json_output = gr.JSON(label="Все поля строки")

    dataframe.select(show_details, outputs=[image_output, json_output, status_text])

demo.launch()
