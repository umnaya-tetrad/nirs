"""Join labels only to completed CAS reports and compare identical inputs."""

from collections import Counter
import hashlib
import json
from pathlib import Path


def _metrics(rows, labels):
    total = len(rows)
    incorrect = [r for r in rows if labels[r["id"]]["verdict"] == "incorrect"]
    known = [r for r in rows if r["has_error"] is True]
    decided = [r for r in rows if r["verdict"] != "indeterminate"]
    return {
        "examples": total,
        "full_coverage": sum(r["covered"] for r in rows) / total,
        "verdict_coverage": len(decided) / total,
        "verdict_accuracy_all": sum(
            r["verdict"] == labels[r["id"]]["verdict"] for r in rows
        )
        / total,
        "verdict_accuracy_decided": sum(
            r["verdict"] == labels[r["id"]]["verdict"] for r in decided
        )
        / len(decided)
        if decided
        else None,
        "first_error_examples": len(incorrect),
        "first_error_accuracy_incorrect": sum(
            r["verdict"] == "incorrect"
            and r["first_error_step_id"] == labels[r["id"]].get("first_error_step")
            for r in incorrect
        )
        / len(incorrect)
        if incorrect
        else None,
        "error_signals_on_gt_correct": sum(
            labels[r["id"]]["verdict"] == "correct" for r in known
        ),
        "incorrect_verdicts_on_gt_correct": sum(
            r["verdict"] == "incorrect" and labels[r["id"]]["verdict"] == "correct"
            for r in rows
        ),
        "indeterminate_count": total - len(decided),
        "timeouts_or_worker_errors": sum(
            r["parse_status"] == "NOT_MEASURED" for r in rows
        ),
    }


def write_improvement_report(
    before_path, after_path, ocr_path, gt_paths, output, repo_root
):
    paths = [Path(before_path), Path(after_path), Path(ocr_path)]
    before, after, ocr = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    if before["sources"] != after["sources"] or [
        r["id"] for r in before["results"]
    ] != [r["id"] for r in after["results"]]:
        raise ValueError("Before/after must use identical ordered IDs and input hashes")
    # Both checkers have finished before any reference annotation is loaded.
    labels = {}
    dev_ids = set()
    for index, path in enumerate(gt_paths):
        items = json.loads(Path(path).read_text(encoding="utf-8"))
        labels.update({r["id"]: r for r in items})
        if index == 0:
            dev_ids = {r["id"] for r in items}
    if {r["id"] for r in after["results"]} != set(labels):
        raise ValueError("GT labels must match before/after IDs exactly")
    if {r["id"] for r in ocr["results"]} != dev_ids:
        raise ValueError("Saved OCR must match the first GT split exactly")
    gt_dev = [r for r in after["results"] if r["id"] in dev_ids]
    metrics = {
        "ordinary_gt100": _metrics(before["results"], labels),
        "exact_gt100": _metrics(after["results"], labels),
        "exact_gt_dev20": _metrics(gt_dev, labels),
        "exact_ocr_dev20": _metrics(ocr["results"], labels),
    }
    old = {r["id"]: r for r in before["results"]}
    new = {r["id"]: r for r in after["results"]}
    changed = []
    fields = ("covered", "verdict", "first_error_step_id", "has_error")
    for identifier, row in new.items():
        if any(old[identifier][k] != row[k] for k in fields):
            changed.append(
                {
                    "id": identifier,
                    "gt_verdict": labels[identifier]["verdict"],
                    "before": {k: old[identifier][k] for k in fields},
                    "after": {k: row[k] for k in fields},
                }
            )
    errors = Counter(
        c.get("rule", c["reason"])
        for r in after["results"]
        for t in r["transitions"]
        for c in t.get("checks", [])
        if c["status"] == "UNSUPPORTED"
    )
    code_paths = [
        Path(repo_root) / "nirs_cas" / name
        for name in (
            "written_exact.py",
            "written_layout.py",
            "exact_math.py",
            "assisted_rules.py",
            "oracle.py",
            "contracts.py",
            "improvement_report.py",
        )
    ]
    report = {
        "evaluation": "Exploratory: all 100 GT examples already used for development; no independent holdout",
        "input_projection": "steps[].latex only; no GT labels, hints, corrections or graph fields",
        "report_sha256": {
            p.name + ":" + str(i): hashlib.sha256(p.read_bytes()).hexdigest()
            for i, p in enumerate(paths)
        },
        "code_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in code_paths
        },
        "metrics": metrics,
        "changed_examples": changed,
        "unsupported_checks_by_rule": dict(errors.most_common()),
        "gt_vs_ocr": [
            {
                "id": r["id"],
                "gt_input_covered": new[r["id"]]["covered"],
                "ocr_input_covered": r["covered"],
                "gt_input_verdict": new[r["id"]]["verdict"],
                "ocr_input_verdict": r["verdict"],
            }
            for r in ocr["results"]
        ],
    }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for name, payload in [
        ("ordinary_gt100.json", before),
        ("exact_gt100.json", after),
        ("exact_ocr_dev20.json", ocr),
        ("comparison.json", report),
    ]:
        (output / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    lines = [
        "# Проверка доработок CAS на GT и сохранённом OCR",
        "",
        "Модели и prompts не менялись; новые VLM-запросы не запускались. Ordinary остаётся режимом по умолчанию.",
        "",
        "| Вход / режим | Полное покрытие | Вынесен вердикт | Вердикт совпал с GT, от всех | Первая ошибка, только GT incorrect | Сигналы ошибки на GT correct |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, m in metrics.items():
        lines.append(
            f"| {name} | {m['full_coverage']:.1%} | {m['verdict_coverage']:.1%} | {m['verdict_accuracy_all']:.1%} | {m['first_error_accuracy_incorrect']:.1%} ({m['first_error_examples']} ошибочных GT) | {m['error_signals_on_gt_correct']} |"
        )
    lines += [
        "",
        "Проверяется согласованность написанной математики относительно начальной предпосылки. Условие задачи в GT не передано: полнота ответа и пропущенные условия не доказаны.",
        "Сигнал ошибки (`has_error=true`) может существовать без установленной первой ошибки. Канонический вердикт тогда остаётся indeterminate; доказанные шаги доступны отдельно в known_error_step_ids.",
        "Совпадение со всеми GT-метками не гарантируется. Например, пропущенная подстановка или выбор положительного корня может требовать отсутствующего условия задачи. Расхождения нужно разбирать по доказательству, а не исправлять по метке.",
        "Все 100 использовались для исследовательской разработки. Для независимой оценки нужна новая выборка. Строгая метрика первой ошибки зависит от разбиения строк и сравнивает исходные step_id.",
        "",
        "Изменения по примерам и причины отказа находятся в comparison.json; полные проверки — в ordinary_gt100.json и exact_gt100.json.",
        "",
        "| Изменившийся пример | GT | Вердикт до → после | Полное покрытие до → после |",
        "|---|---|---|---|",
    ]
    for row in changed:
        a, b = row["before"], row["after"]
        lines.append(
            f"| {row['id']} | {row['gt_verdict']} | {a['verdict']} → {b['verdict']} | {a['covered']} → {b['covered']} |"
        )
    (output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
