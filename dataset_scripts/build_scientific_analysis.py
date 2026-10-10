"""Build a traceable narrative analysis from frozen final-80 v2 artifacts.

This script performs no model or CAS calls.  It reads the evaluator report,
canonical GT and saved Assisted-extraction artifacts, then writes a separate
scientific-analysis bundle.  Diagnostic notes distinguish direct evidence from
cases that still need visual/manual review.
"""
from __future__ import annotations

import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/final80_v2/four-routes-evaluation/report.json"
GT_PATH = ROOT / "dataset/final_gt_v2.json"
OUT = ROOT / "reports/final80_v2/scientific_analysis"

PROVIDERS = ("gemini", "gigachat")
PAIR_KEYS = {
    "gemini": "gemini:gemini_e2e__gemini_assisted_cas",
    "gigachat": "gigachat:gigachat_e2e__gigachat_assisted_cas",
}

# These notes are deliberately conservative.  They describe what the saved
# artifacts demonstrate, not a causal claim about the photographed handwriting.
CASE_NOTES = {
    ("gemini", "img_455_pert_5.1"): (
        "Ложный определённый CAS-вердикт. Saved extraction и canonical GT расходятся в промежуточном элементе матрицы; "
        "CAS также фиксирует недостающие matrix bindings. Это показывает mismatch представления/проверки, но для отнесения причины "
        "к OCR, GT или CAS требуется проверка фотографии."),
    ("gemini", "img_108_pert_1.4"): (
        "Ложный определённый CAS-вердикт. Тригонометрическая цепочка имеет тот же финальный результат, что GT, но GT помечает "
        "решение как incorrect. Артефакты не позволяют отделить принятие неверного перехода CAS от проблемы GT/фото; нужна ручная проверка."),
    ("gemini", "img_529_pert_4.5"): (
        "Ложный определённый CAS-вердикт. Задача с упорядоченной парой извлечена в те же два уравнения, что canonical GT, но CAS "
        "даёт correct при GT=incorrect. Это семантическое расхождение TaskSpec/проверки, а не доказанная OCR-причина."),
    ("gemini", "img_77_pert_5.1"): (
        "Ложный определённый CAS-вердикт. Extraction разворачивает запись в строки с прозой и имеет класс missed-line. Diagnostics содержат "
        "ошибки разбора прозы; единственную причину неверного финального вердикта без просмотра изображения назначать нельзя."),
    ("gemini", "img_78_pert_5.1"): (
        "Ложный определённый CAS-вердикт с missed-line extraction и unsupported-text diagnostics. Он совместим с влиянием recognition/" 
        "normalisation на проверку, но данные не доказывают, что это единственная причина вердикта."),
    ("gemini", "img_400_pert_5.1"): (
        "Indeterminate при структурированном TaskSpec: diagnostics явно требуют постоянное положительное основание и оставляют граф зависимостей "
        "неразрешённым. Это подтверждённое ограничение области/предпосылок CAS, а не свидетельство ошибки ученика."),
    ("gemini", "img_374_pert_5.1"): (
        "Indeterminate при почти полной extraction определённого интеграла. Diagnostics явно не поддерживают интегральную нотацию; это ограничение "
        "области CAS, а не наблюдаемая ошибка транскрипции."),
    ("gemini", "img_98_pert_2.1"): (
        "Exact extraction, но indeterminate из-за сохранённых diagnostics TIMEOUT_OR_WORKER_EXIT. Кейс показывает, что точный LaTeX сам по себе "
        "не гарантирует CAS coverage."),
    ("gigachat", "img_190_pert_3.2"): (
        "Сильный пример влияния recognition: GT содержит произведение в расчёте среднего, а extraction использует сумму и получает 5.2. "
        "CAS принимает извлечённую цепочку, хотя GT помечает исходное решение incorrect. Фото может подтвердить исходную нотацию."),
    ("gigachat", "img_387_pert_5.1"): (
        "Indeterminate с TaskSpec класса missing_goal и diagnostics, требующими calculus verifier. Наблюдаются и структурная неполнота, "
        "и неподдерживаемая математическая область; их индивидуальный вклад неразделим."),
    ("gigachat", "img_65_pert_5.1"): (
        "Exact step transcription, но indeterminate. Diagnostics фиксируют unanchored statement/unknown goal: это ограничение привязки TaskSpec "
        "даже без найденного step-level OCR mismatch."),
    ("gigachat", "img_488_pert_5.1"): (
        "Технический contract failure, а не математический abstention: повторный output содержал пустое обязательное поле target_latex. Он остаётся missing "
        "в all-denominator metrics и не считается CAS indeterminate."),
    ("gigachat", "img_592_pert_5.1"): (
        "Ложный определённый CAS-вердикт с segmentation error и unsupported logical/prose diagnostics. Артефакты подтверждают mismatch представления, "
        "но для установления первопричины нужна визуальная проверка."),
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def short(value: Any, limit: int = 420) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return text if len(text) <= limit else text[: limit - 1] + "…"


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def bar_svg(path: Path, title: str, values: list[tuple[str, float]]) -> None:
    width, left, top, row_h = 820, 310, 45, 46
    height = top + len(values) * row_h + 36
    usable = width - left - 70
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f"<title>{html.escape(title)}</title>",
        f'<text x="{left}" y="24" font-family="sans-serif" font-size="18">{html.escape(title)}</text>',
    ]
    for i, (label, value) in enumerate(values):
        y = top + i * row_h
        w = max(0, min(1, value)) * usable
        lines += [
            f'<text x="{left - 8}" y="{y + 16}" text-anchor="end" font-family="sans-serif" font-size="13">{html.escape(label)}</text>',
            f'<rect x="{left}" y="{y}" width="{w:.1f}" height="23" fill="#357edd"/>',
            f'<text x="{left + w + 7:.1f}" y="{y + 16}" font-family="sans-serif" font-size="13">{value:.1%}</text>',
        ]
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def extraction(provider: str, case_id: str) -> dict[str, Any] | None:
    path = ROOT / f"outputs/final80_v2-assisted/{provider}-assisted-extraction/{case_id}.json"
    if not path.exists():
        return None
    payload = load_json(path)
    return payload.get("contract") if payload.get("status") == "ok" else None


def outcome_category(row: dict[str, Any]) -> str:
    label = row["cas_label"]
    if label == "indeterminate":
        return "CAS indeterminate"
    if label == "missing_or_failed":
        return "API/contract missing"
    return "CAS correct determinate" if row["cas_correct"] else "CAS wrong determinate"


def make_bundle() -> None:
    payload = load_json(REPORT)
    gt = {row["id"]: row for row in load_json(GT_PATH)}
    OUT.mkdir(parents=True, exist_ok=True)
    plots = OUT / "plots"
    plots.mkdir(exist_ok=True)

    h1_rows: list[dict[str, Any]] = []
    extraction_rows: list[dict[str, Any]] = []
    reason_case_sets: dict[tuple[str, str], set[str]] = defaultdict(set)
    diagnostics: list[dict[str, Any]] = []
    h3_rows: list[dict[str, Any]] = []

    for provider in PROVIDERS:
        key = PAIR_KEYS[provider]
        pair = payload["h1"]["pairs"][key]
        h2_by_id = {row["id"]: row for row in payload["h2"]["pairs"][key]["rows"]}
        h3_by_id = {row["id"]: row for row in payload["h3"]["pairs"][key]["rows"]}
        for row in pair["paired"]["rows"]:
            category = outcome_category(row)
            h1_rows.append({"provider": provider, "id": row["id"], "cas_outcome": category,
                            "gt_verdict": row["gt_verdict"], "e2e_verdict": row["e2e_label"],
                            "e2e_correct": row["e2e_correct"], "cas_verdict": row["cas_label"],
                            "cas_correct": row["cas_correct"]})
        for row in payload["h2"]["pairs"][key]["rows"]:
            extraction_rows.append({"provider": provider, "id": row["id"], "error_class": row["error_class"],
                                    "transcription_error_class": row["transcription_error_class"],
                                    "exact": row["exact"], "task_spec_class": row["task_spec_class"],
                                    "task_visibility": row["task_visibility"], "cas_indeterminate": row["cas_indeterminate"],
                                    "final_correct": row["final_correct"], "fallback_reasons": " | ".join(row["cas_fallback_reasons"])})
            if row["cas_indeterminate"]:
                for reason in set(row["cas_fallback_reasons"]):
                    if reason:
                        reason_case_sets[(provider, reason)].add(row["id"])
        for policy, stats in payload["h3"]["pairs"][key]["policies"].items():
            h3_rows.append({"provider": provider, "policy": policy, "automated": stats["automated_count"],
                            "manual": stats["manual_count"], "automation_rate": stats["automation_rate"],
                            "accuracy_on_automated": stats["accuracy_on_automated"],
                            "e2e_errors_total": stats["e2e_errors_total"],
                            "e2e_errors_automated": stats["e2e_errors_automated"],
                            "e2e_errors_manual": stats["e2e_errors_manual"],
                            "captured_e2e_error_recall": stats["captured_e2e_error_recall"],
                            "manual_queue_e2e_error_precision": stats["manual_queue_e2e_error_precision"],
                            "automated_ids": " ".join(stats["automated_ids"]), "manual_ids": " ".join(stats["manual_ids"])})

    # Curated diagnostic cases are chosen before interpretation, from observed
    # categories: false determinate, exact-but-indeterminate, TaskSpec issue,
    # and the one technical missing output.
    selected = [(provider, case_id) for provider, case_id in CASE_NOTES]
    for provider, case_id in selected:
        key = PAIR_KEYS[provider]
        pair_row = next(row for row in payload["h1"]["pairs"][key]["paired"]["rows"] if row["id"] == case_id)
        h2 = next(row for row in payload["h2"]["pairs"][key]["rows"] if row["id"] == case_id)
        h3 = next(row for row in payload["h3"]["pairs"][key]["rows"] if row["id"] == case_id)
        contract = extraction(provider, case_id)
        task = contract.get("task") if contract else None
        diagnostics.append({
            "provider": provider, "id": case_id, "category": outcome_category(pair_row),
            "gt_verdict": pair_row["gt_verdict"], "e2e_verdict": pair_row["e2e_label"],
            "cas_verdict": pair_row["cas_label"], "gt_steps": " | ".join(step["latex"] for step in gt[case_id]["steps"]),
            "assisted_steps": " | ".join(step.get("latex", "") for step in (contract or {}).get("steps", [])),
            "task_spec": short(task), "transcription_class": h2["error_class"],
            "task_spec_class": h2["task_spec_class"], "cas_diagnostics": " | ".join(h2["cas_fallback_reasons"]),
            "h3_comparison": h3["comparison_status"], "note": CASE_NOTES[(provider, case_id)],
        })

    reason_rows = [{"provider": provider, "reason": reason, "cases": len(ids), "ids": " ".join(sorted(ids))}
                   for (provider, reason), ids in reason_case_sets.items()]
    reason_rows.sort(key=lambda row: (row["provider"], -row["cases"], row["reason"]))
    write_csv(OUT / "h1_cas_outcomes.csv", h1_rows,
              ["provider", "id", "cas_outcome", "gt_verdict", "e2e_verdict", "e2e_correct", "cas_verdict", "cas_correct"])
    write_csv(OUT / "cas_indeterminate_reasons.csv", reason_rows, ["provider", "reason", "cases", "ids"])
    write_csv(OUT / "assisted_extraction_errors.csv", extraction_rows,
              ["provider", "id", "error_class", "transcription_error_class", "exact", "task_spec_class", "task_visibility", "cas_indeterminate", "final_correct", "fallback_reasons"])
    write_csv(OUT / "h3_policy_details.csv", h3_rows,
              ["provider", "policy", "automated", "manual", "automation_rate", "accuracy_on_automated", "e2e_errors_total", "e2e_errors_automated", "e2e_errors_manual", "captured_e2e_error_recall", "manual_queue_e2e_error_precision", "automated_ids", "manual_ids"])
    write_csv(OUT / "diagnostic_cases.csv", diagnostics, list(diagnostics[0]) if diagnostics else [])

    run_metrics = {row["run_id"]: row["metrics"] for row in payload["runs"]}
    main_rows = [
        {"route": "Gemini E2E", "valid": "80/80", "all_effectiveness": run_metrics["gemini_e2e"]["correct_determinate_over_all"], "coverage": run_metrics["gemini_e2e"]["coverage"], "selective_accuracy": run_metrics["gemini_e2e"]["selective_accuracy_on_covered"]},
        {"route": "Gemini Assisted → Task-aware CAS", "valid": "80/80", "all_effectiveness": run_metrics["gemini_assisted_cas"]["correct_determinate_over_all"], "coverage": run_metrics["gemini_assisted_cas"]["coverage"], "selective_accuracy": run_metrics["gemini_assisted_cas"]["selective_accuracy_on_covered"]},
        {"route": "GigaChat E2E", "valid": "80/80", "all_effectiveness": run_metrics["gigachat_e2e"]["correct_determinate_over_all"], "coverage": run_metrics["gigachat_e2e"]["coverage"], "selective_accuracy": run_metrics["gigachat_e2e"]["selective_accuracy_on_covered"]},
        {"route": "GigaChat Assisted → Task-aware CAS", "valid": "79/80", "all_effectiveness": run_metrics["gigachat_assisted_cas"]["correct_determinate_over_all"], "coverage": run_metrics["gigachat_assisted_cas"]["coverage"], "selective_accuracy": run_metrics["gigachat_assisted_cas"]["selective_accuracy_on_covered"]},
    ]
    write_csv(OUT / "main_comparison.csv", main_rows, list(main_rows[0]))
    bar_svg(plots / "route_effectiveness.svg", "Correct determinate verdicts / all 80 IDs",
            [(row["route"], row["all_effectiveness"]) for row in main_rows])
    bar_svg(plots / "h3_captured_errors.svg", "H3: captured E2E error recall",
            [(f"{row['provider']} {row['policy']}", row["captured_e2e_error_recall"] or 0.0) for row in h3_rows])

    outcome_summary: dict[str, dict[str, Counter[str]]] = {provider: defaultdict(Counter) for provider in PROVIDERS}
    for row in h1_rows:
        outcome_summary[row["provider"]][row["cas_outcome"]]["total"] += 1
        outcome_summary[row["provider"]][row["cas_outcome"]]["e2e_correct"] += int(row["e2e_correct"])

    lines = [
        "# Результаты экспериментального исследования: final-80 v2", "",
        "## Статус и источники", "",
        "Анализ выполнен офлайн по canonical GT, frozen VLM artifacts, CAS diagnostics и итоговому evaluator report. "
        "Новые API-вызовы, изменения CAS, GT, prompts и состава final-80 v2 не выполнялись. Эксперимент остаётся PARTIAL: "
        "`img_488_pert_5.1` не имеет валидного GigaChat Assisted-контракта и учитывается как technical missing, а не как CAS abstention.", "",
        "## Основное сравнение маршрутов", "",
        "| Маршрут | Валидные VLM | Correct determinate / 80 | Coverage | Selective accuracy |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in main_rows:
        lines.append(f"| {row['route']} | {row['valid']} | {row['all_effectiveness']:.1%} | {row['coverage']:.1%} | {row['selective_accuracy']:.1%} |")
    lines += [
        "", "Direct E2E имеет более высокую all-ID эффективность: Gemini 73.8% против 12.5% у Assisted→CAS, "
        "GigaChat 55.0% против 13.8%. Это не следует трактовать как доказательство математической ненадёжности каждого "
        "indeterminate случая: основное ограничение Assisted-маршрута — coverage около 20–21%, а не низкая selective accuracy на покрытых случаях.",
        "", "## H1 — разбор исходов Assisted→CAS", "",
    ]
    for provider in PROVIDERS:
        lines += [f"### {provider}", "", "| Исход CAS | Число | E2E верен |", "|---|---:|---:|"]
        for category in ("CAS correct determinate", "CAS wrong determinate", "CAS indeterminate", "API/contract missing"):
            bucket = outcome_summary[provider][category]
            lines.append(f"| {category} | {bucket['total']} | {bucket['e2e_correct']} |")
        pair = payload["h1"]["pairs"][PAIR_KEYS[provider]]["paired"]
        lines += [
            "", f"Содержательное совпадение двух определённых вердиктов: {pair['verdict_agreement_count']}/{pair['verdict_comparable_count']} "
            f"({pair['verdict_agreement_rate_on_comparable']:.1%}). Показатель correctness-outcome agreement over all IDs "
            f"({pair['correctness_outcome_agreement_over_all']:.1%}) — другая GT-зависимая величина и не используется как agreement для H3.", "",
        ]
    lines += [
        "## H2 — ошибки извлечения и границы CAS", "",
        "Частоты extraction-классов и CAS diagnostics доступны в CSV. Причина конкретного неверного CAS-вердикта не назначается "
        "автоматически: совпадение OCR-класса и отказа CAS — диагностический сигнал, а не доказательство причинности. "
        "Например, точная транскрипция может оставаться indeterminate из-за интегралов, дифференцирования, незафиксированной цели или timeout.", "",
    ]
    for provider in PROVIDERS:
        key = PAIR_KEYS[provider]
        h2_pair = payload["h2"]["pairs"][key]
        lines += [f"### {provider}: распределение ошибок Assisted Extraction", "",
                  "| Класс | Случаев | Доля | Финальный CAS-вердикт неверен/неопределён |",
                  "|---|---:|---:|---:|"]
        for entry in h2_pair["by_error_class"]:
            lines.append(f"| {entry['error_class']} | {entry['cases']} | {entry['share']:.1%} | {entry['final_wrong_rate']:.1%} |")
        lines += ["", "Частоты диагностических причин среди indeterminate (один ID учитывается не более одного раза для одной причины):", "",
                  "| Причина | Случаев |", "|---|---:|"]
        for row in [row for row in reason_rows if row["provider"] == provider][:10]:
            lines.append(f"| {row['reason']} | {row['cases']} |")
        lines.append("")
    lines += ["### Наиболее показательные случаи", ""]
    for case in diagnostics:
        lines += [
            f"#### {case['provider']} — `{case['id']}`", "",
            f"- Категория: {case['category']}; GT `{case['gt_verdict']}`, E2E `{case['e2e_verdict']}`, CAS `{case['cas_verdict']}`.",
            f"- GT: `{case['gt_steps']}`", f"- Assisted steps: `{case['assisted_steps'] or '— (contract missing)'}`",
            f"- TaskSpec: `{case['task_spec']}`", f"- OCR/TaskSpec class: `{case['transcription_class']}` / `{case['task_spec_class']}`.",
            f"- CAS diagnostics: `{case['cas_diagnostics'] or '—'}`", f"- Интерпретация: {case['note']}", "",
        ]
    lines += [
        "## H3 — нейросимвольная маршрутизация", "",
        "| Провайдер | Политика | Автоматически | Вручную | Accuracy авто | Ошибки E2E: авто | Ошибки E2E: вручную | Captured error recall |", "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in h3_rows:
        lines.append(f"| {row['provider']} | {row['policy']} | {row['automated']}/80 ({row['automation_rate']:.1%}) | {row['manual']}/80 | {row['accuracy_on_automated']:.1%} | {row['e2e_errors_automated']} | {row['e2e_errors_manual']} | {row['captured_e2e_error_recall']:.1%} |")
    lines += [
        "", "Для GigaChat missing Assisted output маршрутизируется в ручную очередь политикой `disagreement_or_cas_indeterminate`; "
        "он не становится математическим CAS abstention. Политика `disagreement_only` не отправляет обычные CAS abstentions человеку, "
        "поэтому обладает высокой автоматизацией, но низкой долей захваченных ошибок E2E.",
        "", "## Выводы для НИРС", "",
        "1. На данном final-80 Direct E2E превосходит текущий Assisted→Task-aware CAS по all-ID эффективности у обоих провайдеров; "
        "это статистически подтверждено парным McNemar тестом в frozen evaluator report.",
        "2. Assisted→CAS имеет умеренную/высокую accuracy среди покрытых решений, но покрывает лишь около одной пятой набора; "
        "поэтому selective accuracy нельзя выдавать за accuracy всей системы.",
        "3. Большая доля indeterminate документирует ограничения поддерживаемого CAS-подмножества и TaskSpec anchoring, а не автоматически ошибки ученика или OCR.",
        "4. Есть подтверждённый пример распознавания, способный изменить проверку (`img_190_pert_3.2`); для большинства других несоответствий "
        "доступных данных недостаточно, чтобы отделить OCR, GT и CAS как единственную причину.",
        "5. H3 поддерживает использование CAS-indeterminate как триггера для ручной проверки: строгая политика захватывает 81.0% Gemini и 97.2% GigaChat ошибок E2E, "
        "но снижает автоматизацию до 15.0% и 12.5% соответственно.",
        "6. При 16–17 определённых CAS-вердиктах интервальные и class-conditional оценки нестабильны; результаты о balanced accuracy/F1 CAS следует подавать как описательные, "
        "а не как широкое сравнение математических областей.",
        "7. H1 поддерживает преимущество E2E в текущем контуре; H2 частично поддерживается диагностически; H3 поддерживается как trade-off coverage/risk, "
        "а не как доказательство причинной надёжности disagreement без ручной верификации.",
        "", "## Воспроизводимость", "",
        "Все строки этой записки выводимы из `main_comparison.csv`, `h1_cas_outcomes.csv`, `assisted_extraction_errors.csv`, "
        "`cas_indeterminate_reasons.csv`, `h3_policy_details.csv`, `diagnostic_cases.csv` и frozen report/raw artifacts. "
        "Исходный экспериментальный архив не изменялся.",
    ]
    (OUT / "scientific_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    make_bundle()
