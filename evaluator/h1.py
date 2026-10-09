"""H1: end-to-end versus extraction->CAS on the same provider and IDs."""
from __future__ import annotations

from collections import Counter
from typing import Any

from .runs import STATUS_OK, RunData
from .ocr import align_steps
from .stats import mcnemar_exact, paired_bootstrap_ci, precision_recall_f1, wilson_interval

LABELS = ("correct", "incorrect", "indeterminate", "missing_or_failed")
DECIDABLE = ("correct", "incorrect")


def system_label(record) -> str:
    if record is None or record.status != STATUS_OK or not isinstance(record.contract, dict):
        return "missing_or_failed"
    verdict = record.contract.get("verdict")
    return verdict if verdict in DECIDABLE + ("indeterminate",) else "missing_or_failed"


def _is_correct(record, gt_verdict: str) -> bool:
    return system_label(record) == gt_verdict and gt_verdict in DECIDABLE


def _aligned_first_error_match(record, gt_record: dict[str, Any]) -> bool:
    """Evaluate localization after step alignment, not by accidental ID equality.

    VLM extraction is free to split or merge written lines.  A predicted first
    error is counted as localized only when its extracted step aligns to the GT
    first-error step; an extra/unmatched line has no such correspondence.
    """
    if (system_label(record) != "incorrect" or record is None or not isinstance(record.contract, dict)
            or not isinstance(gt_record.get("first_error_step"), str)):
        return False
    predicted_step = record.contract.get("first_error_step")
    predicted_steps = record.contract.get("steps")
    gt_steps = gt_record.get("steps")
    if not isinstance(predicted_step, str) or not isinstance(predicted_steps, list) or not isinstance(gt_steps, list):
        return False
    for entry in align_steps(gt_steps, predicted_steps):
        if (entry["gt_step_id"] == gt_record["first_error_step"]
                and entry["pred_step_id"] == predicted_step
                and entry["status"] in ("equal", "substituted")):
            return True
    return False


def run_metrics(run: RunData, gt_by_id: dict[str, dict[str, Any]], ids: list[str]) -> dict[str, Any]:
    confusion = {verdict: {label: 0 for label in LABELS} for verdict in ("correct", "incorrect")}
    status_counts: Counter[str] = Counter()
    correct = covered = wrong_covered = 0
    indeterminate = 0
    first_error_hits = first_error_aligned_hits = first_error_total = 0
    fp = fn = tp = tn = 0
    missing_ids: list[str] = []
    vlm_latencies: list[int] = []
    cas_latencies: list[int] = []
    pipeline_latencies: list[int] = []
    tokens_in = tokens_out = 0
    provider_reported_cost_rub = estimated_provider_cost_rub = 0.0
    provider_reported_cost_cases = estimated_provider_cost_cases = 0
    for record_id in ids:
        record = run.records.get(record_id)
        gt_verdict = gt_by_id[record_id]["verdict"]
        label = system_label(record)
        status_counts[record.status if record is not None else "missing"] += 1
        if record is None or record.status != STATUS_OK:
            missing_ids.append(record_id)
        confusion[gt_verdict][label] += 1
        # Full-set binary metric policy: an abstention/failed response did not
        # detect an error.  It therefore counts as FN for an incorrect GT and
        # as TN for a correct GT.  Coverage and selective accuracy below keep
        # that policy from being mistaken for ordinary covered-only accuracy.
        if gt_verdict == "incorrect":
            if label == "incorrect":
                tp += 1
            else:
                fn += 1
        elif label == "incorrect":
            fp += 1
        else:
            tn += 1
        if label in DECIDABLE:
            covered += 1
            if label == gt_verdict:
                correct += 1
            else:
                wrong_covered += 1
        elif label == "indeterminate":
            indeterminate += 1
        if gt_verdict == "incorrect":
            first_error_total += 1
            if (label == "incorrect" and record is not None and record.contract is not None
                    and record.contract.get("first_error_step") == gt_by_id[record_id].get("first_error_step")):
                first_error_hits += 1
            if _aligned_first_error_match(record, gt_by_id[record_id]):
                first_error_aligned_hits += 1
        if record is not None and record.vlm_latency_ms is not None:
            vlm_latencies.append(record.vlm_latency_ms)
        if record is not None and record.cas_latency_ms is not None:
            cas_latencies.append(record.cas_latency_ms)
        if record is not None:
            components = [value for value in (record.vlm_latency_ms, record.cas_latency_ms) if value is not None]
            if components:
                pipeline_latencies.append(sum(components))
        if record is not None:
            tokens_in += record.vlm_tokens_in or 0
            tokens_out += record.vlm_tokens_out or 0
            if record.cost_rub is not None:
                if record.cost_kind == "provider_reported":
                    provider_reported_cost_rub += record.cost_rub
                    provider_reported_cost_cases += 1
                elif record.cost_kind == "estimated":
                    estimated_provider_cost_rub += record.cost_rub
                    estimated_provider_cost_cases += 1
    total = len(ids)
    coverage = covered / total if total else 0.0
    interval = wilson_interval(covered, total)
    token_rate_estimate = None
    if run.spec.pricing is not None:
        token_rate_estimate = tokens_in / 1e6 * run.spec.pricing["input_per_million"] + tokens_out / 1e6 * run.spec.pricing["output_per_million"]
    incorrect_metrics = precision_recall_f1(tp, fp, fn)
    specificity = tn / (tn + fp) if tn + fp else None
    balanced_accuracy = ((incorrect_metrics["recall"] + specificity) / 2) if specificity is not None else None
    gt_incorrect = sum(gt_by_id[record_id]["verdict"] == "incorrect" for record_id in ids)
    gt_correct = total - gt_incorrect
    always_incorrect_accuracy = gt_incorrect / total if total else 0.0
    return {
        "run_id": run.spec.run_id,
        "system": run.spec.system,
        "provider": run.spec.provider,
        "examples": total,
        "status_counts": {key: status_counts.get(key, 0) for key in ("ok", "api_failed", "invalid_contract", "missing")},
        "confusion": confusion,
        "accuracy_all": correct / total if total else 0.0,
        "accuracy_all_ci95": wilson_interval(correct, total),
        "accuracy_on_covered": correct / covered if covered else None,
        "coverage": coverage,
        "coverage_ci95": interval,
        "indeterminate_share": indeterminate / total if total else 0.0,
        "selective_risk": wrong_covered / covered if covered else None,
        "first_error_accuracy_on_incorrect": first_error_hits / first_error_total if first_error_total else None,
        "first_error_accuracy_aligned_on_incorrect": (
            first_error_aligned_hits / first_error_total if first_error_total else None),
        "incorrect_detection": {**incorrect_metrics, "specificity": specificity,
                                "balanced_accuracy": balanced_accuracy,
                                "policy": "abstention_as_not_detected"},
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn,
                             "positive_class": "incorrect", "policy": "abstention_as_not_detected"},
        "always_incorrect_baseline": {
            "accuracy_all": always_incorrect_accuracy,
            "accuracy_all_ci95": wilson_interval(gt_incorrect, total),
            "precision": always_incorrect_accuracy, "recall": 1.0 if gt_incorrect else None,
            "specificity": 0.0 if gt_correct else None,
            "balanced_accuracy": 0.5 if gt_incorrect and gt_correct else None,
            "examples": total, "correct_gt": gt_correct, "incorrect_gt": gt_incorrect,
        },
        "mean_vlm_latency_ms": (sum(vlm_latencies) / len(vlm_latencies)) if vlm_latencies else None,
        "mean_cas_latency_ms": (sum(cas_latencies) / len(cas_latencies)) if cas_latencies else None,
        "mean_pipeline_latency_ms": (sum(pipeline_latencies) / len(pipeline_latencies)) if pipeline_latencies else None,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_rub": {
            "provider_reported": provider_reported_cost_rub if provider_reported_cost_cases else None,
            "provider_reported_cases": provider_reported_cost_cases,
            "provider_estimated": estimated_provider_cost_rub if estimated_provider_cost_cases else None,
            "provider_estimated_cases": estimated_provider_cost_cases,
            "token_rate_estimate": token_rate_estimate,
            "token_rate_estimate_note": "Estimate from manifest rates; image-token accounting depends on provider usage semantics.",
        },
        "missing_ids": missing_ids,
    }


def paired_analysis(e2e_run: RunData, cas_run: RunData, gt_by_id: dict[str, dict[str, Any]], ids: list[str],
                    e2e_metrics: dict[str, Any], cas_metrics: dict[str, Any]) -> dict[str, Any]:
    both_right = e2e_only = cas_only = both_wrong = 0
    differences: list[float] = []
    rows: list[dict[str, Any]] = []
    for record_id in ids:
        gt_verdict = gt_by_id[record_id]["verdict"]
        e2e_correct = _is_correct(e2e_run.records.get(record_id), gt_verdict)
        cas_correct = _is_correct(cas_run.records.get(record_id), gt_verdict)
        if e2e_correct and cas_correct:
            both_right += 1
        elif e2e_correct:
            e2e_only += 1
        elif cas_correct:
            cas_only += 1
        else:
            both_wrong += 1
        differences.append((1.0 if e2e_correct else 0.0) - (1.0 if cas_correct else 0.0))
        rows.append({
            "id": record_id, "gt_verdict": gt_verdict,
            "e2e_label": system_label(e2e_run.records.get(record_id)),
            "cas_label": system_label(cas_run.records.get(record_id)),
            "e2e_correct": e2e_correct, "cas_correct": cas_correct,
        })
    total = len(ids)
    return {
        "both_correct": both_right, "e2e_only_correct": e2e_only,
        "cas_only_correct": cas_only, "both_wrong": both_wrong,
        "agreement": (both_right + both_wrong) / total if total else 0.0,
        "mcnemar_exact_p": mcnemar_exact(e2e_only, cas_only),
        "bootstrap_accuracy_difference": paired_bootstrap_ci(differences),
        "accuracy_difference": e2e_metrics["accuracy_all"] - cas_metrics["accuracy_all"],
        "rows": rows,
    }
