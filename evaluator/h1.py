"""H1: end-to-end versus extraction->CAS on the same provider and IDs."""
from __future__ import annotations

from collections import Counter
from typing import Any

from .runs import STATUS_OK, RunData
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


def run_metrics(run: RunData, gt_by_id: dict[str, dict[str, Any]], ids: list[str]) -> dict[str, Any]:
    confusion = {verdict: {label: 0 for label in LABELS} for verdict in ("correct", "incorrect")}
    status_counts: Counter[str] = Counter()
    correct = covered = wrong_covered = 0
    indeterminate = 0
    first_error_hits = first_error_total = 0
    fp = fn = tp = 0
    missing_ids: list[str] = []
    vlm_latencies: list[int] = []
    tokens_in = tokens_out = 0
    for record_id in ids:
        record = run.records.get(record_id)
        gt_verdict = gt_by_id[record_id]["verdict"]
        label = system_label(record)
        status_counts[record.status if record is not None else "missing"] += 1
        if record is None or record.status != STATUS_OK:
            missing_ids.append(record_id)
        confusion[gt_verdict][label] += 1
        if label in DECIDABLE:
            covered += 1
            if label == gt_verdict:
                correct += 1
                if gt_verdict == "incorrect":
                    tp += 1
            else:
                wrong_covered += 1
                if gt_verdict == "incorrect":
                    fn += 1
                if gt_verdict == "correct":
                    fp += 1
        elif label == "indeterminate":
            indeterminate += 1
        if gt_verdict == "incorrect":
            first_error_total += 1
            if (label == "incorrect" and record is not None and record.contract is not None
                    and record.contract.get("first_error_step") == gt_by_id[record_id].get("first_error_step")):
                first_error_hits += 1
        if record is not None and record.vlm_latency_ms is not None:
            vlm_latencies.append(record.vlm_latency_ms)
        if record is not None:
            tokens_in += record.vlm_tokens_in or 0
            tokens_out += record.vlm_tokens_out or 0
    total = len(ids)
    coverage = covered / total if total else 0.0
    interval = wilson_interval(covered, total)
    cost = None
    if run.spec.pricing is not None:
        cost = tokens_in / 1e6 * run.spec.pricing["input_per_million"] + tokens_out / 1e6 * run.spec.pricing["output_per_million"]
    return {
        "run_id": run.spec.run_id,
        "system": run.spec.system,
        "provider": run.spec.provider,
        "examples": total,
        "status_counts": {key: status_counts.get(key, 0) for key in ("ok", "api_failed", "invalid_contract", "missing")},
        "confusion": confusion,
        "accuracy_all": correct / total if total else 0.0,
        "accuracy_on_covered": correct / covered if covered else None,
        "coverage": coverage,
        "coverage_ci95": interval,
        "indeterminate_share": indeterminate / total if total else 0.0,
        "selective_risk": wrong_covered / covered if covered else None,
        "first_error_accuracy_on_incorrect": first_error_hits / first_error_total if first_error_total else None,
        "incorrect_detection": precision_recall_f1(tp, fp, fn),
        "mean_vlm_latency_ms": (sum(vlm_latencies) / len(vlm_latencies)) if vlm_latencies else None,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "estimated_cost": cost,
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
