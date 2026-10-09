"""Assemble the H1/H2/H3 experiment from a manifest and write the report bundle."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .evaluator import EvaluationInputError, load_gt
from .h1 import DECIDABLE, paired_analysis, run_metrics, system_label
from .h2 import analyze_h2
from .h3 import analyze_h3
from .manifest import ExperimentManifest, load_manifest
from .report import write_all
from .runs import RunData, load_cas_on_gt, load_run

LIMITATIONS = [
    "Frozen and simulated sources keep api_failed/invalid_contract/missing cases in every denominator.",
    "CAS-on-GT uses reference steps; it bounds the pipeline but is not available at inference time.",
    "Prompt/CAS tuning saw all 100 GT examples, so results on dev/final splits are exploratory, not independent holdout.",
    "CDN/OS availability noise and OCR failures are reported as statuses and are not silently dropped.",
]


def _key(pair: dict[str, str]) -> str:
    return f"{pair['provider']}:{pair['e2e_run']}__{pair['cas_run']}"


def _cases(manifest: ExperimentManifest, runs: dict[str, RunData], gt_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for record_id in manifest.ids:
        gt = gt_by_id[record_id]
        row: dict[str, Any] = {
            "id": record_id, "gt_verdict": gt["verdict"],
            "gt_first_error_step": gt.get("first_error_step"),
        }
        for spec in manifest.runs:
            record = runs[spec.run_id].records.get(record_id)
            row[f"{spec.run_id}_status"] = record.status if record is not None else "missing"
            row[f"{spec.run_id}_verdict"] = system_label(record)
            row[f"{spec.run_id}_first_error_step"] = (
                record.contract.get("first_error_step") if record is not None and record.contract is not None else None)
            row[f"{spec.run_id}_correct"] = system_label(record) == gt["verdict"] and gt["verdict"] in DECIDABLE
        rows.append(row)
    return rows


def _ocr_classes(h2: dict[str, Any]) -> dict[str, str]:
    return {row["id"]: row["error_class"] for row in h2["rows"]}


def run_experiment(manifest_path: Path, output_dir: Path, repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = (repo_root or Path(__file__).resolve().parents[1]).resolve()
    manifest = load_manifest(Path(manifest_path), repo_root)
    gt_records = load_gt(manifest.gt_paths)
    gt_by_id = {record["id"]: record for record in gt_records}
    missing_gt = [record_id for record_id in manifest.ids if record_id not in gt_by_id]
    if missing_gt:
        raise EvaluationInputError(f"GT lacks manifest ids: {missing_gt}")
    cas_on_gt = load_cas_on_gt(manifest.cas_on_gt_path, manifest.ids) if manifest.cas_on_gt_path else None
    runs = {spec.run_id: load_run(spec, manifest, repo_root) for spec in manifest.runs}

    pair_payload: dict[str, Any] = {}
    h3_payload: dict[str, Any] = {}
    selected_cas: str | None = None
    for pair in manifest.h1_pairs:
        e2e_run, cas_run = runs[pair["e2e_run"]], runs[pair["cas_run"]]
        if e2e_run.id_set != cas_run.id_set:
            raise EvaluationInputError(
                f"pair {_key(pair)}: id sets differ (e2e {len(e2e_run.id_set)}, cas {len(cas_run.id_set)})")
        e2e_metrics = run_metrics(e2e_run, gt_by_id, manifest.ids)
        cas_metrics = run_metrics(cas_run, gt_by_id, manifest.ids)
        paired = paired_analysis(e2e_run, cas_run, gt_by_id, manifest.ids, e2e_metrics, cas_metrics)
        key = _key(pair)
        pair_payload[key] = {"provider": pair["provider"], "e2e_run": pair["e2e_run"], "cas_run": pair["cas_run"],
                             "e2e": e2e_metrics, "cas": cas_metrics, "paired": paired}
        if selected_cas is None and cas_run.extraction is not None:
            selected_cas = pair["cas_run"]
    if cas_on_gt is not None and selected_cas is not None:
        h2_analysis = analyze_h2(runs[selected_cas], gt_by_id, cas_on_gt, manifest.ids)
        ocr_by_id = _ocr_classes(h2_analysis)
        h2_payload = {"run_id": selected_cas, "per_case": h2_analysis["rows"],
                      "by_error_class": h2_analysis["by_error_class"], "overall": h2_analysis["overall"]}
        for pair in manifest.h1_pairs:
            e2e_run, cas_run = runs[pair["e2e_run"]], runs[pair["cas_run"]]
            analysis = analyze_h3(e2e_run, cas_run, gt_by_id, manifest.ids, ocr_by_id)
            h3_payload[_key(pair)] = {"provider": pair["provider"], "e2e_run": pair["e2e_run"],
                                      "cas_run": pair["cas_run"], **analysis}
    payload = {
        "experiment": {
            "manifest_path": str(manifest.path.relative_to(repo_root)) if repo_root in manifest.path.parents else str(manifest.path),
            "manifest_sha256": hashlib.sha256(manifest.path.read_bytes()).hexdigest(),
            "experiment_id": manifest.experiment_id,
            "evaluation_note": manifest.evaluation_note,
            "split": manifest.split,
            "ids_count": len(manifest.ids),
            "gt_sources": [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in manifest.gt_paths],
            "error_policy": manifest.error_policy,
        },
        "runs": [{"run_id": spec.run_id, "system": spec.system, "provider": spec.provider, "mode": spec.mode,
                  "simulated": spec.simulated, "model": spec.model, "prompt_version": spec.prompt_version,
                  "prompt_sha256": spec.prompt_sha256, "git_commit": spec.git_commit,
                  "provenance": runs[spec.run_id].provenance, "unmapped": runs[spec.run_id].unmapped,
                  "metrics": run_metrics(runs[spec.run_id], gt_by_id, manifest.ids)}
                 for spec in manifest.runs],
        "h1": {"pairs": pair_payload, "per_case": next(iter(pair_payload.values()))["paired"]["rows"] if pair_payload else []},
        "h2": {**h2_payload, "per_case": h2_payload.get("per_case", []), "by_error_class": h2_payload.get("by_error_class", []),
               "overall": h2_payload.get("overall", {})},
        "h3": {"pairs": h3_payload, "policies": next(iter(h3_payload.values()))["policies"] if h3_payload else {},
               "per_case": next(iter(h3_payload.values()))["rows"] if h3_payload else []},
        "cases": _cases(manifest, runs, gt_by_id),
        "limitations": LIMITATIONS,
    }
    payload["unmapped_records"] = sum(len(run.unmapped) for run in runs.values())
    write_all(Path(output_dir), payload)
    return payload
