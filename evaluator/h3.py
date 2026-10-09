"""H3: disagreement routing and selective automation between E2E and CAS."""
from __future__ import annotations

from typing import Any

from .h1 import DECIDABLE, system_label
from .runs import RunData

POLICIES = ("disagreement_routing", "e2e_only", "cas_only")


def _route(e2e_label: str, cas_label: str, policy: str) -> tuple[str, str]:
    if policy == "e2e_only":
        return "e2e", e2e_label
    if policy == "cas_only":
        return "cas", cas_label
    if cas_label == e2e_label and e2e_label in DECIDABLE:
        return "agreement", cas_label
    return "manual", "missing_or_failed"


def analyze_h3(e2e_run: RunData, cas_run: RunData, gt_by_id: dict[str, dict[str, Any]], ids: list[str],
               ocr_by_id: dict[str, str]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    policy_stats = {policy: {"correct": 0, "automated": 0} for policy in POLICIES}
    for record_id in ids:
        gt_verdict = gt_by_id[record_id]["verdict"]
        e2e_label = system_label(e2e_run.records.get(record_id))
        cas_label = system_label(cas_run.records.get(record_id))
        entry: dict[str, Any] = {
            "id": record_id, "gt_verdict": gt_verdict, "ocr_error_class": ocr_by_id.get(record_id),
            "e2e_label": e2e_label, "cas_label": cas_label, "agree": e2e_label == cas_label,
        }
        for policy in POLICIES:
            source, label = _route(e2e_label, cas_label, policy)
            correct = label == gt_verdict and label in DECIDABLE
            automated = label in DECIDABLE
            entry[f"{policy}_source"] = source
            entry[f"{policy}_label"] = label
            entry[f"{policy}_correct"] = correct
            policy_stats[policy]["correct"] += 1 if correct else 0
            policy_stats[policy]["automated"] += 1 if automated else 0
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
        }
    return {"rows": rows, "policies": policies, "risk_coverage": _risk_coverage(rows, ids)}


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
        coverage_from_disagreement = _disagreement_curve(rows, ids)
        result[policy] = curve if policy != "disagreement_routing" else coverage_from_disagreement
    return result


def _disagreement_curve(rows: list[dict[str, Any]], ids: list[str]) -> list[dict[str, float]]:
    by_id = {row["id"]: row for row in rows}
    ordered = sorted(ids, key=lambda record_id: (not by_id[record_id]["agree"], record_id))
    covered = correct = 0
    curve: list[dict[str, float]] = [{"coverage": 0.0, "risk": 0.0}]
    for record_id in ordered:
        row = by_id[record_id]
        if row["disagreement_routing_label"] in DECIDABLE:
            covered += 1
            correct += 1 if row["disagreement_routing_correct"] else 0
            curve.append({"coverage": covered / len(ids), "risk": (covered - correct) / covered})
    return curve
