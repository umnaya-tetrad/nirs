"""Render experiment results into JSON, CSV and Markdown."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUN_CSV_COLUMNS = ["id", "gt_verdict", "gt_first_error_step"]


def _percent(value: Any) -> str:
    return "—" if value is None else f"{value:.1%}"


def _number(value: Any, digits: int = 3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def write_all(output_dir: Path, payload: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(
        json.dumps({"generated_at_utc": datetime.now(timezone.utc).isoformat(), **payload}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    _write_cases(output_dir / "cases.csv", payload)
    _write_h1(output_dir / "h1_paired.csv", payload)
    _write_h2(output_dir / "h2_ocr.csv", payload)
    _write_h3(output_dir / "h3_routing.csv", payload)
    (output_dir / "report.md").write_text(_markdown(payload), encoding="utf-8")


def _csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_cases(path: Path, payload: dict[str, Any]) -> None:
    run_ids = [run["run_id"] for run in payload["runs"]]
    columns = list(RUN_CSV_COLUMNS)
    for run_id in run_ids:
        columns += [f"{run_id}_status", f"{run_id}_verdict", f"{run_id}_first_error_step", f"{run_id}_correct"]
    _csv(path, columns, payload["cases"])


def _write_h1(path: Path, payload: dict[str, Any]) -> None:
    columns = ["id", "gt_verdict", "e2e_label", "cas_label", "e2e_correct", "cas_correct"]
    _csv(path, columns, payload["h1"]["per_case"])


def _write_h2(path: Path, payload: dict[str, Any]) -> None:
    columns = ["id", "gt_verdict", "error_class", "transcription_error_class", "ocr_available", "exact",
               "step_edit_distance", "total_gt_tokens", "missed_steps", "extra_steps",
               "cas_ext_verdict", "cas_gt_verdict", "cas_flip", "final_correct", "final_wrong"]
    _csv(path, columns, payload["h2"]["per_case"])


def _write_h3(path: Path, payload: dict[str, Any]) -> None:
    columns = ["id", "gt_verdict", "ocr_error_class", "e2e_label", "cas_label", "agree"]
    for policy in payload["h3"]["policies"]:
        columns += [f"{policy}_source", f"{policy}_label", f"{policy}_correct"]
    _csv(path, columns, payload["h3"]["per_case"])


def _markdown(payload: dict[str, Any]) -> str:
    experiment = payload["experiment"]
    lines = [
        "# Experiment evaluation", "",
        f"- experiment_id: `{experiment['experiment_id']}`",
        f"- split: {experiment['split']} ({experiment['ids_count']} IDs)",
        f"- evaluation_note: {experiment['evaluation_note'] or '—'}",
        f"- manifest: `{experiment['manifest_path']}` (sha256 {experiment['manifest_sha256'][:12]})", "",
        "## Runs", "",
        "| Run | System | Provider | Simulated | OK | api_failed | invalid_contract | missing | Verdict acc | Coverage | Indeterminate | Selective risk |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for run in payload["runs"]:
        status = run["metrics"]["status_counts"]
        metrics = run["metrics"]
        lines.append(
            f"| {run['run_id']} | {run['system']} | {run['provider']} | "
            f"{'yes' if run['simulated'] else 'no'} | {status['ok']} | {status['api_failed']} | "
            f"{status['invalid_contract']} | {status['missing']} | {_percent(metrics['accuracy_all'])} | "
            f"{_percent(metrics['coverage'])} | {_percent(metrics['indeterminate_share'])} | "
            f"{_percent(metrics['selective_risk'])} |")
    for key, pair in payload["h1"]["pairs"].items():
        paired = pair["paired"]
        lines += [
            "", f"## H1 — paired E2E vs extraction→CAS ({key})", "",
            f"Provider `{pair['provider']}`. E2E run `{pair['e2e_run']}`, CAS run `{pair['cas_run']}`.", "",
            f"- Verdict accuracy: E2E {_percent(pair['e2e']['accuracy_all'])} vs CAS {_percent(pair['cas']['accuracy_all'])} "
            f"(Δ {paired['accuracy_difference']:+.3f}, paired bootstrap 95% CI "
            f"[{paired['bootstrap_accuracy_difference']['ci_low']:+.3f}, "
            f"{paired['bootstrap_accuracy_difference']['ci_high']:+.3f}])",
            f"- McNemar exact p = {paired['mcnemar_exact_p']:.4f} "
            f"(E2E-only correct {paired['e2e_only_correct']}, CAS-only correct {paired['cas_only_correct']})",
            f"- Agreement {_percent(paired['agreement'])}; both correct {paired['both_correct']}, both wrong {paired['both_wrong']}", "",
            "| Pair metric | E2E | CAS |", "|---|---|---|",
            f"| Verdict accuracy (all) | {_percent(pair['e2e']['accuracy_all'])} | {_percent(pair['cas']['accuracy_all'])} |",
            f"| Accuracy on covered | {_percent(pair['e2e']['accuracy_on_covered'])} | {_percent(pair['cas']['accuracy_on_covered'])} |",
            f"| Coverage | {_percent(pair['e2e']['coverage'])} | {_percent(pair['cas']['coverage'])} |",
            f"| Indeterminate share | {_percent(pair['e2e']['indeterminate_share'])} | {_percent(pair['cas']['indeterminate_share'])} |",
            f"| First-error acc (incorrect GT) | {_percent(pair['e2e']['first_error_accuracy_on_incorrect'])} | {_percent(pair['cas']['first_error_accuracy_on_incorrect'])} |",
            f"| Incorrect F1 | {_number(pair['e2e']['incorrect_detection']['f1'])} | {_number(pair['cas']['incorrect_detection']['f1'])} |",
        ]
    h2 = payload["h2"]["overall"]
    lines += ["", "## H2 — OCR quality and propagation", ""]
    if h2:
        lines += [
            f"Run `{payload['h2']['run_id']}`. Exactly transcribed: {h2['exact_transcriptions']}/{h2['examples']} "
            f"({_percent(h2['exact_match_rate'])}). Mean step edit distance {_number(h2['mean_step_edit_distance'])} "
            f"({_number(h2['normalized_edit_distance'])} normalized).", "",
            f"CAS verdict accuracy: {_percent(h2['extraction_cas_verdict_accuracy'])} on OCR steps vs "
            f"{_percent(h2['cas_on_gt_verdict_accuracy'])} on GT steps (drop {h2['verdict_accuracy_drop']:+.3f}). "
            f"CAS flips due to OCR: {h2['cas_flips']}/{h2['examples']} ({_percent(h2['cas_flip_rate'])}).", "",
            "| Error class | Cases | Share | CAS flips | Final wrong | Failure share |", "|---|---|---|---|---|---|",
        ]
        for entry in payload["h2"]["by_error_class"]:
            lines.append(
                f"| {entry['error_class']} | {entry['cases']} | {_percent(entry['share'])} | "
                f"{entry['cas_flips']} ({_percent(entry['cas_flip_rate'])}) | {_percent(entry['final_wrong_rate'])} | "
                f"{_percent(entry['failure_fraction'])} |")
    else:
        lines.append("H2 unavailable: CAS-on-GT predictions and extraction artifacts are required.")
    policies = payload["h3"]["policies"]
    lines += [
        "", "## H3 — selective automation", "",
        "| Policy | Accuracy (all) | Accuracy (automated) | Automation rate |", "|---|---|---|---|",
    ]
    for name, stats in policies.items():
        lines.append(
            f"| {name} | {_percent(stats['accuracy_all'])} | {_percent(stats['accuracy_on_automated'])} | "
            f"{_percent(stats['automation_rate'])} |")
    lines += ["", "## Limitations", ""]
    lines += [f"- {item}" for item in payload["limitations"]]
    return "\n".join(lines) + "\n"
