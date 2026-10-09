"""H2: OCR quality and how transcription errors propagate to CAS."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .h1 import DECIDABLE, system_label
from .ocr import analyze_transcription
from .runs import RunData

FAILURE_CLASSES = {"api_failed", "invalid_contract", "transcription_error"}


def _cas_verdict(record) -> str | None:
    label = system_label(record)
    return label if label in DECIDABLE else None


def analyze_h2(run: RunData, gt_by_id: dict[str, dict[str, Any]], cas_on_gt: dict[str, dict[str, Any]], ids: list[str]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    by_class: dict[str, dict[str, int]] = defaultdict(lambda: {"cases": 0, "cas_flips": 0, "final_wrong": 0, "final_correct": 0})
    exact_cases = missed_steps = extra_steps = total_distance = total_gt_tokens = 0
    cas_flips = flip_total = 0
    cas_ext_correct = cas_gt_correct = 0
    for record_id in ids:
        gt = gt_by_id[record_id]
        record = run.records.get(record_id)
        extraction = (run.extraction or {}).get(record_id)
        transcription = analyze_transcription(gt, extraction)
        first_class = transcription["error_class"]
        if record is None or record.status != "ok":
            error_class = "invalid_contract" if (record is not None and record.status == "invalid_contract") else (
                "api_failed" if record is not None else "transcription_error")
        elif not transcription["available"]:
            error_class = "transcription_error"
        else:
            error_class = first_class
        cas_ext = _cas_verdict(record)
        cas_gt = cas_on_gt[record_id]["verdict"]
        final_correct = cas_ext == gt["verdict"] and cas_ext in DECIDABLE
        flipped = cas_ext != cas_gt if (cas_ext in DECIDABLE and cas_gt in DECIDABLE) else None
        if cas_ext in DECIDABLE:
            flip_total += 1
            cas_ext_correct += cas_ext == gt["verdict"]
            if flipped:
                cas_flips += 1
        if cas_gt in DECIDABLE:
            cas_gt_correct += cas_gt == gt["verdict"]
        status = transcription["status_counts"]
        exact_cases += transcription["error_class"] == "exact"
        missed_steps += status.get("missed_line", 0)
        extra_steps += status.get("extra_line", 0)
        total_distance += transcription["step_edit_distance"]
        total_gt_tokens += transcription["total_gt_tokens"]
        bucket = by_class[error_class]
        bucket["cases"] += 1
        bucket["cas_flips"] += 1 if flipped else 0
        bucket["final_wrong"] += 0 if final_correct else 1
        bucket["final_correct"] += 1 if final_correct else 0
        rows.append({
            "id": record_id, "gt_verdict": gt["verdict"], "error_class": error_class,
            "transcription_error_class": first_class,
            "ocr_available": transcription["available"],
            "exact": transcription["error_class"] == "exact",
            "step_edit_distance": transcription["step_edit_distance"],
            "total_gt_tokens": transcription["total_gt_tokens"],
            "missed_steps": status.get("missed_line", 0), "extra_steps": status.get("extra_line", 0),
            "cas_ext_verdict": cas_ext, "cas_gt_verdict": cas_gt,
            "cas_flip": flipped, "final_correct": final_correct,
            "final_wrong": not final_correct,
            "counts": transcription["counts"],
        })
    total = len(ids)
    class_table = []
    for name in sorted(by_class, key=lambda key: (-by_class[key]["cases"], key)):
        bucket = by_class[name]
        class_table.append({
            "error_class": name, "cases": bucket["cases"],
            "share": bucket["cases"] / total if total else 0.0,
            "cas_flips": bucket["cas_flips"],
            "cas_flip_rate": bucket["cas_flips"] / bucket["cases"] if bucket["cases"] else 0.0,
            "final_wrong": bucket["final_wrong"],
            "final_wrong_rate": bucket["final_wrong"] / bucket["cases"] if bucket["cases"] else 0.0,
            "failure_fraction": bucket["final_wrong"] / max(1, sum(entry["final_wrong"] for entry in by_class.values())),
        })
    return {
        "rows": rows,
        "by_error_class": class_table,
        "overall": {
            "examples": total,
            "exact_transcriptions": exact_cases,
            "exact_match_rate": exact_cases / total if total else 0.0,
            "missed_steps": missed_steps, "extra_steps": extra_steps,
            "mean_step_edit_distance": total_distance / total if total else 0.0,
            "normalized_edit_distance": total_distance / total_gt_tokens if total_gt_tokens else 0.0,
            "cas_flips": cas_flips, "cas_flip_rate": cas_flips / flip_total if flip_total else 0.0,
            "extraction_cas_verdict_accuracy": cas_ext_correct / total if total else 0.0,
            "cas_on_gt_verdict_accuracy": cas_gt_correct / total if total else 0.0,
            "verdict_accuracy_drop": (cas_gt_correct - cas_ext_correct) / total if total else 0.0,
        },
    }
