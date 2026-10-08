from copy import deepcopy
import json
from pathlib import Path
import pytest

from nirs_cas.benchmark import validate_dataset, summarize, run_isolated
from nirs_cas.verifier import verify_solution

FIXTURE = Path(__file__).resolve().parents[1] / "data" / "synthetic_20.json"


def load():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_twenty_cases_and_known_limitations():
    data = load()
    rows = []
    for example in validate_dataset(data):
        result = verify_solution([s["latex"] for s in example["steps"]])
        if result["covered"]:
            assert result["has_error"] == example["has_error"], example["id"]
            assert result["first_error_step"] == example["first_error_step"], example["id"]
        rows.append(result)
    summary = summarize(data, rows)
    assert summary["covered_examples"] == 17
    assert summary["decision"] == "PRELIMINARY_ONLY"


@pytest.mark.parametrize("count,decision", [(13, "NO-GO"), (14, "GO")])
def test_go_threshold_and_denominator(count, decision):
    rows = [{"covered": i < count, "parse_status": "OK"} for i in range(20)]
    report = summarize({"kind": "fermat_dev"}, rows)
    assert report["decision"] == decision
    assert report["coverage"] == count / 20
    assert report["has_error_accuracy_on_covered"] is None


@pytest.mark.parametrize("mutation", ["size", "duplicate", "index", "test", "source"])
def test_bad_datasets_rejected(mutation):
    data = deepcopy(load())
    if mutation == "size":
        data["examples"].pop()
    elif mutation == "duplicate":
        data["examples"][1]["id"] = data["examples"][0]["id"]
    elif mutation == "index":
        data["examples"][0]["first_error_step"] = 0
    else:
        data["kind"] = "fermat_dev"
        for i, ex in enumerate(data["examples"]):
            ex.update(source_id=str(i), split="dev")
        if mutation == "test":
            data["examples"][0]["split"] = "test"
        else:
            data["examples"][0].pop("source_id")
    with pytest.raises(ValueError):
        validate_dataset(data)


def test_subprocess_timeout_is_abstention():
    result = run_isolated(["x=1", "x=1"], timeout=0.00001)
    assert result["status"] == "UNSUPPORTED"
    assert result["parse_status"] == "NOT_MEASURED"
    assert result["has_error"] is None
    assert not result["covered"]


def test_subprocess_returns_actual_result():
    result = run_isolated(["x=1", "x=2"])
    assert result["status"] == "INVALID"
    assert result["first_error_step"] == 2
