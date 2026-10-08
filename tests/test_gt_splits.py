import json
from pathlib import Path

from nirs_llm.contracts import validate_contract


ROOT = Path(__file__).resolve().parents[1]
def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_gt_splits_are_schema_valid_and_disjoint():
    dev = _read_json(ROOT / "dataset" / "test_gt.json")
    final = _read_json(ROOT / "dataset" / "final_gt.json")

    assert len(dev) == 20
    assert len(final) == 80
    for item in [*dev, *final]:
        validate_contract(item, "solution_analysis", ROOT)

    dev_ids = {item["id"] for item in dev}
    final_ids = {item["id"] for item in final}
    assert len(dev_ids) == len(dev)
    assert len(final_ids) == len(final)
    assert not dev_ids & final_ids


def test_gt_splits_match_the_deduplicated_manifest():
    manifest = _read_json(ROOT / "dataset_scripts" / "selected.json")["new_custom_id"]
    dev = _read_json(ROOT / "dataset" / "test_gt.json")
    final = _read_json(ROOT / "dataset" / "final_gt.json")

    assert len(manifest) == 100
    assert len(manifest) == len(set(manifest))
    labelled = {item["id"] for item in [*dev, *final]}
    assert labelled == set(manifest)


def test_final_gt_verdicts_reference_existing_steps_consistently():
    for item in _read_json(ROOT / "dataset" / "final_gt.json"):
        step_ids = {step["step_id"] for step in item["steps"]}
        if item["is_correct"]:
            assert item["verdict"] == "correct"
            assert item["first_error_step"] is None
        else:
            assert item["verdict"] == "incorrect"
            assert item["first_error_step"] in step_ids
