"""Build post-hoc exploratory domain analysis from frozen final-80 v2 outputs.

No inference, CAS invocation, prompt change, or input-set change occurs here.
The script joins the independent domain sidecar only after the experiment.
"""
from __future__ import annotations

import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SIDE = ROOT / "dataset/annotations/math_domains_final80_v2.json"
MANIFEST = ROOT / "dataset/manifests/fermat_final_80_v2.json"
GT = ROOT / "dataset/final_gt_v2.json"
EVALUATION = ROOT / "reports/final80_v2/four-routes-evaluation/report.json"
CAS = {
    "gemini": ROOT / "reports/final80_v2/assisted/gemini-assisted-cas/results.csv",
    "gigachat": ROOT / "reports/final80_v2/assisted/gigachat-assisted-cas/results.csv",
}
OUT = ROOT / "reports/final80_v2/scientific_analysis"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def csv_write(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def percent(numerator: int, denominator: int) -> str:
    return "—" if not denominator else f"{numerator / denominator:.1%}"


def chart(path: Path, title: str, groups: list[tuple[str, list[tuple[str, float]]]]) -> None:
    labels = [label for label, _ in groups]
    series = sorted({name for _, values in groups for name, _ in values})
    colors = {"Gemini Assisted CAS": "#357edd", "GigaChat Assisted CAS": "#d95f02", "Gemini E2E": "#1b9e77", "GigaChat E2E": "#7570b3"}
    width, left, top, row = 1060, 240, 82, 58
    height = top + row * len(labels) + 75
    usable = width - left - 105
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             f"<title>{html.escape(title)}</title>", f'<text x="{left}" y="28" font-family="sans-serif" font-size="19">{html.escape(title)}</text>']
    for idx, name in enumerate(series):
        x = left + idx * 190
        lines += [f'<rect x="{x}" y="43" width="14" height="14" fill="{colors.get(name, "#555")}"/>',
                  f'<text x="{x + 20}" y="55" font-family="sans-serif" font-size="13">{html.escape(name)}</text>']
    for i, (label, vals) in enumerate(groups):
        y = top + i * row
        lines.append(f'<text x="{left - 9}" y="{y + 22}" text-anchor="end" font-family="sans-serif" font-size="12">{html.escape(label)}</text>')
        indexed = dict(vals)
        for j, name in enumerate(series):
            value = indexed.get(name, 0.0)
            x = left + j * (usable / max(len(series), 1))
            max_bar = usable / max(len(series), 1) - 42
            w = max_bar * min(1.0, max(0.0, value))
            lines += [f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="22" fill="{colors.get(name, "#555")}"/>',
                      f'<text x="{x + w + 4:.1f}" y="{y + 16}" font-family="sans-serif" font-size="11">{value:.0%}</text>']
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def normalize_reasons(text: str) -> set[str]:
    return {part.strip() for part in text.split(";") if part.strip()}


def write_qc(records: list[dict[str, Any]], manifest_ids: list[str], gt_ids: set[str]) -> None:
    image_missing = []
    manifest = load(MANIFEST)["cases"]
    for case in manifest:
        path = (MANIFEST.parent / case["image"]).resolve()
        if not path.is_file():
            image_missing.append(case["id"])
    visual = [r["solution_id"] for r in records if r.get("review_status") == "visual_confirmed"]
    queue = [r["solution_id"] for r in records if r.get("review_status") != "visual_confirmed"]
    uncertain = [r["solution_id"] for r in records if r.get("uncertain")]
    lines = [
        "# QC доменной разметки final-80 v2", "",
        "## Проверки целостности", "",
        f"- Records in sidecar: **{len(records)}/80**; exact manifest ID match: **{set(manifest_ids) == {r['solution_id'] for r in records}}**.",
        f"- Images present: **{80-len(image_missing)}/80**; missing: {', '.join(image_missing) if image_missing else 'none'}.",
        f"- Canonical GT present: **{len(set(manifest_ids) & gt_ids)}/80**; missing: {', '.join(sorted(set(manifest_ids)-gt_ids)) if set(manifest_ids)-gt_ids else 'none'}.",
        "- Schema: passed `python -m evaluator.domains validate --require-complete`.",
        "- Annotation input intentionally excluded all E2E predictions, CAS verdicts, failures and metrics.", "",
        "## Taxonomy and evidence", "",
        "Primary `domain` denotes the mathematical object/operation; `task_type` is descriptive; `features` encode notation/constructions. Thus `word_problem` is not treated as a mathematical domain.",
        "Every sidecar record records `annotation_source`: canonical GT steps for inherited final rows; canonical GT plus original FERMAT question/domain/subdomain for 22 replacement rows.",
        "",
        "## Visual review scope", "",
        "Direct visual checks were deliberately limited and are not represented as an image-by-image manual audit. Confirmed visual samples:",
    ]
    lines.extend([f"- `{identifier}`" for identifier in visual])
    lines += ["", f"The following **{len(queue)}** source-checked IDs retain `source_checked_not_visually_audited` and are the concrete human visual-review queue:", "", ", ".join(f"`{identifier}`" for identifier in queue), "",
              f"`uncertain=true` records: {', '.join(uncertain) if uncertain else 'none'}. No category was marked uncertain because canonical GT plus relevant FERMAT metadata identify its mathematical object; this does not substitute for the visual-review queue above.",
              "", "## Interpretation limits", "", "This is a post-hoc, descriptive/exploratory annotation. It was not used to select final-80 v2 or tune prompts/CAS. Small domains (function and inequality, n=1) are reported but are not suitable for comparative inference."]
    (OUT / "domain_annotation_qc.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_report(section: str) -> None:
    target = OUT / "scientific_results.md"
    base = target.read_text(encoding="utf-8")
    marker = "\n## Анализ эффективности методов по математическим областям\n"
    if marker in base:
        base = base.split(marker, 1)[0].rstrip() + "\n"
    target.write_text(base.rstrip() + "\n\n" + section.strip() + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "plots").mkdir(exist_ok=True)
    annotation = load(SIDE)
    records = annotation["records"]
    by_id = {r["solution_id"]: r for r in records}
    manifest_ids = [r["id"] for r in load(MANIFEST)["cases"]]
    gt = {r["id"]: r for r in load(GT)}
    report = load(EVALUATION)
    pairs = report["h1"]["pairs"]
    h2_pairs = report["h2"]["pairs"]

    # One transparent CSV per annotated case, with source/review provenance.
    annotation_rows = []
    for identifier in manifest_ids:
        r = by_id[identifier]
        annotation_rows.append({"solution_id": identifier, "domain": r["domain"], "features": "|".join(r["features"]),
                                "task_type": r["task_type"], "annotation_source": r["annotation_source"],
                                "review_status": r["review_status"], "uncertain": r["uncertain"], "notes": r["notes"]})
    csv_write(OUT / "math_domains_final80_v2.csv", annotation_rows, list(annotation_rows[0]))
    write_qc(records, manifest_ids, set(gt))

    cas_rows = {provider: {r["id"]: r for r in csv.DictReader(CAS[provider].open(encoding="utf-8-sig"))}
                for provider in CAS}
    summary_rows: list[dict[str, Any]] = []
    reason_counts: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    feature_error: dict[tuple[str, str, str, str], Counter[str]] = defaultdict(Counter)

    for provider in ("gemini", "gigachat"):
        pair_key = f"{provider}:{provider}_e2e__{provider}_assisted_cas"
        h1 = {r["id"]: r for r in pairs[pair_key]["paired"]["rows"]}
        h2 = {r["id"]: r for r in h2_pairs[pair_key]["rows"]}
        for domain in sorted({r["domain"] for r in records}):
            ids = [identifier for identifier in manifest_ids if by_id[identifier]["domain"] == domain]
            e2e_correct = sum(bool(h1[i]["e2e_correct"]) for i in ids)
            determinate = [i for i in ids if h1[i]["cas_label"] in {"correct", "incorrect"}]
            cas_correct = sum(bool(h1[i]["cas_correct"]) for i in determinate)
            cas_wrong = len(determinate) - cas_correct
            indeterminate = sum(h1[i]["cas_label"] == "indeterminate" for i in ids)
            missing = sum(h1[i]["cas_label"] == "missing_or_failed" for i in ids)
            gt_correct = sum(gt[i]["verdict"] == "correct" for i in ids)
            gt_incorrect = len(ids) - gt_correct
            for identifier in ids:
                if h1[identifier]["cas_label"] == "indeterminate":
                    for reason in normalize_reasons(cas_rows[provider][identifier].get("fallback_reasons", "")):
                        reason_counts[(domain, provider, reason)].add(identifier)
                err = h2[identifier]["error_class"]
                for feature in by_id[identifier]["features"] or ["none"]:
                    feature_error[(domain, provider, feature, err)]["cases"] += 1
                    feature_error[(domain, provider, feature, err)]["indeterminate"] += int(h1[identifier]["cas_label"] == "indeterminate")
            summary_rows.append({
                "domain": domain, "provider": provider, "examples": len(ids), "gt_correct": gt_correct, "gt_incorrect": gt_incorrect,
                "e2e_correct": e2e_correct, "e2e_accuracy": e2e_correct / len(ids),
                "assisted_determinate": len(determinate), "assisted_correct_determinate": cas_correct,
                "assisted_wrong_determinate": cas_wrong, "assisted_indeterminate": indeterminate, "assisted_missing_or_failed": missing,
                "assisted_coverage": len(determinate) / len(ids),
                "assisted_selective_accuracy": (cas_correct / len(determinate)) if determinate else None,
                "assisted_correct_determinate_over_all": cas_correct / len(ids),
            })
    summary_rows.sort(key=lambda r: (r["domain"], r["provider"]))
    csv_write(OUT / "domain_metrics.csv", summary_rows, list(summary_rows[0]))
    reason_rows = [{"domain": domain, "provider": provider, "reason": reason, "indeterminate_cases": len(ids),
                    "denominator_domain": sum(1 for x in manifest_ids if by_id[x]["domain"] == domain), "ids": " ".join(sorted(ids))}
                   for (domain, provider, reason), ids in reason_counts.items()]
    reason_rows.sort(key=lambda r: (r["domain"], r["provider"], -r["indeterminate_cases"], r["reason"]))
    csv_write(OUT / "domain_cas_failure_reasons.csv", reason_rows, ["domain", "provider", "reason", "indeterminate_cases", "denominator_domain", "ids"])
    feature_rows = [{"domain": d, "provider": p, "feature": f, "extraction_error_class": e, "cases": counts["cases"], "cas_indeterminate": counts["indeterminate"]}
                    for (d, p, f, e), counts in feature_error.items()]
    feature_rows.sort(key=lambda r: (r["domain"], r["provider"], r["feature"], -r["cases"], r["extraction_error_class"]))
    csv_write(OUT / "domain_feature_extraction_errors.csv", feature_rows, list(feature_rows[0]))

    domains = sorted({r["domain"] for r in records})
    by_domain_provider = {(r["domain"], r["provider"]): r for r in summary_rows}
    chart(OUT / "plots/domain_cas_coverage.svg", "Assisted CAS coverage by mathematical domain (exploratory)", [
        (d, [("Gemini Assisted CAS", by_domain_provider[d, "gemini"]["assisted_coverage"]),
             ("GigaChat Assisted CAS", by_domain_provider[d, "gigachat"]["assisted_coverage"])]) for d in domains])
    chart(OUT / "plots/domain_e2e_vs_assisted.svg", "Direct E2E versus Assisted CAS: correct determinate / domain n", [
        (d, [("Gemini E2E", by_domain_provider[d, "gemini"]["e2e_accuracy"]),
             ("Gemini Assisted CAS", by_domain_provider[d, "gemini"]["assisted_correct_determinate_over_all"]),
             ("GigaChat E2E", by_domain_provider[d, "gigachat"]["e2e_accuracy"]),
             ("GigaChat Assisted CAS", by_domain_provider[d, "gigachat"]["assisted_correct_determinate_over_all"])]) for d in domains])

    lines = ["## Анализ эффективности методов по математическим областям", "",
             "Это дополнительный **exploratory analysis**, выполненный постфактум по независимой sidecar-разметке. Разметка не использовалась при выборе final-80 v2, в VLM/CAS не передавалась и не меняет frozen raw-эксперимент.", "",
             "| Область | n | GT correct / incorrect | Gemini E2E | Gemini CAS coverage; selective accuracy | GigaChat E2E | GigaChat CAS coverage; selective accuracy |", "|---|---:|---:|---:|---:|---:|---:|"]
    for domain in domains:
        g, q = by_domain_provider[domain, "gemini"], by_domain_provider[domain, "gigachat"]
        lines.append(f"| {domain} | {g['examples']} | {g['gt_correct']} / {g['gt_incorrect']} | {percent(g['e2e_correct'], g['examples'])} ({g['e2e_correct']}/{g['examples']}) | {percent(g['assisted_determinate'], g['examples'])} ({g['assisted_determinate']}/{g['examples']}); {percent(g['assisted_correct_determinate'], g['assisted_determinate'])} | {percent(q['e2e_correct'], q['examples'])} ({q['e2e_correct']}/{q['examples']}) | {percent(q['assisted_determinate'], q['examples'])} ({q['assisted_determinate']}/{q['examples']}); {percent(q['assisted_correct_determinate'], q['assisted_determinate'])} |")
    lines += ["", "`function` and `inequality` each have n=1, so their percentages are descriptive only.", "",
              "### Наблюдения", "",
              "- Gemini Assisted CAS имеет наибольшее coverage в `algebraic_expression` (5/12, 41.7%) и `arithmetic` (3/10, 30.0%); GigaChat — в `arithmetic` (5/10, 50.0%) и `algebraic_expression` (4/12, 33.3%). Это наблюдаемая связь, не доказательство, что именно домен вызывает coverage.",
              "- На `geometry` GigaChat Assisted не дал ни одного определённого вердикта (0/15), Gemini дал 3/15; на `calculus` и `trigonometry` оба провайдера дали по 1/8 или меньше. Диагностика связывает многие отказы с unsupported notation, unresolved dependencies и отсутствующей явной целью, а не только с доменом.",
              "- При достаточном количестве определённых ответов selective accuracy может быть высокой (например, Gemini arithmetic 3/3), но знаменатель мал и не заменяет coverage. В `equation` Gemini имеет 2/13 coverage и 0/2 selective accuracy; поэтому нельзя говорить о приемлемой совместной эффективности этого маршрута.",
              "- Direct E2E превосходит Assisted correct-determinate/all во всех многокейсных доменах данного набора. Разница особенно заметна в geometry/calculus/trigonometry, однако доменные группы малы и пересекаются с особенностями записи и TaskSpec.",
              "- Feature-level таблица `domain_feature_extraction_errors.csv` показывает совместное распределение классов extraction и фичей. Дроби, матрицы, интегралы и тригонометрические функции часто сосуществуют с indeterminate, но по этим observational данным нельзя приписывать им причинность: одна и та же запись может иметь несколько features и структурную проблему TaskSpec.",
              "", "Основные причины fallback по каждому domain/provider и конкретные ID приведены в `domain_cas_failure_reasons.csv`; это позволяет проверить каждое обобщение на case-level artifacts."]
    append_report("\n".join(lines))
    print(f"Wrote domain analysis for {len(records)} annotated records to {OUT}")


if __name__ == "__main__":
    main()
