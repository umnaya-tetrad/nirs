import json

from evaluator import evaluator


def test_evaluator_uses_task_aware_coverage_without_step_only_rerun(tmp_path, monkeypatch):
    gt = [{"id": "case-1", "verdict": "correct", "first_error_step": None}]
    prediction = {
        "id": "case-1",
        "verdict": "correct",
        "first_error_step": None,
        "steps": [{"step_id": "s1", "latex": "x=1"}],
        "pipeline": {"approach": "llm_assisted_extraction_plus_math_core"},
        "problem": {"verified_solution_covered": True, "task_aware_covered": True},
    }
    gt_path = tmp_path / "gt.json"
    predictions_path = tmp_path / "predictions.json"
    gt_path.write_text(json.dumps(gt), encoding="utf-8")
    predictions_path.write_text(json.dumps([prediction]), encoding="utf-8")
    monkeypatch.setattr(evaluator, "run_isolated", lambda *_: (_ for _ in ()).throw(AssertionError("must not run step-only CAS")))

    report = evaluator.evaluate(gt_path, predictions_path)

    row = report["cases"][0]
    assert row["cas_status"] == "ASSISTED"
    assert row["cas_covered"] is True
    assert row["assisted_task_aware_covered"] is True
    assert report["summary"]["cas"]["coverage"] == 1
    assert report["summary"]["cas"]["task_aware_coverage"] == 1
