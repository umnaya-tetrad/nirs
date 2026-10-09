import json

from nirs_cas.subset import build_supported_subset


def test_supported_subset_uses_operational_status_not_gt_labels(tmp_path):
    gt = tmp_path / "gt.json"
    gt.write_text(json.dumps([
        {"id": "supported", "verdict": "incorrect", "first_error_step": "s1"},
        {"id": "unsupported", "verdict": "correct", "first_error_step": None},
    ]), encoding="utf-8")
    report = tmp_path / "oracle.json"
    report.write_text(json.dumps({"results": [
        {"id": "supported", "status": "VALID", "covered": True, "parse_status": "OK", "has_error": False},
        {"id": "unsupported", "status": "UNSUPPORTED", "covered": False, "parse_status": "PARTIAL", "has_error": None},
    ]}), encoding="utf-8")
    output = tmp_path / "subset.json"
    subset = build_supported_subset(report, [gt], output)
    assert subset["ids"] == ["supported"]
    assert subset["selected_count"] == 1
    assert json.loads(output.read_text(encoding="utf-8"))["selection_criterion"]["status_in"] == ["VALID", "INVALID"]
