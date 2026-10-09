"""OCR diagnostics: LaTeX normalization, step alignment and error taxonomy."""
from __future__ import annotations

import difflib
import re
from collections import Counter
from typing import Any

COMMAND_RE = re.compile(r"\\[a-zA-Z]+")
TOKEN_RE = re.compile(r"\\[a-zA-Z]+|[0-9]+(?:\.[0-9]+)?(?![0-9])|[a-zA-Z]|[+\-*/=^_{}()\[\]<>.,;:!|]")
STRUCTURE = set("{}()[]")
OPERATORS = set("+-*/=<>|,;:!")
SPACING_COMMANDS = {"\\,", "\\;", "\\!", "\\quad", "\\qquad", "\\:", "\\ "}
SIGN_COMMANDS = {"\\pm", "\\mp", "\\cdot", "\\times", "\\div"}
ERROR_CLASSES = (
    "digit", "sign", "exponent", "variable", "operator",
    "structure", "missed_line", "extra_line", "segmentation", "ambiguous",
)


def normalize_latex(value: Any) -> str:
    text = value if isinstance(value, str) else str(value)
    text = text.replace("$", "")
    text = re.sub(r"\\(left|right|big|Big|bigg|Bigg)\b", "", text)
    for command in SPACING_COMMANDS:
        text = text.replace(command, " ")
    text = re.sub(r"\\[a-zA-Z]+\s*", lambda match: match.group(0).rstrip(), text)
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"\s+(?=\\)", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*([+\-*/=<>^_{}()\[\]])\s*", r"\1", text)
    return text.strip().rstrip(",.").strip()


def tokenize(value: Any) -> list[str]:
    return TOKEN_RE.findall(normalize_latex(value))


def _numeric(token: str) -> bool:
    return bool(re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", token))


def _digits(token: str) -> str:
    return re.sub(r"\D", "", token)


def classify_token_pair(left: str, right: str) -> str:
    if left == right:
        return "ambiguous"
    if _numeric(left) and _numeric(right):
        if _digits(left) != _digits(right) and left.replace(".", "") != right.replace(".", ""):
            return "digit"
        return "sign"
    if left == "^" or right == "^":
        return "exponent"
    if left.isalpha() and right.isalpha():
        return "variable"
    if left in OPERATORS or right in OPERATORS:
        return "operator"
    if left in STRUCTURE or right in STRUCTURE:
        return "structure"
    return "ambiguous"


def token_edit_counts(left: list[str], right: list[str]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    matcher = difflib.SequenceMatcher(a=left, b=right, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            span = min(i2 - i1, j2 - j1)
            for offset in range(span):
                counts[classify_token_pair(left[i1 + offset], right[j1 + offset])] += 1
            if i2 - i1 != j2 - j1:
                counts["segmentation"] += abs((i2 - i1) - (j2 - j1))
        elif tag == "delete":
            counts["extra_line"] += i2 - i1
        elif tag == "insert":
            counts["missed_line"] += j2 - j1
    return dict(counts)


def _levenshtein(left: list[str], right: list[str]) -> int:
    previous = list(range(len(right) + 1))
    for i, token_left in enumerate(left, 1):
        current = [i]
        for j, token_right in enumerate(right, 1):
            cost = 0 if token_left == token_right else 1
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost))
        previous = current
    return previous[-1]


def align_steps(gt_steps: list[dict[str, Any]], pred_steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gt_keys = [normalize_latex(step.get("latex", "")) for step in gt_steps]
    pred_keys = [normalize_latex(step.get("latex", "")) for step in pred_steps]
    matcher = difflib.SequenceMatcher(a=gt_keys, b=pred_keys, autojunk=False)
    alignment: list[dict[str, Any]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                alignment.append(_aligned(gt_steps, pred_steps, i1 + offset, j1 + offset, "equal"))
        elif tag == "replace":
            span = min(i2 - i1, j2 - j1)
            for offset in range(span):
                alignment.append(_aligned(gt_steps, pred_steps, i1 + offset, j1 + offset, "substituted"))
            for index in range(i1 + span, i2):
                alignment.append(_aligned(gt_steps, pred_steps, index, None, "missed_line"))
            for index in range(j1 + span, j2):
                alignment.append(_aligned(gt_steps, pred_steps, None, index, "extra_line"))
        elif tag == "delete":
            for index in range(i1, i2):
                alignment.append(_aligned(gt_steps, pred_steps, index, None, "missed_line"))
        else:
            for index in range(j1, j2):
                alignment.append(_aligned(gt_steps, pred_steps, None, index, "extra_line"))
    return alignment


def _aligned(gt_steps: list[dict[str, Any]], pred_steps: list[dict[str, Any]], gt_index: int | None, pred_index: int | None, status: str) -> dict[str, Any]:
    gt_id = gt_steps[gt_index].get("step_id", f"s{gt_index + 1}") if gt_index is not None else None
    pred_id = pred_steps[pred_index].get("step_id", f"s{pred_index + 1}") if pred_index is not None else None
    return {"gt_index": gt_index, "pred_index": pred_index, "gt_step_id": gt_id,
            "pred_step_id": pred_id, "status": status}


def step_diagnosis(gt_latex: Any, pred_latex: Any) -> dict[str, Any]:
    gt_tokens = tokenize(gt_latex)
    pred_tokens = tokenize(pred_latex)
    counts = token_edit_counts(gt_tokens, pred_tokens)
    dominant = "exact" if not counts else max(counts.items(), key=lambda item: (item[1], item[0]))[0]
    return {"error_class": dominant, "counts": counts,
            "token_edit_distance": _levenshtein(gt_tokens, pred_tokens),
            "gt_tokens": len(gt_tokens), "pred_tokens": len(pred_tokens),
            "exact": not counts}


def analyze_transcription(gt_record: dict[str, Any], extraction: dict[str, Any] | None) -> dict[str, Any]:
    gt_steps = gt_record.get("steps") if isinstance(gt_record.get("steps"), list) else []
    if not isinstance(extraction, dict) or not isinstance(extraction.get("steps"), list):
        return {"available": False, "error_class": "transcription_error", "steps": [], "counts": {},
                "status_counts": {"missed_line": len(gt_steps)}, "step_edit_distance": len(gt_steps), "total_gt_tokens": 0}
    pred_steps = extraction["steps"]
    alignment = align_steps(gt_steps, pred_steps)
    per_step: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    total_distance = 0
    total_gt_tokens = 0
    exact = True
    for entry in alignment:
        if entry["status"] == "equal":
            per_step.append({**entry, "error_class": "exact", "token_edit_distance": 0, "counts": {}})
            continue
        if entry["status"] == "missed_line":
            counts["missed_line"] += 1
            exact = False
            per_step.append({**entry, "error_class": "missed_line", "token_edit_distance": None, "counts": {}})
            continue
        if entry["status"] == "extra_line":
            counts["extra_line"] += 1
            exact = False
            per_step.append({**entry, "error_class": "extra_line", "token_edit_distance": None, "counts": {}})
            continue
        gt_step = gt_steps[entry["gt_index"]]
        pred_step = pred_steps[entry["pred_index"]]
        diagnosis = step_diagnosis(gt_step.get("latex", ""), pred_step.get("latex", ""))
        total_distance += diagnosis["token_edit_distance"]
        total_gt_tokens += diagnosis["gt_tokens"]
        if not diagnosis["exact"]:
            exact = False
            counts[diagnosis["error_class"]] += 1
            for name, value in diagnosis["counts"].items():
                counts[name] += value
        per_step.append({**entry, **diagnosis})
    return {"available": True, "error_class": "exact" if exact else _dominant_class(counts, alignment),
            "steps": per_step, "counts": dict(counts), "status_counts": _status_counts(alignment),
            "step_edit_distance": total_distance, "total_gt_tokens": total_gt_tokens}


def _status_counts(alignment: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(entry["status"] for entry in alignment)
    return dict(counts)


def _dominant_class(counts: Counter[str], alignment: list[dict[str, Any]]) -> str:
    if not counts:
        return "ambiguous"
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]
