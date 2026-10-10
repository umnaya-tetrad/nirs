"""H3: disagreement routing and selective automation between E2E and CAS."""
from __future__ import annotations

from typing import Any

from .h1 import DECIDABLE, system_label
from .runs import RunData

POLICIES = ("disagreement_only", "disagreement_or_cas_indeterminate")


def _route(e2e_label: str, cas_label: str, policy: str) -> tuple[str, str]:
    both_determinate = e2e_label in DECIDABLE and cas_label in DECIDABLE
    if policy == "disagreement_only":
        # An abstention is not a neural-symbolic disagreement.  This policy
        # keeps a determinate E2E decision automated unless both systems made
        # incompatible determinate decisions.
        if both_determinate and e2e_label != cas_label:
            return "manual_disagreement", "missing_or_failed"
        return ("e2e", e2e_label) if e2e_label in DECIDABLE else ("manual_api_or_e2e_abstention", "missing_or_failed")
    if both_determinate and e2e_label == cas_label:
        return "agreement", e2e_label
    return "manual_disagreement_or_cas_indeterminate", "missing_or_failed"


def analyze_h3(e2e_run: RunData, cas_run: RunData, gt_by_id: dict[str, dict[str, Any]], ids: list[str],
               ocr_by_id: dict[str, str]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    policy_stats = {policy: {"correct": 0, "automated": 0, "manual": 0,
                              "automated_e2e_errors": 0, "manual_e2e_errors": 0,
                              "e2e_errors": 0, "automated_ids": [], "manual_ids": []}
                    for policy in POLICIES}
    comparable_pairs = agreements = 0
    for record_id in ids:
        gt_verdict = gt_by_id[record_id]["verdict"]
        e2e_label = system_label(e2e_run.records.get(record_id))
        cas_label = system_label(cas_run.records.get(record_id))
        comparable = e2e_label in DECIDABLE and cas_label in DECIDABLE
        if comparable:
            comparable_pairs += 1
            agreements += int(e2e_label == cas_label)
        entry: dict[str, Any] = {
            "id": record_id, "gt_verdict": gt_verdict, "ocr_error_class": ocr_by_id.get(record_id),
            "e2e_label": e2e_label, "cas_label": cas_label,
            # ``agree`` is deliberately null when CAS abstains/fails: that is
            # not a meaningful neural-symbolic disagreement.
            "agree": e2e_label == cas_label if comparable else None,
            "comparison_status": "comparable" if comparable else "cas_or_e2e_not_decidable",
        }
        for policy in POLICIES:
            source, label = _route(e2e_label, cas_label, policy)
            correct = label == gt_verdict and label in DECIDABLE
            automated = label in DECIDABLE
            entry[f"{policy}_source"] = source
            entry[f"{policy}_label"] = label
            entry[f"{policy}_correct"] = correct
            stats = policy_stats[policy]
            stats["correct"] += 1 if correct else 0
            stats["automated"] += 1 if automated else 0
            stats["manual"] += 0 if automated else 1
            stats["automated_ids" if automated else "manual_ids"].append(record_id)
            e2e_error = e2e_label in DECIDABLE and e2e_label != gt_verdict
            stats["e2e_errors"] += 1 if e2e_error else 0
            if e2e_error:
                stats["automated_e2e_errors" if automated else "manual_e2e_errors"] += 1
        rows.append(entry)
    total = len(ids)
    policies: dict[str, Any] = {}
    for policy in POLICIES:
        stats = policy_stats[policy]
        policies[policy] = {
            "accuracy_all": stats["correct"] / total if total else 0.0,
            "accuracy_on_automated": stats["correct"] / stats["automated"] if stats["automated"] else None,
            "automation_rate": stats["automated"] / total if total else 0.0,
            "manual_rate": (total - stats["automated"]) / total if total else 0.0,
            "manual_queue_e2e_error_rate": (stats["manual_e2e_errors"] / stats["manual"]
                                            if stats["manual"] else None),
            "manual_queue_e2e_error_precision": (stats["manual_e2e_errors"] / stats["manual"]
                                                   if stats["manual"] else None),
            "captured_e2e_error_recall": (stats["manual_e2e_errors"] / stats["e2e_errors"]
                                            if stats["e2e_errors"] else None),
            "e2e_errors_total": stats["e2e_errors"],
            "e2e_errors_automated": stats["automated_e2e_errors"],
            "e2e_errors_manual": stats["manual_e2e_errors"],
            "automated_count": stats["automated"],
            "manual_count": stats["manual"],
            "automated_ids": stats["automated_ids"],
            "manual_ids": stats["manual_ids"],
        }
    return {"rows": rows, "policies": policies, "risk_coverage": _risk_coverage(rows, ids),
            "comparison": {"total": total, "comparable_pairs": comparable_pairs,
                           "agreement_count": agreements,
                           "agreement_rate_on_comparable": agreements / comparable_pairs if comparable_pairs else None,
                           "excluded_not_decidable": total - comparable_pairs}}


def _risk_coverage(rows: list[dict[str, Any]], ids: list[str]) -> dict[str, list[dict[str, float]]]:
    result: dict[str, list[dict[str, float]]] = {}
    for policy in POLICIES:
        ordered = list(ids)
        covered = correct = 0
        curve: list[dict[str, float]] = [{"coverage": 0.0, "risk": 0.0}]
        by_id = {row["id"]: row for row in rows}
        for record_id in ordered:
            row = by_id[record_id]
            if row[f"{policy}_label"] in DECIDABLE:
                covered += 1
                correct += 1 if row[f"{policy}_correct"] else 0
                curve.append({"coverage": covered / len(ids), "risk": (covered - correct) / covered})
        coverage_from_disagreement = _disagreement_curve(rows, ids, policy)
        result[policy] = coverage_from_disagreement
    return result


def _disagreement_curve(rows: list[dict[str, Any]], ids: list[str], policy: str) -> list[dict[str, float]]:
    by_id = {row["id"]: row for row in rows}
    # Abstentions are never promoted as agreements in the risk/coverage plot.
    ordered = sorted(ids, key=lambda record_id: (by_id[record_id]["agree"] is not True, record_id))
    covered = correct = 0
    curve: list[dict[str, float]] = [{"coverage": 0.0, "risk": 0.0}]
    for record_id in ordered:
        row = by_id[record_id]
        if row[f"{policy}_label"] in DECIDABLE:
            covered += 1
            correct += 1 if row[f"{policy}_correct"] else 0
            curve.append({"coverage": covered / len(ids), "risk": (covered - correct) / covered})
    return curve
