"""Run the task-aware CAS branch over saved LLM-assisted extraction artifacts.

This is intentionally separate from :mod:`nirs_cas.oracle`: the ordinary
oracle projects its input to ``steps[].latex``.  Here ``task``, givens, goal,
step roles and graph edges are inputs to the verifier and remain present in
the emitted SolutionAnalysis records.
"""
from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from .contracts import analyze_assisted_contract


def _read_json(path: Path) -> Any:
    return json.loads(path.read_bytes().decode("utf-8-sig"))


def _input_files(inputs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for supplied in inputs:
        path = Path(supplied)
        if path.is_dir():
            files.extend(sorted(item for item in path.glob("*.json") if item.name != "run_metadata.json"))
        else:
            files.append(path)
    if not files:
        raise ValueError("No JSON assisted-extraction artifacts found")
    return files


def load_assisted_records(inputs: list[Path]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Load saved successful artifacts; return malformed/failed artifacts as diagnostics.

    A runner persists one JSON object per request, while frozen reproducibility
    bundles use ``{\"items\": [...]}``.  Both formats are accepted without
    transforming the semantic contract.
    """
    records: list[dict[str, Any]] = []
    sources: list[dict[str, str]] = []
    seen: set[str] = set()
    for path in _input_files(inputs):
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8-sig"))
        sources.append({"path": path.as_posix(), "sha256": hashlib.sha256(raw).hexdigest()})
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            items = payload["items"]
        elif isinstance(payload, list):
            items = payload
        else:
            items = [payload]
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f"{path}: artifact is not an object")
            contract = item.get("contract", item)
            if not isinstance(contract, dict):
                raise ValueError(f"{path}: contract is not an object")
            identifier = contract.get("id", item.get("case_id"))
            if not isinstance(identifier, str) or not identifier:
                raise ValueError(f"{path}: artifact needs a nonempty id/case_id")
            if identifier in seen:
                raise ValueError(f"Duplicate assisted artifact ID: {identifier}")
            seen.add(identifier)
            if item.get("status") == "error":
                raise ValueError(f"{path}: {identifier} is a failed VLM artifact and has no assisted contract")
            if not isinstance(contract.get("task"), dict) or not isinstance(contract.get("steps"), list):
                raise ValueError(f"{path}: {identifier} is not an assisted-extraction contract")
            records.append(contract)
    return records, sources


def _summary(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(predictions)
    verified = [item.get("problem", {}).get("verified_solution_covered", False) for item in predictions]
    context = [item.get("problem", {}).get("context_check", {}).get("status") for item in predictions]
    verdicts = Counter(item["verdict"] for item in predictions)
    return {
        "examples": total,
        "verified_solution_covered": sum(verified),
        "verified_solution_coverage": sum(verified) / total if total else 0,
        "task_aware_covered": sum(status in {"valid", "invalid"} for status in context),
        "task_aware_coverage": sum(status in {"valid", "invalid"} for status in context) / total if total else 0,
        "verdict_counts": dict(sorted(verdicts.items())),
        "indeterminate": verdicts["indeterminate"],
    }


def run_assisted_oracle(
    inputs: list[Path], output: Path, repo_root: Path, *, timeout: float | None = 10.0, split_name: str = "assisted_extraction"
) -> dict[str, Any]:
    if timeout is not None and timeout <= 0:
        raise ValueError("timeout must be positive")
    records, sources = load_assisted_records(inputs)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    predictions_dir = output / "predictions"
    predictions_dir.mkdir(exist_ok=True)
    predictions = [analyze_assisted_contract(record, repo_root, timeout=timeout) for record in records]
    for index, prediction in enumerate(predictions, 1):
        (predictions_dir / f"{index:04}.json").write_text(json.dumps(prediction, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "predictions.json").write_text(json.dumps(predictions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = _summary(predictions)
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation": split_name,
        "pipeline": "llm_assisted_extraction_plus_math_core",
        "input_projection": "task + givens + goal + constraints + structured steps; no labels read",
        "timeout_seconds": timeout,
        "sources": sources,
        "summary": summary,
        "results": [
            {
                "id": item["id"], "verdict": item["verdict"], "first_error_step": item["first_error_step"],
                "verified_solution_covered": item["problem"]["verified_solution_covered"],
                "task_aware_covered": item["problem"]["context_check"]["status"] in {"valid", "invalid"},
                "fallback_reasons": item["problem"]["fallback_reasons"],
            }
            for item in predictions
        ],
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output / "results.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["id", "verdict", "first_error_step", "verified_solution_covered", "task_aware_covered", "fallback_reasons"])
        writer.writeheader()
        for row in report["results"]:
            writer.writerow({**row, "fallback_reasons": "; ".join(row["fallback_reasons"])})
    return report
