"""Freeze selected runner artifacts into Git-safe reproducibility bundles.

The bundles deliberately retain contracts and provenance only.  They do not
contain images, API keys, FERMAT source columns, or reference verdicts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dataset" / "artifacts"
MIXED = ROOT / "outputs" / "20261008T191307Z_gemini_assisted_extraction_assisted_extraction_gemini_v2"
MISSING = ROOT / "outputs" / "20261008T204206Z_gemini_assisted_extraction_assisted_extraction_gemini_v2"
ORDINARY = ROOT / "outputs" / "20261008T162532Z_gemini_extraction_extraction_gemini_v2"


def artifact(path: Path) -> dict:
    raw = path.read_bytes()
    value = json.loads(raw)
    if value.get("status") != "ok":
        raise ValueError(f"Not a successful artifact: {path}")
    prompt = value["prompt"]
    return {"id": value["case_id"], "contract": value["contract"],
            "contract_sha256": hashlib.sha256(json.dumps(value["contract"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "source_run": str(path.parent.relative_to(ROOT)), "source_artifact_sha256": hashlib.sha256(raw).hexdigest(),
            "provider": value["provider"], "model": value.get("provider_model"),
            "prompt_version": value["prompt_version"], "prompt_sha256": prompt["sha256"]}


def write(name: str, rows: list[dict]) -> None:
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate ID in {name}")
    payload = {"artifact_version": "1.0", "ids": ids, "items": rows}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    mixed = [artifact(path) for path in sorted(MIXED.glob("*.json"))]
    missing = [artifact(path) for path in sorted(MISSING.glob("*.json"))]
    # Current mixed run includes the first ten dev FERMAT IDs and ten EGE
    # engineering cases. The manifest is the authority for the dev ordering.
    manifest = json.loads((ROOT / "dataset/manifests/fermat_dev_20.json").read_text())
    dev_ids = [case["id"] for case in manifest["cases"]]
    assisted_by_id = {item["id"]: item for item in mixed + missing}
    write("gemini_assisted_mixed_20.json", mixed)
    write("gemini_assisted_fermat_dev_20.json", [assisted_by_id[item] for item in dev_ids])
    ordinary_items = [artifact(path) for path in ORDINARY.glob("*.json")]
    ordinary_by_id = {item["id"]: item for item in ordinary_items}
    write("gemini_ordinary_fermat_dev_20.json", [ordinary_by_id[item] for item in dev_ids])


if __name__ == "__main__":
    main()
