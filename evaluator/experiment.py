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
from .domains import validate as validate_domains

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


def _domain_metrics(path: Path | None, manifest: ExperimentManifest, runs: dict[str, RunData], gt_by_id: dict[str, dict[str, Any]], repo_root: Path) -> dict[str, Any]:
    if path is None:
        return {"available": False, "reason": "No domain sidecar declared."}
    # A manifest loaded from dataset_manifest retains that exact source in
    # ids_path.  Never validate a v2 sidecar against the old final-80 list.
    domain_manifest = manifest.ids_path if manifest.ids_path is not None else repo_root / "dataset/manifests/fermat_final_80.json"
    summary = validate_domains(path, domain_manifest)
    import json
    annotations = json.loads(path.read_text(encoding="utf-8")).get("records", [])
    by_id = {row["solution_id"]: row for row in annotations}
    rows: list[dict[str, Any]] = []
    for domain in sorted({row["domain"] for row in annotations}):
        domain_ids = [record_id for record_id in manifest.ids if by_id.get(record_id, {}).get("domain") == domain]
        for run_id, run in runs.items():
            metrics = run_metrics(run, gt_by_id, domain_ids)
            rows.append({"domain": domain, "run_id": run_id, "examples": len(domain_ids),
                         "small_n_warning": len(domain_ids) < 5, "coverage": metrics["coverage"],
                         "accuracy_all": metrics["accuracy_all"], "accuracy_on_covered": metrics["accuracy_on_covered"],
                         "status_counts": metrics["status_counts"]})
    return {"available": True, "sidecar": str(path), "validation": summary, "rows": rows}


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
    expected_ids = set(manifest.ids)
    for spec in manifest.runs:
        run = runs[spec.run_id]
        if not run.id_set.issubset(expected_ids):
            missing = sorted(expected_ids - run.id_set)
            unexpected = sorted(run.id_set - expected_ids)
            raise EvaluationInputError(
                f"run {spec.run_id}: source contains IDs outside the manifest "
                f"(missing={missing}, unexpected={unexpected})")
        if run.extraction is not None and not set(run.extraction).issubset(expected_ids):
            missing = sorted(expected_ids - set(run.extraction))
            unexpected = sorted(set(run.extraction) - expected_ids)
            raise EvaluationInputError(
                f"run {spec.run_id}: extraction artifacts contain IDs outside the manifest "
                f"(missing={missing}, unexpected={unexpected})")

    pair_payload: dict[str, Any] = {}
    h2_payload: dict[str, Any] = {}
    h3_payload: dict[str, Any] = {}
    for pair in manifest.h1_pairs:
        e2e_run, cas_run = runs[pair["e2e_run"]], runs[pair["cas_run"]]
        # A partial run is evaluable but must never masquerade as a complete
        # final experiment. Missing IDs become explicit abstentions in H1/H3.
        e2e_metrics = run_metrics(e2e_run, gt_by_id, manifest.ids)
        cas_metrics = run_metrics(cas_run, gt_by_id, manifest.ids)
        paired = paired_analysis(e2e_run, cas_run, gt_by_id, manifest.ids, e2e_metrics, cas_metrics)
        key = _key(pair)
        pair_payload[key] = {"provider": pair["provider"], "e2e_run": pair["e2e_run"], "cas_run": pair["cas_run"],
                             "e2e": e2e_metrics, "cas": cas_metrics, "paired": paired}
    for pair in manifest.h1_pairs:
        e2e_run, cas_run = runs[pair["e2e_run"]], runs[pair["cas_run"]]
        ocr_by_id = {}
        if cas_run.extraction is not None and cas_run.id_set == expected_ids:
            h2_analysis = analyze_h2(cas_run, gt_by_id, cas_on_gt, manifest.ids)
            key = _key(pair)
            h2_payload[key] = {"provider": pair["provider"], "run_id": pair["cas_run"], **h2_analysis}
            ocr_by_id = _ocr_classes(h2_analysis)
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
            "ids_source": ({"path": str(manifest.ids_path.relative_to(repo_root)) if repo_root in manifest.ids_path.parents else str(manifest.ids_path),
                            "sha256": hashlib.sha256(manifest.ids_path.read_bytes()).hexdigest()}
                           if manifest.ids_path is not None else None),
            "gt_sources": [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in manifest.gt_paths],
            "error_policy": manifest.error_policy,
            "has_simulated_runs": any(spec.simulated for spec in manifest.runs),
            "scientific_report_ready": not any(spec.simulated for spec in manifest.runs) and all(
                runs[spec.run_id].id_set == expected_ids for spec in manifest.runs),
            "complete": all(runs[spec.run_id].id_set == expected_ids for spec in manifest.runs),
            "incomplete_runs": {spec.run_id: sorted(expected_ids - runs[spec.run_id].id_set)
                                for spec in manifest.runs if runs[spec.run_id].id_set != expected_ids},
        },
        "runs": [{"run_id": spec.run_id, "system": spec.system, "provider": spec.provider, "mode": spec.mode,
                  "simulated": spec.simulated, "model": spec.model, "prompt_version": spec.prompt_version,
                  "prompt_sha256": spec.prompt_sha256, "git_commit": spec.git_commit,
                  "provenance": runs[spec.run_id].provenance, "unmapped": runs[spec.run_id].unmapped,
                  "metrics": run_metrics(runs[spec.run_id], gt_by_id, manifest.ids)}
                 for spec in manifest.runs],
        "h1": {"pairs": pair_payload,
               "per_case": [{"provider": pair["provider"], **row}
                            for pair in pair_payload.values() for row in pair["paired"]["rows"]]},
        # Top-level fields retain compatibility for exploratory callers; final
        # reports and CSVs consume every provider entry under pairs.
        "h2": {"pairs": h2_payload,
               "run_id": next(iter(h2_payload.values()))["run_id"] if h2_payload else None,
               "per_case": [{"provider": pair["provider"], "run_id": pair["run_id"], **row}
                            for pair in h2_payload.values() for row in pair["rows"]],
               "by_error_class": next(iter(h2_payload.values()))["by_error_class"] if h2_payload else [],
               "overall": next(iter(h2_payload.values()))["overall"] if h2_payload else {}},
        "h3": {"pairs": h3_payload,
               "policies": next(iter(h3_payload.values()))["policies"] if h3_payload else {},
               "per_case": [{"provider": pair["provider"], **row}
                            for pair in h3_payload.values() for row in pair["rows"]]},
        "cases": _cases(manifest, runs, gt_by_id),
        "domains": _domain_metrics(manifest.domain_annotations_path, manifest, runs, gt_by_id, repo_root),
        "limitations": LIMITATIONS,
    }
    payload["unmapped_records"] = sum(len(run.unmapped) for run in runs.values())
    write_all(Path(output_dir), payload)
    return payload
