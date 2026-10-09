"""Independent, manually curated math-domain sidecar utilities.

This module deliberately does not import or alter model/CAS contracts.  It is
only joined to experiment rows by immutable solution ID after inference.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

DOMAINS = (
    "arithmetic", "algebraic_expression", "equation", "inequality", "function",
    "trigonometry", "geometry", "calculus", "probability_statistics", "number_theory",
    "linear_algebra", "other", "uncertain",
)
FEATURES = (
    "fractions", "powers", "radicals", "polynomials", "systems", "absolute_value",
    "logarithms", "exponentials", "trigonometric_functions", "derivatives", "integrals",
    "matrices", "word_problem", "other",
)


def _ids(manifest: Path) -> list[dict[str, Any]]:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    cases = payload.get("cases", payload) if isinstance(payload, dict) else payload
    if not isinstance(cases, list):
        raise ValueError("dataset manifest must contain cases")
    result = []
    for item in cases:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not isinstance(item.get("image"), str):
            raise ValueError("each dataset case must provide id and image")
        result.append({"solution_id": item["id"], "image_path": item["image"]})
    if len({entry["solution_id"] for entry in result}) != len(result):
        raise ValueError("dataset manifest has duplicate IDs")
    return result


def validate(path: Path, manifest: Path, *, require_complete: bool = False) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        raise ValueError("sidecar needs an object with a records array")
    expected = {entry["solution_id"] for entry in _ids(manifest)}
    seen: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"records[{index}] must be an object")
        identifier, domain, features = record.get("solution_id"), record.get("domain"), record.get("features")
        if not isinstance(identifier, str) or identifier not in expected:
            raise ValueError(f"records[{index}].solution_id is not in the final manifest")
        if identifier in seen:
            raise ValueError(f"duplicate annotation for {identifier}")
        if domain not in DOMAINS:
            raise ValueError(f"records[{index}].domain must be one of the documented categories")
        if not isinstance(features, list) or any(feature not in FEATURES for feature in features):
            raise ValueError(f"records[{index}].features contains an unknown feature")
        seen.add(identifier)
    missing = sorted(expected - seen)
    if require_complete and missing:
        raise ValueError(f"sidecar is incomplete: {len(missing)} IDs missing")
    return {"annotated": len(seen), "expected": len(expected), "missing_ids": missing,
            "complete": not missing, "domains": sorted({record["domain"] for record in records})}


def write_csv_template(manifest: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("solution_id", "image_path", "domain", "features", "notes"))
        writer.writeheader()
        writer.writerows({**row, "domain": "", "features": "", "notes": ""} for row in _ids(manifest))


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or validate independent math-domain annotations.")
    commands = parser.add_subparsers(dest="command", required=True)
    template = commands.add_parser("template")
    template.add_argument("--manifest", type=Path, required=True)
    template.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("validate")
    check.add_argument("--manifest", type=Path, required=True)
    check.add_argument("--sidecar", type=Path, required=True)
    check.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    if args.command == "template":
        write_csv_template(args.manifest, args.output)
        print(f"Wrote {args.output}")
    else:
        print(json.dumps(validate(args.sidecar, args.manifest, require_complete=args.require_complete), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
