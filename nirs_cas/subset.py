"""Create a fixed CAS-supported ID subset from a completed GT→CAS diagnostic run.

Selection deliberately uses only CAS operational statuses on the reference LaTeX:
it never reads the reference verdict, first-error label, or agreement with them.
This makes the subset a documented applicability domain of the existing verifier,
not an accuracy-filtered sample.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CRITERION = {
    "status_in": ["VALID", "INVALID"],
    "covered": True,
    "parse_status": "OK",
    "has_error_type": "bool",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _gt_ids(paths: list[Path]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, list):
            raise ValueError(f"{path}: GT must be a JSON array")
        for index, record in enumerate(payload):
            identifier = record.get("id") if isinstance(record, dict) else None
            if not isinstance(identifier, str) or not identifier:
                raise ValueError(f"{path}: GT item {index} has no nonempty id")
            if identifier in seen:
                raise ValueError(f"duplicate GT id: {identifier}")
            ids.append(identifier)
            seen.add(identifier)
    return ids


def _is_supported(result: dict[str, Any]) -> bool:
    return (
        result.get("status") in CRITERION["status_in"]
        and result.get("covered") is True
        and result.get("parse_status") == CRITERION["parse_status"]
        and type(result.get("has_error")) is bool
    )


def build_supported_subset(report_path: Path, gt_paths: list[Path], output_path: Path) -> dict[str, Any]:
    """Write an ordered, provenance-stamped subset for a declared GT split."""
    report_path = Path(report_path)
    gt_paths = [Path(path) for path in gt_paths]
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    results = report.get("results") if isinstance(report, dict) else None
    if not isinstance(results, list):
        raise ValueError(f"{report_path}: expected an oracle report with a results array")
    by_id: dict[str, dict[str, Any]] = {}
    for index, result in enumerate(results):
        identifier = result.get("id") if isinstance(result, dict) else None
        if not isinstance(identifier, str) or not identifier or identifier in by_id:
            raise ValueError(f"{report_path}: invalid or duplicate results[{index}].id")
        by_id[identifier] = result

    candidate_ids = _gt_ids(gt_paths)
    missing = [identifier for identifier in candidate_ids if identifier not in by_id]
    if missing:
        raise ValueError(f"{report_path}: missing CAS diagnostic result(s): {missing}")
    ids = [identifier for identifier in candidate_ids if _is_supported(by_id[identifier])]
    payload = {
        "subset_version": "1.0",
        "kind": "cas_supported",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "ids": ids,
        "candidate_count": len(candidate_ids),
        "selected_count": len(ids),
        "selection_criterion": CRITERION,
        "selection_rule": (
            "Selected solely from the completed GT→CAS operational statuses; "
            "GT verdict and first-error labels are not read for selection."
        ),
        "limitations": [
            "The CAS implementation was tuned using all 100 GT examples; this is not an independent CAS holdout.",
            "The subset defines the current verifier applicability domain, not a guarantee of CAS correctness.",
        ],
        "source_oracle_report": {"path": report_path.as_posix(), "sha256": _sha256(report_path)},
        "source_gt": [{"path": path.as_posix(), "sha256": _sha256(path)} for path in gt_paths],
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload
