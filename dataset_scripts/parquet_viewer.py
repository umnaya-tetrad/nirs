import glob
from io import BytesIO
import json
import os

# Gradio checks its own local URL through httpx when starting. In environments with
# a global proxy that probe must stay on the loopback interface.
_localhost_exclusions = "127.0.0.1,localhost"
os.environ["NO_PROXY"] = _localhost_exclusions
os.environ["no_proxy"] = _localhost_exclusions

import gradio as gr
from gradio_client import utils as gradio_client_utils
from datasets import load_dataset
from PIL import Image

# gradio-client 1.3.0 does not recognise the valid OpenAPI shorthand
# `additionalProperties: true`.  The patch is local to this viewer and maps that
# unrestricted object schema to ``Any`` when Gradio prepares its UI metadata.
_schema_to_python_type = gradio_client_utils._json_schema_to_python_type


def _schema_to_python_type_with_boolean_support(schema, defs):
    if isinstance(schema, bool):
        return "Any" if schema else "Never"
    return _schema_to_python_type(schema, defs)


gradio_client_utils._json_schema_to_python_type = _schema_to_python_type_with_boolean_support

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

    image = _decode_image(row.get("image"))
    metadata = {k: v for k, v in row.items() if k != "image"}

    return image, json.dumps(metadata, ensure_ascii=False, indent=2, default=str), f"Выбрана строка #{row_idx} из {len(ds)}"


def _decode_image(image):
    """The parquet image column stores {bytes, path}; Gradio needs image data itself."""
    if isinstance(image, dict) and isinstance(image.get("bytes"), bytes):
        return Image.open(BytesIO(image["bytes"]))
    return image


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
            json_output = gr.Textbox(label="Все поля строки (JSON)", lines=22, interactive=False)

    dataframe.select(show_details, outputs=[image_output, json_output, status_text])

# The viewer is a local manual tool, so it does not need Gradio's generated API
# description.  Disabling it also avoids schema generation issues in Gradio 4.x.
demo.launch(server_name="127.0.0.1", show_api=False)
