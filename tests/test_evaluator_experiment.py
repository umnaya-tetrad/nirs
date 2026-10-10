import json
from pathlib import Path

import pytest

from evaluator import experiment
from evaluator.evaluator import EvaluationInputError
from evaluator.h1 import paired_analysis, run_metrics
from evaluator.h3 import analyze_h3
from evaluator.manifest import RunSpec, load_manifest
from evaluator.ocr import analyze_transcription, step_diagnosis
from evaluator.runs import RunData, RunRecord, STATUS_API_FAILED, STATUS_OK
from nirs_llm.contracts import validate_contract


def _write(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _sa(identifier, verdict, latex_steps, first_error=None, approach="llm_end_to_end"):
    correct = verdict == "correct"
    return {
        "schema_version": "1.0", "id": identifier,
        "steps": [{"step_id": f"s{i}", "kind": "step", "latex": latex} for i, latex in enumerate(latex_steps, 1)],
        "verdict": verdict, "is_correct": correct,
        "first_error_step": first_error if verdict == "incorrect" else None,
        "findings": [], "meta": {"run_id": "test", "approach": approach, "stage": "verify"},
    }


def _runner_artifact(identifier, contract=None, status="ok", error_type=None):
    if status == "ok":
        return {"case_id": identifier, "status": "ok", "contract": contract,
                "latency_ms": 1000, "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
    return {"case_id": identifier, "status": "error", "error_type": error_type, "error": "boom"}


def _run_spec(run_id, system, mode, source_kind, source_path, key=None, extraction=None):
    return RunSpec(run_id=run_id, system=system, provider="gemini", mode=mode, model=None,
                   prompt_version=None, prompt_sha256=None, git_commit=None, timestamp=None, simulated=False,
                   source_kind=source_kind, source_path=Path(source_path), source_key=key,
                   extraction_kind="bundle" if extraction else None,
                   extraction_path=Path(extraction) if extraction else None, pricing=None)


def test_simulated_fixture_matches_schema_and_marks_failures():
    artifacts = json.loads(Path("evaluator/fixtures/e2e_simulated_dev_20.json").read_text(encoding="utf-8"))
    assert len(artifacts) == 20
    repo_root = Path(__file__).resolve().parents[1]
    failures = [item for item in artifacts if item["status"] == "error"]
    assert {item["error_type"] for item in failures} == {"PolzaUnavailableError", "ContractError"}
    for item in artifacts:
        if item["status"] == "ok":
            validate_contract(item["contract"], "solution_analysis", repo_root)
    assert sum(item["status"] == "ok" for item in artifacts) == 18


def test_manifest_rejects_prompt_sha_mismatch(tmp_path):
    _write(tmp_path / "gt.json", [_sa("c1", "correct", ["x=1"])])
    _write(tmp_path / "e2e.json", [_runner_artifact("c1", _sa("c1", "correct", ["x=1"]))])
    _write(tmp_path / "cases.json", [_sa("c1", "correct", ["x=1"])])
    base = {
        "manifest_version": "1.0", "experiment_id": "tiny", "evaluation_note": "exploratory",
        "dataset": {"split": "tiny", "gt_paths": ["gt.json"], "ids": ["c1"]},
        "h1_pairs": [{"provider": "gemini", "e2e_run": "e2e", "cas_run": "cas"}],
    }
    bad = {**base, "runs": [
        {"run_id": "e2e", "system": "e2e", "provider": "gemini", "mode": "e2e",
         "prompt_version": "v2", "prompt_sha256": "0" * 64,
         "source": {"kind": "runner_artifacts", "path": "e2e.json"}},
        {"run_id": "cas", "system": "extraction_cas", "provider": "gemini", "mode": "extraction",
         "source": {"kind": "solution_analysis_array", "path": "cases.json"}},
    ]}
    path = _write(tmp_path / "bad.json", bad)
    with pytest.raises(EvaluationInputError, match="prompt_sha256 mismatch"):
        load_manifest(path, tmp_path)


def test_manifest_rejects_pair_with_wrong_system(tmp_path):
    _write(tmp_path / "gt.json", [_sa("c1", "correct", ["x=1"])])
    _write(tmp_path / "cases.json", [_sa("c1", "correct", ["x=1"])])
    payload = {
        "manifest_version": "1.0", "experiment_id": "tiny", "dataset": {"split": "tiny", "gt_paths": ["gt.json"], "ids": ["c1"]},
        "h1_pairs": [{"provider": "gemini", "e2e_run": "cas", "cas_run": "cas"}],
        "runs": [{"run_id": "cas", "system": "extraction_cas", "provider": "gemini", "mode": "extraction",
                  "source": {"kind": "solution_analysis_array", "path": "cases.json"}}],
    }
    path = _write(tmp_path / "bad.json", payload)
    with pytest.raises(EvaluationInputError, match="e2e_run must have system=e2e"):
        load_manifest(path, tmp_path)


def test_manifest_rejects_simulated_final_evaluation(tmp_path):
    _write(tmp_path / "gt.json", [_sa("c1", "correct", ["x=1"])])
    _write(tmp_path / "e2e.json", [_runner_artifact("c1", _sa("c1", "correct", ["x=1"]))])
    payload = {
        "manifest_version": "1.0", "experiment_id": "final", "evaluation_note": "final",
        "dataset": {"split": "final", "gt_paths": ["gt.json"], "ids": ["c1"]},
        "h1_pairs": [{"provider": "gemini", "e2e_run": "e2e", "cas_run": "cas"}],
        "runs": [
            {"run_id": "e2e", "system": "e2e", "provider": "gemini", "mode": "e2e", "simulated": True,
             "source": {"kind": "runner_artifacts", "path": "e2e.json"}},
            {"run_id": "cas", "system": "extraction_cas", "provider": "gemini", "mode": "extraction",
             "source": {"kind": "solution_analysis_array", "path": "gt.json"}},
        ],
    }
    with pytest.raises(EvaluationInputError, match="must not contain simulated"):
        load_manifest(_write(tmp_path / "manifest.json", payload), tmp_path)


def test_manifest_loads_ids_from_fixed_subset_file(tmp_path):
    _write(tmp_path / "gt.json", [_sa("c1", "correct", ["x=1"])])
    _write(tmp_path / "subset.json", {"ids": ["c1"]})
    _write(tmp_path / "source.json", [_runner_artifact("c1", _sa("c1", "correct", ["x=1"]))])
    payload = {
        "manifest_version": "1.0", "experiment_id": "subset", "dataset": {
            "split": "final", "gt_paths": ["gt.json"], "ids_file": "subset.json"},
        "runs": [{"run_id": "e2e", "system": "e2e", "provider": "gemini", "mode": "e2e",
                  "source": {"kind": "runner_artifacts", "path": "source.json"}}],
        "h1_pairs": [],
    }
    manifest = load_manifest(_write(tmp_path / "manifest.json", payload), tmp_path)
    assert manifest.ids == ["c1"]
    assert manifest.ids_path == tmp_path / "subset.json"


def test_run_metrics_keep_api_failures_in_denominator():
    good = _sa("good", "correct", ["x=1"])
    bad = _sa("bad", "incorrect", ["2x=4", "x=3"], first_error="s2")
    spec = _run_spec("e2e", "e2e", "e2e", "solution_analysis_array", "x.json")
    run = RunData(spec=spec, records={
        "good": RunRecord("good", STATUS_OK, good),
        "bad": RunRecord("bad", STATUS_API_FAILED, error_type="PolzaUnavailableError"),
    }, id_set={"good", "bad"})
    gt_by_id = {"good": good, "bad": bad}
    metrics = run_metrics(run, gt_by_id, ["good", "bad"])
    assert metrics["accuracy_all"] == 0.5
    assert metrics["status_counts"]["api_failed"] == 1
    assert metrics["missing_ids"] == ["bad"]
    assert metrics["coverage"] == 0.5
    assert metrics["confusion_matrix"] == {"tp": 0, "fp": 0, "tn": 1, "fn": 0,
                                            "positive_class": "incorrect", "policy": "determinate_verdicts_only",
                                            "denominator": 1}


def test_imbalance_metrics_and_always_incorrect_baseline_are_explicit():
    gt = {
        "a": _sa("a", "incorrect", ["x=1"], first_error="s1"),
        "b": _sa("b", "incorrect", ["x=1"], first_error="s1"),
        "c": _sa("c", "correct", ["x=1"]),
    }
    predicted = {
        "a": RunRecord("a", STATUS_OK, gt["a"]),
        "b": RunRecord("b", STATUS_OK, _sa("b", "correct", ["x=1"])),
        "c": RunRecord("c", STATUS_OK, _sa("c", "incorrect", ["x=1"], first_error="s1")),
    }
    run = RunData(spec=_run_spec("e2e", "e2e", "e2e", "solution_analysis_array", "x.json"), records=predicted, id_set=set(predicted))
    metrics = run_metrics(run, gt, ["a", "b", "c"])
    assert metrics["confusion_matrix"] == {"tp": 1, "fp": 1, "tn": 0, "fn": 1,
                                            "positive_class": "incorrect", "policy": "determinate_verdicts_only",
                                            "denominator": 3}
    assert metrics["incorrect_detection"]["specificity"] == 0.0
    assert metrics["incorrect_detection"]["balanced_accuracy"] == 0.25
    assert metrics["always_incorrect_baseline"]["accuracy_all"] == pytest.approx(2 / 3)


def test_run_metrics_reports_vlm_cas_and_end_to_end_latency_separately():
    good = _sa("good", "correct", ["x=1"])
    spec = _run_spec("cas", "extraction_cas", "extraction", "solution_analysis_array", "x.json")
    run = RunData(spec=spec, records={
        "good": RunRecord("good", STATUS_OK, good, vlm_latency_ms=12_000, cas_latency_ms=250),
    }, id_set={"good"})
    metrics = run_metrics(run, {"good": good}, ["good"])
    assert metrics["mean_vlm_latency_ms"] == 12_000
    assert metrics["mean_cas_latency_ms"] == 250
    assert metrics["mean_pipeline_latency_ms"] == 12_250


def test_first_error_metric_aligns_different_step_ids():
    gt = _sa("case", "incorrect", ["2x=4", "x=3"], first_error="s2")
    prediction = _sa("case", "incorrect", ["2x=4", "x=3"], first_error="model_step_b")
    prediction["steps"][0]["step_id"] = "model_step_a"
    prediction["steps"][1]["step_id"] = "model_step_b"
    run = RunData(spec=_run_spec("e2e", "e2e", "e2e", "solution_analysis_array", "x.json"),
                  records={"case": RunRecord("case", STATUS_OK, prediction)}, id_set={"case"})
    metrics = run_metrics(run, {"case": gt}, ["case"])
    assert metrics["first_error_accuracy_on_incorrect"] == 0.0
    assert metrics["first_error_accuracy_aligned_on_incorrect"] == 1.0


def test_h1_paired_metrics_and_bootstrap():
    good = _sa("good", "correct", ["x=1"])
    bad = _sa("bad", "incorrect", ["2x=4", "x=3"], first_error="s2")
    gt_by_id = {"good": good, "bad": bad}
    e2e = RunData(spec=_run_spec("e2e", "e2e", "e2e", "solution_analysis_array", "x.json"),
                  records={"good": RunRecord("good", STATUS_OK, good), "bad": RunRecord("bad", STATUS_OK, bad)},
                  id_set={"good", "bad"})
    cas = RunData(spec=_run_spec("cas", "extraction_cas", "extraction", "solution_analysis_array", "y.json"),
                  records={"good": RunRecord("good", STATUS_OK, _sa("good", "indeterminate", ["x=1"])),
                           "bad": RunRecord("bad", STATUS_OK, bad)},
                  id_set={"good", "bad"})
    e2e_metrics = run_metrics(e2e, gt_by_id, ["good", "bad"])
    cas_metrics = run_metrics(cas, gt_by_id, ["good", "bad"])
    paired = paired_analysis(e2e, cas, gt_by_id, ["good", "bad"], e2e_metrics, cas_metrics)
    assert e2e_metrics["accuracy_all"] == 1.0
    assert cas_metrics["accuracy_all"] == 0.5
    assert paired["e2e_only_correct"] == 1
    assert paired["accuracy_difference"] == 0.5
    assert paired["bootstrap_accuracy_difference"]["diff"] == 0.5


def test_h2_taxonomy_and_transcription_alignment():
    gt = _sa("c1", "incorrect", ["2x=4", "x=3"], first_error="s2")
    diagnosis = step_diagnosis("x=3", "x=5")
    assert diagnosis["error_class"] == "digit"
    extraction = {"steps": [{"step_id": "s1", "latex": "2x=4"}]}
    transcription = analyze_transcription(gt, extraction)
    assert transcription["error_class"] == "missed_line"
    assert transcription["status_counts"]["missed_line"] == 1


def test_h3_disagreement_routes_to_manual():
    good = _sa("good", "correct", ["x=1"])
    bad = _sa("bad", "incorrect", ["2x=4", "x=3"], first_error="s2")
    gt_by_id = {"good": good, "bad": bad}
    e2e = RunData(spec=_run_spec("e2e", "e2e", "e2e", "solution_analysis_array", "x.json"),
                  records={"good": RunRecord("good", STATUS_OK, good), "bad": RunRecord("bad", STATUS_OK, bad)},
                  id_set={"good", "bad"})
    cas = RunData(spec=_run_spec("cas", "extraction_cas", "extraction", "solution_analysis_array", "y.json"),
                  records={"good": RunRecord("good", STATUS_OK, _sa("good", "indeterminate", ["x=1"])),
                           "bad": RunRecord("bad", STATUS_OK, bad)},
                  id_set={"good", "bad"})
    analysis = analyze_h3(e2e, cas, gt_by_id, ["good", "bad"], {"good": "exact", "bad": "exact"})
    assert analysis["policies"]["disagreement_or_cas_indeterminate"]["automation_rate"] == 0.5
    assert analysis["policies"]["disagreement_or_cas_indeterminate"]["accuracy_on_automated"] == 1.0
    assert analysis["rows"][0]["disagreement_or_cas_indeterminate_source"] == "manual_disagreement_or_cas_indeterminate"
    assert analysis["policies"]["disagreement_only"]["automation_rate"] == 1.0
    assert analysis["rows"][0]["agree"] is None
    assert analysis["comparison"]["comparable_pairs"] == 1
    assert analysis["policies"]["disagreement_or_cas_indeterminate"]["captured_e2e_error_recall"] is None


def test_determinate_classification_and_h3_error_capture_exclude_abstentions():
    gt = {
        "a": _sa("a", "incorrect", ["x=1"], first_error="s1"),
        "b": _sa("b", "correct", ["x=1"]),
        "c": _sa("c", "correct", ["x=1"]),
        "d": _sa("d", "incorrect", ["x=1"], first_error="s1"),
    }
    e2e = RunData(spec=_run_spec("e2e", "e2e", "e2e", "solution_analysis_array", "x.json"), records={
        "a": RunRecord("a", STATUS_OK, _sa("a", "correct", ["x=1"]),),
        "b": RunRecord("b", STATUS_OK, _sa("b", "incorrect", ["x=1"], first_error="s1")),
        "c": RunRecord("c", STATUS_OK, gt["c"]),
        "d": RunRecord("d", STATUS_OK, gt["d"]),
    }, id_set=set(gt))
    cas = RunData(spec=_run_spec("cas", "assisted_cas", "assisted_extraction", "solution_analysis_array", "y.json"), records={
        "a": RunRecord("a", STATUS_OK, _sa("a", "indeterminate", ["x=1"])),
        "b": RunRecord("b", STATUS_OK, _sa("b", "indeterminate", ["x=1"])),
        "c": RunRecord("c", STATUS_OK, gt["c"]),
        "d": RunRecord("d", STATUS_OK, gt["d"]),
    }, id_set=set(gt))
    metrics = run_metrics(cas, gt, ["a", "b", "c", "d"])
    assert metrics["coverage"] == 0.5
    assert metrics["correct_determinate_over_all"] == 0.5
    assert metrics["selective_accuracy_on_covered"] == 1.0
    assert metrics["confusion_matrix"] == {"tp": 1, "fp": 0, "tn": 1, "fn": 0,
                                            "positive_class": "incorrect", "policy": "determinate_verdicts_only",
                                            "denominator": 2}
    analysis = analyze_h3(e2e, cas, gt, ["a", "b", "c", "d"], {})
    selective = analysis["policies"]["disagreement_or_cas_indeterminate"]
    assert selective["automated_ids"] == ["c", "d"]
    assert selective["manual_ids"] == ["a", "b"]
    assert selective["e2e_errors_total"] == 2
    assert selective["e2e_errors_manual"] == 2
    assert selective["e2e_errors_automated"] == 0
    assert selective["captured_e2e_error_recall"] == 1.0


def _integration_workspace(tmp_path, cas_ids=("good", "bad")):
    good = _sa("good", "correct", ["x=1"])
    bad = _sa("bad", "incorrect", ["2x=4", "x=3"], first_error="s2")
    _write(tmp_path / "gt.json", [good, bad])
    _write(tmp_path / "e2e.json", [
        _runner_artifact("good", _sa("good", "correct", ["x=1"])),
        _runner_artifact("bad", _sa("bad", "incorrect", ["2x=4", "x=3"], first_error="s2")),
    ])
    cas_predictions = [record for record in [
        _sa("good", "indeterminate", ["x=1"]),
        _sa("bad", "incorrect", ["2x=4", "x=3"], first_error="s2"),
    ] if record["id"] in cas_ids]
    _write(tmp_path / "cases.json", {"base": {"predictions": cas_predictions}})
    _write(tmp_path / "cas_on_gt.json", [good, bad])
    _write(tmp_path / "extraction.json", {
        "artifact_version": "1.0", "ids": ["good", "bad"],
        "items": [
            {"id": "good", "contract": {"id": "good", "steps": [{"step_id": "s1", "latex": "x=1"}]}},
            {"id": "bad", "contract": {"id": "bad", "steps": [{"step_id": "s1", "latex": "2x=4"}, {"step_id": "s2", "latex": "x=3"}]}},
        ],
    })
    payload = {
        "manifest_version": "1.0", "experiment_id": "tiny", "evaluation_note": "exploratory",
        "dataset": {"split": "tiny", "gt_paths": ["gt.json"], "ids": ["good", "bad"],
                    "cas_on_gt": {"path": "cas_on_gt.json"}},
        "h1_pairs": [{"provider": "gemini", "e2e_run": "e2e", "cas_run": "cas"}],
        "runs": [
            {"run_id": "e2e", "system": "e2e", "provider": "gemini", "mode": "e2e", "simulated": True,
             "source": {"kind": "runner_artifacts", "path": "e2e.json"}},
            {"run_id": "cas", "system": "extraction_cas", "provider": "gemini", "mode": "extraction",
             "source": {"kind": "json_key", "path": "cases.json", "key": "base.predictions"},
             "extraction_artifacts": {"kind": "bundle", "path": "extraction.json"}},
        ],
    }
    manifest_path = _write(tmp_path / "manifest.json", payload)
    return manifest_path


def test_run_experiment_writes_all_outputs(tmp_path):
    manifest_path = _integration_workspace(tmp_path)
    output = tmp_path / "out"
    payload = experiment.run_experiment(manifest_path, output, repo_root=tmp_path)
    for name in ("report.json", "cases.csv", "h1_paired.csv", "h2_ocr.csv", "h3_routing.csv", "report.md",
                 "plots/h1_accuracy.svg", "plots/h3_automation.svg"):
        assert (output / name).exists(), name
    key = next(iter(payload["h1"]["pairs"]))
    assert payload["h1"]["pairs"][key]["e2e"]["accuracy_all"] == 1.0
    assert payload["h1"]["pairs"][key]["cas"]["accuracy_all"] == 0.5
    assert payload["h2"]["overall"]["exact_match_rate"] == 1.0
    assert set(payload["h3"]["policies"]) == {"disagreement_only", "disagreement_or_cas_indeterminate"}
    assert payload["experiment"]["ids_count"] == 2


def test_run_experiment_marks_id_set_mismatch_incomplete(tmp_path):
    manifest_path = _integration_workspace(tmp_path, cas_ids=("good",))
    payload = experiment.run_experiment(manifest_path, tmp_path / "out", repo_root=tmp_path)
    assert payload["experiment"]["complete"] is False
    assert payload["experiment"]["incomplete_runs"] == {"cas": ["bad"]}


@pytest.mark.parametrize("omit", ["baseline", "extraction", "both"])
def test_run_experiment_without_optional_ocr_inputs(tmp_path, omit):
    manifest_path = _integration_workspace(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if omit in ("baseline", "both"):
        del manifest["dataset"]["cas_on_gt"]
    if omit in ("extraction", "both"):
        del manifest["runs"][1]["extraction_artifacts"]
    _write(manifest_path, manifest)

    output = tmp_path / "out"
    payload = experiment.run_experiment(manifest_path, output, repo_root=tmp_path)

    if omit == "baseline":
        assert payload["h2"]["overall"]["cas_on_gt_available"] is False
        assert len(payload["h2"]["per_case"]) == 2
    else:
        assert payload["h2"]["overall"] == {}
        assert payload["h2"]["per_case"] == []
    assert payload["h3"]["policies"]["disagreement_or_cas_indeterminate"]["automation_rate"] == 0.5
    assert len(payload["h1"]["per_case"]) == 2
    markdown = (output / "report.md").read_text(encoding="utf-8")
    if omit == "baseline":
        assert "No GT→step-only CAS was used" in markdown
    else:
        assert "H2 unavailable" in markdown


def test_run_experiment_with_runner_directory(tmp_path):
    manifest_path = _integration_workspace(tmp_path)
    artifacts = json.loads((tmp_path / "e2e.json").read_text(encoding="utf-8"))
    directory = tmp_path / "runner"
    directory.mkdir()
    for artifact in artifacts:
        _write(directory / f"{artifact['case_id']}.json", artifact)
    (directory / "notes.txt").write_text("Not a run artifact", encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runs"][0]["source"]["path"] = "runner"
    _write(manifest_path, manifest)

    first = experiment.run_experiment(manifest_path, tmp_path / "out", repo_root=tmp_path)
    source = first["runs"][0]["provenance"]["source"]
    assert {item["path"] for item in source["files"]} == {"bad.json", "good.json"}
    assert first["runs"][0]["metrics"]["accuracy_all"] == 1.0

    artifacts[0]["latency_ms"] += 1
    _write(directory / "good.json", artifacts[0])
    second = experiment.run_experiment(manifest_path, tmp_path / "out2", repo_root=tmp_path)
    assert source["sha256"] != second["runs"][0]["provenance"]["source"]["sha256"]


def test_h3_uses_ocr_classes_from_each_paired_run(tmp_path):
    manifest_path = _integration_workspace(tmp_path)
    extraction = json.loads((tmp_path / "extraction.json").read_text(encoding="utf-8"))
    extraction["items"][1]["contract"]["steps"][1]["latex"] = "x=5"
    _write(tmp_path / "assisted_extraction.json", extraction)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assisted_run = {**manifest["runs"][1], "run_id": "assisted", "system": "assisted_cas",
                    "mode": "assisted_extraction",
                    "extraction_artifacts": {"kind": "bundle", "path": "assisted_extraction.json"}}
    manifest["runs"].append(assisted_run)
    manifest["h1_pairs"].append({"provider": "gemini", "e2e_run": "e2e", "cas_run": "assisted"})
    _write(manifest_path, manifest)

    payload = experiment.run_experiment(manifest_path, tmp_path / "out", repo_root=tmp_path)
    pairs = payload["h3"]["pairs"]
    ordinary = {row["id"]: row for row in pairs["gemini:e2e__cas"]["rows"]}
    assisted = {row["id"]: row for row in pairs["gemini:e2e__assisted"]["rows"]}
    assert ordinary["bad"]["ocr_error_class"] == "exact"
    assert assisted["bad"]["ocr_error_class"] == "digit"
