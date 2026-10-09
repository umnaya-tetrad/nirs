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


def _task_spec_diagnostics(extraction: dict[str, Any] | None) -> dict[str, Any]:
    """Describe reported TaskSpec structure without pretending it has GT labels."""
    if not isinstance(extraction, dict):
        return {"available": False, "class": "missing_extraction", "task_visibility": None}
    task = extraction.get("task")
    steps = extraction.get("steps")
    if not isinstance(task, dict) or not isinstance(steps, list):
        return {"available": False, "class": "invalid_task_spec", "task_visibility": None}
    visibility = task.get("visibility")
    if visibility == "not_visible":
        kind = "task_not_visible"
    elif visibility != "visible":
        kind = "unknown_task_visibility"
    elif not isinstance(task.get("raw_latex"), str) or not task["raw_latex"].strip():
        kind = "missing_task_text"
    elif not isinstance(task.get("goal"), dict):
        kind = "missing_goal"
    elif any(not isinstance(step, dict) or not isinstance(step.get("derives_from"), list) for step in steps):
        kind = "incomplete_dependencies"
    else:
        kind = "reported_structured"
    return {"available": True, "class": kind, "task_visibility": visibility}


def analyze_h2(run: RunData, gt_by_id: dict[str, dict[str, Any]], cas_on_gt: dict[str, dict[str, Any]] | None, ids: list[str]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    by_class: dict[str, dict[str, int]] = defaultdict(lambda: {"cases": 0, "cas_flips": 0, "final_wrong": 0, "final_correct": 0})
    exact_cases = missed_steps = extra_steps = total_distance = total_gt_tokens = 0
    cas_flips = flip_total = 0
    cas_ext_correct = cas_gt_correct = 0
    indeterminate = 0
    task_spec_classes: dict[str, int] = defaultdict(int)
    fallback_reasons: dict[str, int] = defaultdict(int)
    for record_id in ids:
        gt = gt_by_id[record_id]
        record = run.records.get(record_id)
        extraction = (run.extraction or {}).get(record_id)
        transcription = analyze_transcription(gt, extraction)
        task_spec = _task_spec_diagnostics(extraction)
        task_spec_classes[task_spec["class"]] += 1
        first_class = transcription["error_class"]
        if record is None or record.status != "ok":
            error_class = "invalid_contract" if (record is not None and record.status == "invalid_contract") else (
                "api_failed" if record is not None else "transcription_error")
        elif not transcription["available"]:
            error_class = "transcription_error"
        else:
            error_class = first_class
        cas_ext = _cas_verdict(record)
        cas_gt = cas_on_gt[record_id]["verdict"] if cas_on_gt is not None else None
        final_correct = cas_ext == gt["verdict"] and cas_ext in DECIDABLE
        flipped = cas_ext != cas_gt if (cas_ext in DECIDABLE and cas_gt in DECIDABLE) else None
        if cas_ext in DECIDABLE:
            flip_total += 1
            cas_ext_correct += cas_ext == gt["verdict"]
            if flipped:
                cas_flips += 1
        if cas_gt in DECIDABLE:
            cas_gt_correct += cas_gt == gt["verdict"]
        if cas_ext is None:
            indeterminate += 1
        if record is not None and isinstance(record.contract, dict):
            for reason in record.contract.get("problem", {}).get("fallback_reasons", []):
                if isinstance(reason, str):
                    fallback_reasons[reason] += 1
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
            "counts": transcription["counts"], "task_spec_available": task_spec["available"],
            "task_spec_class": task_spec["class"], "task_visibility": task_spec["task_visibility"],
            "cas_indeterminate": cas_ext is None,
            "cas_fallback_reasons": (record.contract.get("problem", {}).get("fallback_reasons", [])
                                     if record is not None and isinstance(record.contract, dict) else []),
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
            "cas_on_gt_available": cas_on_gt is not None,
            "cas_on_gt_verdict_accuracy": cas_gt_correct / total if cas_on_gt is not None and total else None,
            "verdict_accuracy_drop": ((cas_gt_correct - cas_ext_correct) / total if cas_on_gt is not None and total else None),
            "assisted_indeterminate": indeterminate,
            "assisted_indeterminate_rate": indeterminate / total if total else 0.0,
            "task_spec_classes": dict(sorted(task_spec_classes.items())),
            "cas_indeterminate_reasons": dict(sorted(fallback_reasons.items(), key=lambda item: (-item[1], item[0]))),
        },
    }
