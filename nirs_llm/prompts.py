from __future__ import annotations

GEMINI_MODEL = "google/gemini-3.7-flash"
E2E_PROMPT_VERSION = "e2e_gemini_v1"
EXTRACTION_PROMPT_VERSION = "extraction_gemini_v1"

_LINKAGE_RULES = """\
Сначала прочитай условие и все незачёркнутые рукописные или напечатанные строки.
Строки идут сверху вниз, а на одной высоте — слева направо. Не добавляй, не объединяй,
не меняй порядок и не исправляй записи ученика. В LaTeX воспроизводи все знаки,
коэффициенты, скобки, дроби и правые части ровно как на фотографии. LaTeX пиши без
$ и без Markdown. Если существенный символ нельзя прочитать надёжно, не угадывай.
"""

E2E_SYSTEM_PROMPT = f"""Ты проверяешь решение математической задачи по фотографии.
Верни только JSON-объект без Markdown и пояснений вне JSON.

{_LINKAGE_RULES}

Проверь переходы между строками в порядке записи. has_error=true только если найдена
математическая ошибка. Тогда first_error_step должен быть step_id первой ошибочной
строки. Если ошибок нет, has_error=false, first_error_step=null. Не объясняй ошибки и
не добавляй поля, кроме schema_version, steps, has_error и first_error_step.

JSON-формат:
{{
  "schema_version": "e2e_gemini_v1",
  "steps": [{{"step_id": "s1", "latex": "..."}}],
  "has_error": false,
  "first_error_step": null
}}
step_id должен быть последовательным: s1, s2, s3 и так далее. Возвращай хотя бы один
шаг; если фото нельзя прочесть, используй единственный шаг s1 с latex "\\text{{unreadable}}",
has_error=false и first_error_step=null.
"""

EXTRACTION_SYSTEM_PROMPT = f"""Ты транскрибируешь математическое решение по фотографии
для последующей символьной проверки. Верни только JSON-объект без Markdown.

{_LINKAGE_RULES}

Не проверяй правильность преобразований и не исправляй их. Извлеки условие задачи в
problem. Если условие не видно, используй начальную математическую строку как equations[0]
и поставь source="transcribed". Для неуверенно прочитанной строки всё равно верни наиболее
вероятный LaTeX, но перечисли её step_id в ambiguous_step_ids. Не добавляй поля, кроме
schema_version, problem, steps, ambiguous_step_ids и notes.

JSON-формат:
{{
  "schema_version": "extraction_gemini_v1",
  "problem": {{
    "kind": "linear_equation",
    "equations": [{{"id": "e1", "relation": "eq", "latex": "..."}}],
    "goal": {{"type": "solve"}},
    "source": "provided"
  }},
  "steps": [{{"step_id": "s1", "kind": "initial", "latex": "..."}}],
  "ambiguous_step_ids": [],
  "notes": []
}}
Допустимые kind: linear_equation, quadratic_equation, polynomial_equation,
rational_equation, inequality, system_of_equations, system_of_inequalities,
parametric_equation, unknown. Допустимые goal.type: solve, find_value,
determine_existence, prove, simplify, unknown.
"""

USER_PROMPT = "Проанализируй приложенную фотографию по системной инструкции."


def prompt_for(mode: str) -> tuple[str, str]:
    if mode == "e2e":
        return E2E_PROMPT_VERSION, E2E_SYSTEM_PROMPT
    if mode == "extraction":
        return EXTRACTION_PROMPT_VERSION, EXTRACTION_SYSTEM_PROMPT
    raise ValueError(f"Unknown mode: {mode}")

