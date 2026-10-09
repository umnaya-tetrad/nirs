"""Regenerate the deterministic simulated E2E fixture used by the dev-20 demo.

The fixture emulates a frozen ``llm_end_to_end`` runner artifact set: two API/contract
failures and a few verdict/first-error perturbations around the ground truth. It exists
only because no real E2E run was persisted; it is always marked ``simulated`` in the
manifest and never mixed into final numbers.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from nirs_llm.contracts import validate_contract

MODEL = "google/gemini-3.7-flash"
RUN_ID = "simulated-e2e-dev20"
ERRORS = {
    "img_554_pert_5.1": ("PolzaUnavailableError", "simulated provider outage"),
    "img_471_pert_5.1": ("ContractError", "simulated malformed model response"),
}
OVERRIDES = {
    "img_509_pert_5.1": ("incorrect", "s2"),
    "img_157_pert_3.2": ("correct", None),
    "img_398_pert_4.4": ("incorrect", "s2"),
}


def _pseudo(identifier: str, low: int, high: int) -> int:
    digest = hashlib.sha256(f"{RUN_ID}:{identifier}".encode()).hexdigest()
    return low + int(digest[:8], 16) % (high - low + 1)


def _contract(record: dict, verdict: str, first_error: str | None) -> dict:
    identifier = record["id"]
    contract = {
        "schema_version": "1.0",
        "id": identifier,
        "steps": copy.deepcopy(record["steps"]),
        "verdict": verdict,
        "is_correct": verdict == "correct",
        "first_error_step": first_error if verdict == "incorrect" else None,
        "findings": [],
        "meta": {
            "run_id": RUN_ID, "approach": "llm_end_to_end", "stage": "verify", "model": MODEL,
            "prompt_version": "e2e_gemini_v2", "temperature": 0,
            "duration_ms": _pseudo(identifier, 4000, 18000),
            "tokens_in": _pseudo(identifier, 1200, 1800),
            "tokens_out": _pseudo(identifier, 700, 1400),
        },
    }
    validate_contract(contract, "solution_analysis", Path(__file__).resolve().parents[2])
    return contract


def build(gt_path: Path) -> list[dict]:
    records = json.loads(gt_path.read_bytes().decode("utf-8-sig"))
    artifacts = []
    for record in records:
        identifier = record["id"]
        if identifier in ERRORS:
            error_type, message = ERRORS[identifier]
            artifacts.append({"case_id": identifier, "status": "error", "error_type": error_type, "error": message})
            continue
        verdict, first_error = OVERRIDES.get(identifier, (record["verdict"], record.get("first_error_step")))
        contract = _contract(record, verdict, first_error)
        artifacts.append({
            "case_id": identifier, "status": "ok", "contract": contract,
            "latency_ms": contract["meta"]["duration_ms"],
            "usage": {"prompt_tokens": contract["meta"]["tokens_in"], "completion_tokens": contract["meta"]["tokens_out"]},
        })
    return artifacts


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    artifacts = build(repo_root / "dataset" / "test_gt.json")
    output = Path(__file__).with_name("e2e_simulated_dev_20.json")
    output.write_text(json.dumps(artifacts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output} ({len(artifacts)} artifacts)")


if __name__ == "__main__":
    main()
