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


def _base_img_id(identifier: str) -> str:
    return identifier.split("_pert_", 1)[0]


def test_final80_v2_is_a_complete_schema_valid_frozen_release():
    dev = _read_json(ROOT / "dataset" / "test_gt.json")
    v2 = _read_json(ROOT / "dataset" / "final_gt_v2.json")
    manifest = _read_json(ROOT / "dataset" / "manifests" / "fermat_final_80_v2.json")["cases"]
    replacements = _read_json(ROOT / "dataset" / "final80_v2_replacements.json")

    assert len(v2) == len(manifest) == 80
    assert [item["id"] for item in v2] == [item["id"] for item in manifest]
    assert sum(item["verdict"] == "correct" for item in v2) == 39
    assert sum(item["verdict"] == "incorrect" for item in v2) == 41
    assert len(replacements["removed_ids"]) == len(replacements["added_ids"]) == 22
    assert set(replacements["added_ids"]) <= {item["id"] for item in v2}
    for item in v2:
        validate_contract(item, "solution_analysis", ROOT)
    assert not {_base_img_id(item["id"]) for item in dev} & {_base_img_id(item["id"]) for item in v2}
