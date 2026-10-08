"""Rate system SolutionAnalysis outputs against ground truth and export JSON/CSV reports."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sympy as sp

from nirs_cas.benchmark import run_isolated
from nirs_cas.adapter import extract_step_latex

SYSTEM_VERDICTS = ("correct", "incorrect", "indeterminate")
GT_VERDICTS = ("correct", "incorrect")
MISSING_LABEL = "missing"
CASE_COLUMNS = [
    "id", "status", "note", "gt_verdict", "gt_first_error_step",
    "pred_verdict", "pred_first_error_step", "verdict_match",
    "step_agreements", "step_union", "step_accuracy", "solution_match",
    "first_error_match", "first_error_category",
    "cas_status", "cas_covered", "cas_parse_status", "cas_parsed_steps", "cas_total_steps",
]


class EvaluationInputError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_array(path: Path) -> list[Any]:
    data = json.loads(path.read_bytes().decode("utf-8-sig"))
    if not isinstance(data, list):
        raise EvaluationInputError(f"{path}: expected a JSON array of records")
    return data


def _gt_paths(path: Path | list[Path]) -> list[Path]:
    paths = path if isinstance(path, list) else [path]
    if not paths:
        raise EvaluationInputError("At least one GT file is required")
    return [Path(item) for item in paths]


def load_gt(path: Path | list[Path]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for source in _gt_paths(path):
        for index, record in enumerate(_read_array(source)):
            if not isinstance(record, dict):
                raise EvaluationInputError(f"{source}: record #{index} is not an object")
            record_id = record.get("id")
            if not isinstance(record_id, str) or not record_id:
                raise EvaluationInputError(f"{source}: record #{index} needs a nonempty string id")
            if record_id in seen:
                raise EvaluationInputError(f"{source}: duplicate GT id {record_id}")
            if record.get("verdict") not in GT_VERDICTS:
                raise EvaluationInputError(f"{source}: {record_id}: GT verdict must be correct or incorrect")
            seen.add(record_id)
            result.append(record)
    if not result:
        raise EvaluationInputError(f"{path}: GT is empty")
    return result


def _solution_analysis_reason(record: Any) -> str | None:
    if not isinstance(record, dict):
        return "record is not an object"
    if record.get("verdict") not in SYSTEM_VERDICTS:
        return "record is not a SolutionAnalysis: verdict is missing or unknown (extraction output counts as not evaluated)"
    if not isinstance(record.get("id"), str) or not record.get("id"):
        return "record needs a nonempty string id"
    steps = record.get("steps")
    if not isinstance(steps, list) or not steps:
        return "record needs a non-empty steps array"
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or not isinstance(step.get("latex"), str) or not step["latex"].strip():
            return f"steps[{index}] must carry a nonempty latex string"
    return None


def load_predictions(path: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], int]:
    records = _read_array(path)
    valid: dict[str, dict[str, Any]] = {}
    invalid: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        reason = _solution_analysis_reason(record)
        if reason is None:
            record_id = record["id"]
            if record_id in valid:
                raise EvaluationInputError(f"{path}: duplicate prediction id {record_id}")
            valid[record_id] = record
        else:
            invalid.append({"index": index, "id": (record.get("id") or record.get("case_id")) if isinstance(record, dict) else None, "reason": reason})
    return valid, invalid, len(records)


def _review_map(record: dict[str, Any]) -> dict[str, str] | None:
    reviews = record.get("steps_reviewed")
    if not isinstance(reviews, list):
        return None
    mapping: dict[str, str] = {}
    for review in reviews:
        if isinstance(review, dict) and isinstance(review.get("step_id"), str):
            mapping[review["step_id"]] = str(review.get("verdict"))
    return mapping


def _compare_reviews(gt_reviews: dict[str, str], pred_reviews: dict[str, str]) -> tuple[int, int]:
    union = set(gt_reviews) | set(pred_reviews)
    agreements = sum(1 for step_id in union if gt_reviews.get(step_id) == pred_reviews.get(step_id))
    return agreements, len(union)


def _first_error_outcome(gt: dict[str, Any], row: dict[str, Any]) -> tuple[bool, str]:
    if row["status"] != "ok":
        return False, "missing_or_invalid"
    if row["pred_first_error_step"] == gt.get("first_error_step"):
        return True, "match"
    if row["pred_verdict"] == "indeterminate":
        return False, "indeterminate"
    if row["pred_first_error_step"] is None:
        return False, "no_error_reported"
    return False, "wrong_index"


def _case_row(gt: dict[str, Any], pred: dict[str, Any] | None, status: str, note: str, timeout: float) -> dict[str, Any]:
    gt_reviews = _review_map(gt)
    row: dict[str, Any] = {
        "id": gt["id"],
        "status": status,
        "note": note,
        "gt_verdict": gt["verdict"],
        "gt_first_error_step": gt.get("first_error_step"),
        "pred_verdict": None,
        "pred_first_error_step": None,
        "verdict_match": False,
        "step_agreements": None,
        "step_union": None,
        "step_accuracy": None,
        "solution_match": None,
        "first_error_match": None,
        "first_error_category": None,
        "cas_status": "NOT_RUN",
        "cas_covered": False,
        "cas_parse_status": "NOT_MEASURED",
        "cas_parsed_steps": None,
        "cas_total_steps": None,
    }
    if status == "ok" and pred is not None:
        row["pred_verdict"] = pred.get("verdict")
        row["pred_first_error_step"] = pred.get("first_error_step")
        row["verdict_match"] = row["pred_verdict"] == gt["verdict"]
        pred_reviews = _review_map(pred)
        if gt_reviews is not None and pred_reviews is not None:
            agreements, union = _compare_reviews(gt_reviews, pred_reviews)
            row["step_agreements"] = agreements
            row["step_union"] = union
            row["step_accuracy"] = agreements / union if union else 1.0
            row["solution_match"] = row["verdict_match"] and agreements == union
        cas = run_isolated(extract_step_latex(pred), timeout)
        row["cas_status"] = cas["status"]
        row["cas_covered"] = bool(cas["covered"])
        row["cas_parse_status"] = cas["parse_status"]
        row["cas_parsed_steps"] = cas["parsed_steps"]
        row["cas_total_steps"] = cas["total_steps"]
    elif gt_reviews is not None:
        row["step_agreements"] = 0
        row["step_union"] = len(gt_reviews)
        row["step_accuracy"] = 0.0
        row["solution_match"] = False
    if gt["verdict"] == "incorrect":
        row["first_error_match"], row["first_error_category"] = _first_error_outcome(gt, row)
    return row


def _confusion(rows: list[dict[str, Any]]) -> dict[str, Any]:
    system_labels = list(SYSTEM_VERDICTS) + [MISSING_LABEL]
    counts = {gt_label: {label: 0 for label in system_labels} for gt_label in GT_VERDICTS}
    for row in rows:
        label = row["pred_verdict"] if row["status"] == "ok" else MISSING_LABEL
        counts[row["gt_verdict"]][label] += 1
    return {
        "gt_labels": list(GT_VERDICTS),
        "system_labels": system_labels,
        "matrix": [[counts[gt_label][label] for label in system_labels] for gt_label in GT_VERDICTS],
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    evaluated = [row for row in rows if row["status"] == "ok"]
    verdict_matches = sum(bool(row["verdict_match"]) for row in rows)
    compared = [row for row in rows if row["step_agreements"] is not None]
    agreements = sum(row["step_agreements"] for row in compared)
    union = sum(row["step_union"] for row in compared)
    strict = [row for row in rows if row["solution_match"] is not None]
    strict_matches = sum(bool(row["solution_match"]) for row in strict)
    gt_incorrect = [row for row in rows if row["gt_verdict"] == "incorrect"]
    first_error_matches = sum(bool(row["first_error_match"]) for row in gt_incorrect)
    categories = Counter(row["first_error_category"] for row in gt_incorrect)
    covered = sum(bool(row["cas_covered"]) for row in rows)
    parseable = sum(row["cas_parse_status"] == "OK" for row in rows)
    return {
        "solution": {
            "gt_cases": total,
            "evaluated_cases": len(evaluated),
            "verdict_matches": verdict_matches,
            "verdict_accuracy": verdict_matches / total,
            "verdict_accuracy_on_evaluated": verdict_matches / len(evaluated) if evaluated else None,
            "step_accuracy": agreements / union if union else None,
            "step_compared_cases": len(compared),
            "solution_accuracy": strict_matches / len(strict) if strict else None,
            "solution_compared_cases": len(strict),
        },
        "first_error": {
            "gt_incorrect_cases": len(gt_incorrect),
            "first_error_accuracy": first_error_matches / len(gt_incorrect) if gt_incorrect else None,
            "matches": first_error_matches,
            "wrong_index": categories.get("wrong_index", 0),
            "no_error_reported": categories.get("no_error_reported", 0),
            "indeterminate": categories.get("indeterminate", 0),
            "missing_or_invalid": categories.get("missing_or_invalid", 0),
        },
        "cas": {
            "total_examples": total,
            "covered_examples": covered,
            "coverage": covered / total if total else None,
            "parseable_examples": parseable,
            "parse_rate": parseable / total if total else None,
        },
        "confusion_matrix": _confusion(rows),
    }


def evaluate(gt_path: Path | list[Path], predictions_path: Path, *, timeout: float = 10.0) -> dict[str, Any]:
    if timeout <= 0:
        raise EvaluationInputError("Timeout must be positive")
    gt_records = load_gt(gt_path)
    valid, invalid, record_count = load_predictions(predictions_path)
    invalid_by_id: dict[str, str] = {}
    for item in invalid:
        if isinstance(item["id"], str) and item["id"]:
            invalid_by_id.setdefault(item["id"], item["reason"])
    gt_ids = {record["id"] for record in gt_records}

    rows: list[dict[str, Any]] = []
    for gt in gt_records:
        record_id = gt["id"]
        if record_id in valid:
            status, note, pred = "ok", "", valid[record_id]
        elif record_id in invalid_by_id:
            status, note, pred = "invalid", invalid_by_id[record_id], None
        else:
            status, note, pred = "missing", "no prediction record", None
        rows.append(_case_row(gt, pred, status, note, timeout))

    return {
        "generated_at_utc": _now(),
        "gt": {"sources": [{"path": str(path), "sha256": _sha256(path)} for path in _gt_paths(gt_path)],
               **({"path": str(_gt_paths(gt_path)[0]), "sha256": _sha256(_gt_paths(gt_path)[0])} if len(_gt_paths(gt_path)) == 1 else {}),
               "cases": len(gt_records)},
        "predictions": {
            "path": str(predictions_path),
            "sha256": _sha256(predictions_path),
            "records": record_count,
            "evaluated": sum(row["status"] == "ok" for row in rows),
            "invalid": invalid,
            "extra_ids": sorted(set(valid) - gt_ids),
        },
        "cas": {
            "backend": "sympy",
            "sympy_version": sp.__version__,
            "process_isolated": True,
            "timeout_seconds": timeout,
        },
        "summary": _summary(rows),
        "cases": rows,
    }


def write_outputs(report: dict[str, Any], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    written.append(report_path)

    cases_path = output_dir / "results.csv"
    with cases_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CASE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report["cases"])
    written.append(cases_path)

    matrix = report["summary"]["confusion_matrix"]
    matrix_path = output_dir / "confusion_matrix.csv"
    with matrix_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["gt \\ system"] + matrix["system_labels"])
        for label, counts in zip(matrix["gt_labels"], matrix["matrix"]):
            writer.writerow([label] + counts)
    written.append(matrix_path)
    return written


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gt", type=Path, nargs="+", default=[Path("dataset/test_gt.json")], help="One or more ground-truth SolutionAnalysis arrays.")
    parser.add_argument("--predictions", type=Path, required=True, help="System SolutionAnalysis array to evaluate.")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/evaluation"), help="Directory for report.json, results.csv and confusion_matrix.csv.")
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-case CAS process timeout in seconds.")
    args = parser.parse_args(argv)

    report = evaluate([path.resolve() for path in args.gt], args.predictions.resolve(), timeout=args.timeout)
    paths = write_outputs(report, args.output_dir.resolve())

    solution = report["summary"]["solution"]
    first_error = report["summary"]["first_error"]
    cas = report["summary"]["cas"]
    print(f"verdict_accuracy: {solution['verdict_accuracy']:.2%} ({solution['verdict_matches']}/{solution['gt_cases']})")
    if solution["solution_accuracy"] is not None:
        print(f"solution_accuracy: {solution['solution_accuracy']:.2%} ({solution['solution_compared_cases']} comparable)")
    if solution["step_accuracy"] is not None:
        print(f"step_accuracy: {solution['step_accuracy']:.2%} ({solution['step_compared_cases']} comparable)")
    if first_error["first_error_accuracy"] is not None:
        print(f"first_error_accuracy: {first_error['first_error_accuracy']:.2%} ({first_error['matches']}/{first_error['gt_incorrect_cases']})")
    print(f"cas coverage: {cas['coverage']:.2%} ({cas['covered_examples']}/{cas['total_examples']}); parse_rate: {cas['parse_rate']:.2%}")
    for path in paths:
        print(f"wrote {path}")
    return report


if __name__ == "__main__":
    main()
