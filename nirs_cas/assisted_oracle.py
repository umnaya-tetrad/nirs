"""Reproducible comparison of frozen Gemini OCR and assisted-context artifacts."""

from __future__ import annotations

import json
from collections import Counter
import hashlib
from pathlib import Path
from typing import Any

from .contracts import analyze_assisted_contract, analyze_contract
from .task_spec import compile_task_spec
from .adapter import extract_step_latex
from .benchmark import run_isolated
from .answers import parse_answer


def _bundle(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items")
    if not isinstance(items, list) or len({x.get("id") for x in items}) != len(items):
        raise ValueError(f"Invalid reproducibility bundle: {path}")
    return items


def _metrics(
    predictions: list[dict[str, Any]], labels: dict[str, dict[str, Any]], verified=None
) -> dict[str, Any]:
    total = len(predictions)
    non_indeterminate = [
        item for item in predictions if item["verdict"] != "indeterminate"
    ]
    verdict_ok = [
        item for item in predictions if item["verdict"] == labels[item["id"]]["verdict"]
    ]
    first_ok = [
        item
        for item in predictions
        if item["verdict"] == labels[item["id"]]["verdict"]
        and item["first_error_step"] == labels[item["id"]].get("first_error_step")
    ]
    incorrect = [
        item for item in predictions if labels[item["id"]]["verdict"] == "incorrect"
    ]
    localized = [
        item
        for item in incorrect
        if item["verdict"] == "incorrect"
        and item["first_error_step"] == labels[item["id"]].get("first_error_step")
    ]
    if verified is None:
        verified = [
            item.get("problem", {}).get("verified_solution_covered", False)
            for item in predictions
        ]
    coverage = sum(verified) / total if total else 0
    fallbacks = Counter(
        reason
        for item in predictions
        if item["verdict"] == "indeterminate"
        for reason in set(
            item.get("problem", {}).get("fallback_reasons", [])
            or [
                r.get("note", "")
                for r in item.get("steps_reviewed", [])
                if r["verdict"] == "indeterminate"
            ]
        )
    )
    return {
        "examples": total,
        "coverage": coverage,
        "verified_solution_coverage": coverage,
        "verdict_coverage": len(non_indeterminate) / total if total else 0,
        "indeterminate_count": total - len(non_indeterminate),
        "indeterminate_reasons": dict(fallbacks),
        "indeterminate_share": (total - len(non_indeterminate)) / total if total else 0,
        "verdict_accuracy": len(verdict_ok) / total if total else 0,
        "first_error_accuracy": len(localized) / len(incorrect) if incorrect else None,
        "first_error_examples": len(incorrect),
        "first_error_accuracy_all": len(first_ok) / total if total else 0,
    }


def _classes(predictions, classes, verified):
    result = {}
    for task_class in sorted(set(classes)):
        group = [
            (p, v) for p, c, v in zip(predictions, classes, verified) if c == task_class
        ]
        result[task_class] = {
            "examples": len(group),
            "verified_solution_coverage": sum(v for _, v in group) / len(group),
            "verdict_coverage": sum(p["verdict"] != "indeterminate" for p, _ in group)
            / len(group),
            "task_aware_coverage": sum(
                p.get("problem", {}).get("context_check", {}).get("status")
                in ("valid", "invalid")
                for p, _ in group
            )
            / len(group),
            "indeterminate_reasons": dict(
                Counter(
                    reason
                    for p, _ in group
                    if p["verdict"] == "indeterminate"
                    for reason in set(p.get("problem", {}).get("fallback_reasons", []))
                )
            ),
        }
    return result


def _provenance(paths):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def _context_metrics(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    checks = [item.get("problem", {}).get("context_check", {}) for item in predictions]
    total = len(predictions)
    exact = [check for check in checks if check.get("status") in {"valid", "invalid"}]
    return {
        "examples": total,
        "task_aware_coverage": len(exact) / total if total else 0,
        "context_valid": sum(check.get("status") == "valid" for check in checks),
        "context_invalid": sum(check.get("status") == "invalid" for check in checks),
        "context_unsupported": sum(
            check.get("status") == "unsupported" for check in checks
        ),
    }


def run_comparison(
    ordinary_bundle: Path,
    assisted_bundle: Path,
    gt_path: Path,
    output: Path,
    repo_root: Path,
) -> dict[str, Any]:
    ordinary = _bundle(ordinary_bundle)
    assisted = _bundle(assisted_bundle)
    if [item["id"] for item in ordinary] != [item["id"] for item in assisted]:
        raise ValueError(
            "Ordinary and assisted bundles must have identical ordered IDs"
        )
    # Isolation turns parser/verifier edge cases into a documented abstention.
    ordinary_results = [
        run_isolated(extract_step_latex(item["contract"]), 10) for item in ordinary
    ]
    ordinary_predictions = [
        analyze_contract(item["contract"], repo_root, result=raw)
        for item, raw in zip(ordinary, ordinary_results)
    ]
    assisted_predictions = [
        analyze_assisted_contract(item["contract"], repo_root, timeout=10)
        for item in assisted
    ]
    # Labels enter only reporting, after every prediction is complete.
    labels = {
        item["id"]: item for item in json.loads(gt_path.read_text(encoding="utf-8"))
    }
    if set(labels) != {item["id"] for item in ordinary}:
        raise ValueError("GT labels must match the complete dev bundle exactly")
    classes = [
        compile_task_spec(item["contract"])["compilation"]["task_class"]
        for item in assisted
    ]
    ordinary_coverage = [raw["covered"] for raw in ordinary_results]
    assisted_coverage = [
        p["problem"]["verified_solution_covered"] for p in assisted_predictions
    ]
    report = {
        "evaluation": "FERMAT dev-20 only; labels joined after CAS prediction",
        "input_sha256": _provenance([ordinary_bundle, assisted_bundle, gt_path]),
        "ordinary": {
            "metrics": _metrics(ordinary_predictions, labels, ordinary_coverage),
            "class_coverage": _classes(
                ordinary_predictions, classes, ordinary_coverage
            ),
            "predictions": ordinary_predictions,
        },
        "assisted": {
            "metrics": _metrics(assisted_predictions, labels),
            "context_metrics": _context_metrics(assisted_predictions),
            "class_coverage": _classes(
                assisted_predictions, classes, assisted_coverage
            ),
            "predictions": assisted_predictions,
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    rows = [
        "# Gemini dev-20: ordinary OCR→CAS vs assisted context→TaskSpec→CAS",
        "",
        "| Режим | Verified solution coverage | Indeterminate | Verdict accuracy | First-error accuracy |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in ("ordinary", "assisted"):
        metric = report[name]["metrics"]
        rows.append(
            f"| {name} | {metric['coverage']:.0%} | {metric['indeterminate_share']:.0%} | {metric['verdict_accuracy']:.0%} | {metric['first_error_accuracy']:.0%} |"
        )
    context = report["assisted"]["context_metrics"]
    rows += [
        "",
        f"Task-aware coverage assisted: {context['task_aware_coverage']:.0%} ({context['context_valid']} exact-valid, {context['context_invalid']} exact-invalid, {context['context_unsupported']} unsupported).",
        "Verified solution coverage означает проверку всех записанных шагов и рёбер. Частично покрытое решение с локализованной ошибкой может получить incorrect и не войти в coverage.",
        "First-error accuracy считается только на GT incorrect; отказ не считается правильной локализацией. Сравнение ID строгое и зависит от совпадения сегментации OCR и GT.",
        "Ordinary local verdict сохраняется отдельно. Context unavailable не отменяет локальное доказательство; корректный финал не доказывает неподдержанные шаги.",
        "Только FERMAT dev-20. Mixed-20 — инженерный набор без GT-оценки. final-80 для этих правил не запускался.",
        "",
        "| Task class | Examples | Assisted verified coverage | Task-aware coverage |",
        "|---|---:|---:|---:|",
    ]
    for name, data in report["assisted"]["class_coverage"].items():
        rows.append(
            f"| {name} | {data['examples']} | {data['verified_solution_coverage']:.0%} | {data['task_aware_coverage']:.0%} |"
        )
    rows += ["", "Причины indeterminate (один пример может иметь несколько):"]
    rows += [
        f"- {reason}: {count}"
        for reason, count in report["assisted"]["metrics"][
            "indeterminate_reasons"
        ].items()
    ]
    (output / "comparison.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return report


def run_mixed_coverage(bundle: Path, output: Path, repo_root: Path) -> dict[str, Any]:
    """Engineering-only coverage view; it deliberately reads no GT labels."""
    items = _bundle(bundle)
    rows = []
    predictions = []
    classes = []
    for item in items:
        spec = compile_task_spec(item["contract"])
        prediction = analyze_assisted_contract(item["contract"], repo_root, timeout=10)
        predictions.append(prediction)
        classes.append(spec["compilation"]["task_class"])
        problem = prediction["problem"]
        rows.append(
            {
                "id": item["id"],
                "task_class": spec["compilation"]["task_class"],
                "verdict": prediction["verdict"],
                "first_error_step": prediction["first_error_step"],
                "verified_solution_covered": problem["verified_solution_covered"],
                "context_check": problem["context_check"],
                "graph_check": problem["graph_check"],
                "fallback_reason": problem["fallback_reasons"],
                "answer_normalization": [
                    parse_answer(s["latex"]).to_dict()
                    for s in spec["steps"]
                    if s.get("role") == "answer"
                ],
            }
        )
    output.mkdir(parents=True, exist_ok=True)
    verified = [p["problem"]["verified_solution_covered"] for p in predictions]
    report = {
        "evaluation": "mixed-20 engineering coverage only; no GT labels loaded",
        "input_sha256": _provenance([bundle]),
        "verified_solution_coverage": sum(verified) / len(verified) if verified else 0,
        "context_metrics": _context_metrics(predictions),
        "class_coverage": _classes(predictions, classes, verified),
        "indeterminate_count": sum(
            p["verdict"] == "indeterminate" for p in predictions
        ),
        "results": rows,
    }
    (output / "mixed_coverage.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Assisted-CAS: mixed-20 engineering coverage",
        "",
        "| ID | Task class | Verdict | Fallback reason |",
        "|---|---|---|---|",
    ]
    lines.extend(
        f"| {row['id']} | {row['task_class']} | {row['verdict']} | {'; '.join(row['fallback_reason']) or '—'} |"
        for row in rows
    )
    lines += [
        "",
        "| Task class | Examples | Verified solution coverage | Task-aware coverage |",
        "|---|---:|---:|---:|",
    ]
    lines.extend(
        f"| {name} | {data['examples']} | {data['verified_solution_coverage']:.0%} | {data['task_aware_coverage']:.0%} |"
        for name, data in report["class_coverage"].items()
    )
    (output / "mixed_coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
