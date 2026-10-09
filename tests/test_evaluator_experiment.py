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
    assert analysis["policies"]["disagreement_routing"]["automation_rate"] == 0.5
    assert analysis["policies"]["disagreement_routing"]["accuracy_on_automated"] == 1.0
    assert analysis["rows"][0]["disagreement_routing_source"] == "manual"


def _integration_workspace(tmp_path, cas_ids=("good", "bad")):
    good = _sa("good", "correct", ["x=1"])
    bad = _sa("bad", "incorrect", ["2x=4", "x=3"], first_error="s2")
    gt = _write(tmp_path / "gt.json", [good, bad])
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
    for name in ("report.json", "cases.csv", "h1_paired.csv", "h2_ocr.csv", "h3_routing.csv", "report.md"):
        assert (output / name).exists(), name
    key = next(iter(payload["h1"]["pairs"]))
    assert payload["h1"]["pairs"][key]["e2e"]["accuracy_all"] == 1.0
    assert payload["h1"]["pairs"][key]["cas"]["accuracy_all"] == 0.5
    assert payload["h2"]["overall"]["exact_match_rate"] == 1.0
    assert set(payload["h3"]["policies"]) == {"disagreement_routing", "e2e_only", "cas_only"}
    assert payload["experiment"]["ids_count"] == 2


def test_run_experiment_rejects_id_set_mismatch(tmp_path):
    manifest_path = _integration_workspace(tmp_path, cas_ids=("good",))
    with pytest.raises(EvaluationInputError, match="id sets differ"):
        experiment.run_experiment(manifest_path, tmp_path / "out", repo_root=tmp_path)
