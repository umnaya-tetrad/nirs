"""Render experiment results into JSON, CSV and Markdown."""
from __future__ import annotations

import csv
import html
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
    _write_domains(output_dir / "domain_metrics.csv", payload)
    _write_plots(output_dir / "plots", payload)
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
    columns = ["provider", "id", "gt_verdict", "e2e_label", "cas_label", "e2e_correct", "cas_correct"]
    _csv(path, columns, payload["h1"]["per_case"])


def _write_h2(path: Path, payload: dict[str, Any]) -> None:
    columns = ["provider", "run_id", "id", "gt_verdict", "error_class", "transcription_error_class", "ocr_available", "exact",
               "step_edit_distance", "total_gt_tokens", "missed_steps", "extra_steps",
               "cas_ext_verdict", "cas_gt_verdict", "cas_flip", "final_correct", "final_wrong",
               "task_spec_available", "task_spec_class", "task_visibility", "cas_indeterminate", "cas_fallback_reasons"]
    _csv(path, columns, payload["h2"]["per_case"])


def _write_h3(path: Path, payload: dict[str, Any]) -> None:
    columns = ["provider", "id", "gt_verdict", "ocr_error_class", "e2e_label", "cas_label", "agree", "comparison_status"]
    policies = {name for pair in payload["h3"]["pairs"].values() for name in pair["policies"]}
    for policy in sorted(policies):
        columns += [f"{policy}_source", f"{policy}_label", f"{policy}_correct"]
    _csv(path, columns, payload["h3"]["per_case"])


def _write_domains(path: Path, payload: dict[str, Any]) -> None:
    domains = payload.get("domains", {})
    _csv(path, ["domain", "run_id", "examples", "small_n_warning", "coverage", "accuracy_all", "accuracy_on_covered", "status_counts"],
         domains.get("rows", []) if domains.get("available") else [])


def _bar_svg(path: Path, title: str, values: list[tuple[str, float | None]]) -> None:
    """Write a dependency-free, directly labelled scientific bar chart."""
    width, height, left, top, bottom = 760, 80 + 48 * len(values), 250, 42, 34
    plot_width = width - left - 35
    rows = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">',
        f"<title>{html.escape(title)}</title>",
        f'<text x="{left}" y="24" font-family="sans-serif" font-size="18">{html.escape(title)}</text>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}" stroke="#333"/>',
        f'<line x1="{left}" y1="{height - bottom}" x2="{width - 20}" y2="{height - bottom}" stroke="#333"/>',
    ]
    for tick in range(0, 101, 25):
        x = left + plot_width * tick / 100
        rows.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{height - bottom}" stroke="#ddd"/>')
        rows.append(f'<text x="{x:.1f}" y="{height - 12}" text-anchor="middle" font-family="sans-serif" font-size="12">{tick}%</text>')
    for index, (label, value) in enumerate(values):
        y = top + 12 + index * 48
        rows.append(f'<text x="{left - 10}" y="{y + 13}" text-anchor="end" font-family="sans-serif" font-size="13">{html.escape(label)}</text>')
        if value is None:
            rows.append(f'<text x="{left + 8}" y="{y + 13}" font-family="sans-serif" font-size="13">N/A</text>')
            continue
        clipped = min(1.0, max(0.0, value))
        bar_width = plot_width * clipped
        rows.append(f'<rect x="{left}" y="{y}" width="{bar_width:.1f}" height="24" fill="#357edd"/>')
        rows.append(f'<text x="{left + bar_width + 7:.1f}" y="{y + 17}" font-family="sans-serif" font-size="13">{value:.1%}</text>')
    rows.append("</svg>")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _write_plots(path: Path, payload: dict[str, Any]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    h1_values: list[tuple[str, float | None]] = []
    for key, pair in payload["h1"]["pairs"].items():
        h1_values.append((f"{key} E2E", pair["e2e"]["accuracy_all"]))
        h1_values.append((f"{key} assisted→Task-aware CAS", pair["cas"]["accuracy_all"]))
    _bar_svg(path / "h1_accuracy.svg", "H1 verdict accuracy (all manifest IDs)", h1_values)
    h3_values = [(f"{key} {name}: automation", stats["automation_rate"])
                 for key, pair in payload["h3"]["pairs"].items() for name, stats in pair["policies"].items()]
    _bar_svg(path / "h3_automation.svg", "H3 automation rate", h3_values)


def _markdown(payload: dict[str, Any]) -> str:
    experiment = payload["experiment"]
    lines = [
        "# Experiment evaluation", "",
        f"- experiment_id: `{experiment['experiment_id']}`",
        f"- split: {experiment['split']} ({experiment['ids_count']} IDs)",
        f"- evaluation_note: {experiment['evaluation_note'] or '—'}",
        f"- manifest: `{experiment['manifest_path']}` (sha256 {experiment['manifest_sha256'][:12]})",
        ("- **Not a scientific result bundle:** at least one run is simulated."
         if experiment["has_simulated_runs"] else "- All declared runs are non-simulated."), "",
        ("- **Incomplete input:** missing IDs are retained in all-denominator metrics; this is not a complete final experiment."
         if not experiment.get("complete", True) else "- All required run IDs are present."), "",
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
            "", f"## H1 — paired Direct E2E vs Assisted Extraction → Task-aware CAS ({key})", "",
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
            f"| Mean VLM latency, ms | {_number(pair['e2e']['mean_vlm_latency_ms'])} | {_number(pair['cas']['mean_vlm_latency_ms'])} |",
            f"| Mean CAS latency, ms | {_number(pair['e2e']['mean_cas_latency_ms'])} | {_number(pair['cas']['mean_cas_latency_ms'])} |",
            f"| Mean end-to-end latency, ms | {_number(pair['e2e']['mean_pipeline_latency_ms'])} | {_number(pair['cas']['mean_pipeline_latency_ms'])} |",
            f"| Provider-reported cost, ₽ | {_number(pair['e2e']['cost_rub']['provider_reported'])} | {_number(pair['cas']['cost_rub']['provider_reported'])} |",
            f"| Token-rate estimate, ₽ | {_number(pair['e2e']['cost_rub']['token_rate_estimate'])} | {_number(pair['cas']['cost_rub']['token_rate_estimate'])} |",
            f"| First-error acc, aligned (incorrect GT) | {_percent(pair['e2e']['first_error_accuracy_aligned_on_incorrect'])} | {_percent(pair['cas']['first_error_accuracy_aligned_on_incorrect'])} |",
            f"| Incorrect F1 | {_number(pair['e2e']['incorrect_detection']['f1'])} | {_number(pair['cas']['incorrect_detection']['f1'])} |",
            f"| Specificity (correct) | {_percent(pair['e2e']['incorrect_detection']['specificity'])} | {_percent(pair['cas']['incorrect_detection']['specificity'])} |",
            f"| Balanced accuracy | {_percent(pair['e2e']['incorrect_detection']['balanced_accuracy'])} | {_percent(pair['cas']['incorrect_detection']['balanced_accuracy'])} |",
            f"| Always Incorrect baseline | {_percent(pair['e2e']['always_incorrect_baseline']['accuracy_all'])} | {_percent(pair['cas']['always_incorrect_baseline']['accuracy_all'])} |",
        ]
    lines += ["", "## H2 — OCR quality and propagation", ""]
    if payload["h2"]["pairs"]:
        for key, pair in payload["h2"]["pairs"].items():
            h2 = pair["overall"]
            lines += [f"### {key}", "",
                f"Run `{pair['run_id']}`. Exactly transcribed: {h2['exact_transcriptions']}/{h2['examples']} "
                f"({_percent(h2['exact_match_rate'])}). Mean step edit distance {_number(h2['mean_step_edit_distance'])} "
                f"({_number(h2['normalized_edit_distance'])} normalized).", "",
                f"Assisted determinate-verdict accuracy: {_percent(h2['extraction_cas_verdict_accuracy'])}; "
                f"indeterminate: {h2['assisted_indeterminate']}/{h2['examples']} ({_percent(h2['assisted_indeterminate_rate'])}).", "",
                "| Transcription error class | Cases | Share | Final wrong | Failure share |", "|---|---|---|---|---|",
            ]
            if h2["cas_on_gt_available"]:
                lines += [f"Diagnostic-only GT→step-only CAS comparison: {_percent(h2['cas_on_gt_verdict_accuracy'])} on GT steps; "
                          f"difference {_number(h2['verdict_accuracy_drop'])}. This is not a compared architecture.", ""]
            else:
                lines += ["No GT→step-only CAS was used. TaskSpec fields have no independent GT and are reported only as structural diagnostics.", ""]
            for entry in pair["by_error_class"]:
                lines.append(
                    f"| {entry['error_class']} | {entry['cases']} | {_percent(entry['share'])} | "
                    f"{_percent(entry['final_wrong_rate'])} | {_percent(entry['failure_fraction'])} |")
    else:
        lines.append("H2 unavailable: assisted-extraction artifacts are required.")
    lines += [
        "", "## H3 — selective automation", "",
        "| Policy | Accuracy (all) | Accuracy (automated) | Automation rate | Manual E2E error rate | Captured E2E errors |", "|---|---|---|---|---|---|",
    ]
    for key, pair in payload["h3"]["pairs"].items():
        for name, stats in pair["policies"].items():
            lines.append(
                f"| {key}: {name} | {_percent(stats['accuracy_all'])} | {_percent(stats['accuracy_on_automated'])} | "
                f"{_percent(stats['automation_rate'])} | {_percent(stats['manual_queue_e2e_error_rate'])} | "
                f"{_percent(stats['captured_e2e_error_recall'])} |")
    lines += ["", "## Limitations", ""]
    lines += [f"- {item}" for item in payload["limitations"]]
    return "\n".join(lines) + "\n"
