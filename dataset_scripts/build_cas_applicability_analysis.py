"""Offline applicability analysis of frozen final-80 v2 results.

Reads case-level artifacts only.  It never calls a provider, CAS, or changes a
frozen artifact.  All percentage denominators remain explicit in the CSVs.
"""
from __future__ import annotations

import csv
import html
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/final80_v2/scientific_analysis/cas_applicability"
GT = ROOT / "dataset/final_gt_v2.json"
DOMAINS = ROOT / "dataset/annotations/math_domains_final80_v2.json"
REPORT = ROOT / "reports/final80_v2/four-routes-evaluation/report.json"
E2E = {p: ROOT / f"outputs/final80_v2/{p}-e2e" for p in ("gemini", "gigachat")}
EXTRACT = {p: ROOT / f"outputs/final80_v2-assisted/{p}-assisted-extraction" for p in ("gemini", "gigachat")}
CAS = {p: ROOT / f"reports/final80_v2/assisted/{p}-assisted-cas/predictions.json" for p in ("gemini", "gigachat")}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def artifact_map(directory: Path) -> dict[str, dict[str, Any]]:
    result = {}
    for path in directory.glob("*.json"):
        if path.name == "run_metadata.json":
            continue
        item = load(path); result[item["case_id"]] = item
    return result


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def rate(n: int, d: int) -> float | None:
    return n / d if d else None


def fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:.1%}"


def wilson(n: int, d: int) -> str:
    if not d: return "—"
    z, p = 1.96, n / d; den = 1 + z*z/d
    centre = (p + z*z/(2*d)) / den
    half = z * ((p*(1-p)/d + z*z/(4*d*d)) ** .5) / den
    return f"[{max(0,centre-half):.1%}, {min(1,centre+half):.1%}]"


def label(contract: dict[str, Any] | None) -> str:
    return str((contract or {}).get("verdict", "missing"))


def error_first(contract: dict[str, Any] | None, gt: dict[str, Any]) -> bool | None:
    if gt["verdict"] != "incorrect": return None
    if not contract or label(contract) != "incorrect": return False
    return contract.get("first_error_step") == gt.get("first_error_step")


def primary_failure(reasons: str, h2: dict[str, Any] | None) -> tuple[str, str, str]:
    """Conservative diagnostic label: evidence, not a causal attribution."""
    low = reasons.lower()
    ocr = str((h2 or {}).get("error_class", ""))
    if "timeout" in low or "worker_exit" in low:
        return "timeout", "high", "timeout/worker diagnostic"
    if any(x in low for x in ("requires calculus", "differential notation", "definite integral", "exponent exceeds", "undefined real expression")):
        return "unsupported_math", "medium", "diagnostic reports a mathematical-domain limitation"
    if any(x in low for x in ("unsupported input", "unsupported token", "bare word", "prose/conditions")):
        return "parser_limitation", "medium", "diagnostic reports parser/prose limitation"
    if any(x in low for x in ("task has no explicit", "unanchored", "requires two explicit", "requires one explicit")):
        return "task_formalization", "medium", "TaskSpec anchoring/goal diagnostic"
    if any(x in low for x in ("node/edge proof is unresolved", "continuation requires", "branch")):
        return "dependencies_or_branching", "medium", "dependency graph diagnostic"
    if ocr in {"segmentation", "missed_line", "extra_line", "structure"}:
        return "segmentation_or_structure", "low", "H2 extraction class; causal contribution needs review"
    if ocr and ocr != "exact":
        return "recognition_or_latex", "low", "H2 extraction mismatch; causal contribution needs review"
    return "uncertain", "low", "saved diagnostics do not isolate a primary cause"


def bar(path: Path, title: str, rows: list[tuple[str, float, float]]) -> None:
    width, left, top, rh = 900, 260, 72, 48; height = top + rh * len(rows) + 25; usable = 580
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><title>{html.escape(title)}</title>', f'<text x="{left}" y="30" font-family="sans-serif" font-size="18">{html.escape(title)}</text>', '<rect x="260" y="45" width="14" height="14" fill="#357edd"/><text x="280" y="57" font-family="sans-serif" font-size="12">Gemini</text><rect x="370" y="45" width="14" height="14" fill="#d95f02"/><text x="390" y="57" font-family="sans-serif" font-size="12">GigaChat</text>']
    for i,(name,a,b) in enumerate(rows):
        y=top+i*rh; s.append(f'<text x="{left-8}" y="{y+20}" text-anchor="end" font-family="sans-serif" font-size="12">{html.escape(name)}</text>')
        for j,(value,color) in enumerate(((a,"#357edd"),(b,"#d95f02"))):
            w=usable*max(0,min(1,value)); yy=y+j*22; s.append(f'<rect x="{left}" y="{yy}" width="{w:.1f}" height="17" fill="{color}"/><text x="{left+w+4:.1f}" y="{yy+13}" font-family="sans-serif" font-size="11">{value:.0%}</text>')
    s.append('</svg>'); path.write_text('\n'.join(s)+'\n',encoding='utf-8')


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True); plots=OUT/"plots"; plots.mkdir(exist_ok=True)
    gt={x['id']:x for x in load(GT)}; domains={x['solution_id']:x for x in load(DOMAINS)['records']}
    report=load(REPORT); e2e={p:artifact_map(E2E[p]) for p in E2E}; extraction={p:artifact_map(EXTRACT[p]) for p in EXTRACT}; cas={p:{x['id']:x for x in load(CAS[p])} for p in CAS}
    pairs={p: report['h1']['pairs'][f'{p}:{p}_e2e__{p}_assisted_cas']['paired']['rows'] for p in ('gemini','gigachat')}
    h2={p:{x['id']:x for x in report['h2']['pairs'][f'{p}:{p}_e2e__{p}_assisted_cas']['rows']} for p in ('gemini','gigachat')}
    ids=list(gt)
    # Complete per-case joined records, never filtering indeterminate.
    joined: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for p in ('gemini','gigachat'):
        h1={x['id']:x for x in pairs[p]}
        for ident in ids:
            ea=e2e[p].get(ident); xa=extraction[p].get(ident); ca=cas[p].get(ident)
            vlm=float(xa.get('latency_ms')) if xa and isinstance(xa.get('latency_ms'),(int,float)) else None
            ctime=float(ca.get('meta',{}).get('duration_ms')) if ca and isinstance(ca.get('meta',{}).get('duration_ms'),(int,float)) else None
            cost=(xa or {}).get('usage',{}).get('cost_rub', (xa or {}).get('usage',{}).get('estimated_cost_rub'))
            joined[p][ident]={'e2e':ea,'extract':xa,'cas':ca,'h1':h1[ident], 'vlm_ms':vlm,'cas_ms':ctime,
                'pipeline_ms':(vlm+ctime if vlm is not None and ctime is not None else None),'e2e_ms':float(ea['latency_ms']) if ea and isinstance(ea.get('latency_ms'),(int,float)) else None,
                'e2e_cost':(ea or {}).get('usage',{}).get('cost_rub',(ea or {}).get('usage',{}).get('estimated_cost_rub')),'assist_cost':cost}
    domain_rows=[]
    for d in sorted({x['domain'] for x in domains.values()}):
        dids=[i for i in ids if domains[i]['domain']==d]
        for p in ('gemini','gigachat'):
            j=joined[p]; covered=[i for i in dids if label(j[i]['cas']) in ('correct','incorrect')]
            correct=sum(gt[i]['verdict']=='correct' for i in dids); eok=sum(j[i]['h1']['e2e_correct'] for i in dids); cok=sum(j[i]['h1']['cas_correct'] for i in covered)
            wrong=len(covered)-cok; ind=sum(label(j[i]['cas'])=='indeterminate' for i in dids); missing=len(dids)-len(covered)-ind
            badgt=[i for i in dids if gt[i]['verdict']=='incorrect']; efirst=sum(error_first(j[i]['e2e'].get('contract') if j[i]['e2e'] else None,gt[i]) is True for i in badgt); cfirst=sum(error_first(j[i]['cas'],gt[i]) is True for i in badgt)
            domain_rows.append({'domain':d,'provider':p,'n':len(dids),'gt_correct':correct,'gt_incorrect':len(dids)-correct,'e2e_correct':eok,'e2e_accuracy':rate(eok,len(dids)),'cas_covered':len(covered),'cas_coverage':rate(len(covered),len(dids)),'cas_correct_determinate':cok,'cas_wrong_determinate':wrong,'cas_selective_accuracy':rate(cok,len(covered)),'cas_correct_determinate_over_n':rate(cok,len(dids)),'cas_indeterminate':ind,'cas_missing':missing,'e2e_first_error_correct':efirst,'cas_first_error_correct':cfirst,'first_error_denominator_gt_incorrect':len(badgt),'e2e_latency_mean_ms':mean([j[i]['e2e_ms'] for i in dids if j[i]['e2e_ms'] is not None]),'e2e_latency_median_ms':median([j[i]['e2e_ms'] for i in dids if j[i]['e2e_ms'] is not None]),'assisted_vlm_latency_mean_ms':mean([j[i]['vlm_ms'] for i in dids if j[i]['vlm_ms'] is not None]),'cas_latency_mean_ms':mean([j[i]['cas_ms'] for i in dids if j[i]['cas_ms'] is not None]),'pipeline_latency_mean_ms':mean([j[i]['pipeline_ms'] for i in dids if j[i]['pipeline_ms'] is not None]),'pipeline_latency_median_ms':median([j[i]['pipeline_ms'] for i in dids if j[i]['pipeline_ms'] is not None]),'e2e_cost_mean_rub':mean([float(j[i]['e2e_cost']) for i in dids if isinstance(j[i]['e2e_cost'],(int,float))]),'assisted_api_cost_mean_rub':mean([float(j[i]['assist_cost']) for i in dids if isinstance(j[i]['assist_cost'],(int,float))])})
    write_csv(OUT/'domain_comparison.csv',domain_rows,list(domain_rows[0]))
    # Conditional paired comparison on determinate CAS IDs only.
    covered_rows=[]
    for p in ('gemini','gigachat'):
        for ident in ids:
            j=joined[p][ident]
            if label(j['cas']) not in ('correct','incorrect'): continue
            eok=bool(j['h1']['e2e_correct']); cok=bool(j['h1']['cas_correct']); outcome='both_correct' if eok and cok else 'cas_correct_e2e_wrong' if cok else 'cas_wrong_e2e_correct' if eok else 'both_wrong'
            covered_rows.append({'provider':p,'id':ident,'domain':domains[ident]['domain'],'gt_verdict':gt[ident]['verdict'],'e2e_verdict':label(j['e2e'].get('contract') if j['e2e'] else None),'cas_verdict':label(j['cas']),'e2e_correct':eok,'cas_correct':cok,'outcome':outcome,'e2e_first_error_correct':error_first(j['e2e'].get('contract') if j['e2e'] else None,gt[ident]),'cas_first_error_correct':error_first(j['cas'],gt[ident]),'e2e_latency_ms':j['e2e_ms'],'assisted_vlm_latency_ms':j['vlm_ms'],'cas_latency_ms':j['cas_ms'],'assisted_pipeline_latency_ms':j['pipeline_ms'],'e2e_cost_rub':j['e2e_cost'],'assisted_api_cost_rub':j['assist_cost'],'verdict_agree':label(j['e2e'].get('contract') if j['e2e'] else None)==label(j['cas'])})
    write_csv(OUT/'cas_covered_paired.csv',covered_rows,list(covered_rows[0]))
    # Failure classification only for CAS indeterminate; technical missing remains separate.
    failures=[]
    for p in ('gemini','gigachat'):
        for ident in ids:
            j=joined[p][ident]
            if label(j['cas'])!='indeterminate': continue
            reasons='; '.join(j['cas'].get('problem',{}).get('fallback_reasons',[]))
            primary,conf,evidence=primary_failure(reasons,h2[p].get(ident))
            h2_class=h2[p].get(ident,{}).get('error_class')
            secondary = '' if h2_class in (None, '', 'exact') else f"H2 extraction diagnostic: {h2_class} (not a proven cause)"
            failures.append({'provider':p,'id':ident,'domain':domains[ident]['domain'],'primary_category':primary,'confidence':conf,'evidence':evidence,'secondary_signals':secondary,'h2_error_class':h2_class,'h2_task_spec_class':h2[p].get(ident,{}).get('task_spec_class'),'fallback_reasons':reasons,'needs_manual_review':conf=='low' or h2_class not in (None, '', 'exact')})
    write_csv(OUT/'cas_failures_classified.csv',failures,list(failures[0]))
    # Efficiency rows: all valid pipeline IDs and conditional covered IDs, with paired deltas.
    efficiency=[]
    for p in ('gemini','gigachat'):
        for scope, scopeids in [('all_final80',ids),('cas_determinate_subset',[r['id'] for r in covered_rows if r['provider']==p])]:
            j=joined[p]; paired=[i for i in scopeids if j[i]['e2e_ms'] is not None and j[i]['pipeline_ms'] is not None]
            e_cost=[float(j[i]['e2e_cost']) for i in scopeids if isinstance(j[i]['e2e_cost'],(int,float))]; a_cost=[float(j[i]['assist_cost']) for i in scopeids if isinstance(j[i]['assist_cost'],(int,float))]
            efficiency.append({'provider':p,'scope':scope,'n':len(scopeids),'paired_latency_n':len(paired),'e2e_latency_mean_ms':mean([j[i]['e2e_ms'] for i in scopeids if j[i]['e2e_ms'] is not None]),'e2e_latency_median_ms':median([j[i]['e2e_ms'] for i in scopeids if j[i]['e2e_ms'] is not None]),'assisted_vlm_latency_mean_ms':mean([j[i]['vlm_ms'] for i in scopeids if j[i]['vlm_ms'] is not None]),'cas_latency_mean_ms':mean([j[i]['cas_ms'] for i in scopeids if j[i]['cas_ms'] is not None]),'assisted_pipeline_mean_ms':mean([j[i]['pipeline_ms'] for i in scopeids if j[i]['pipeline_ms'] is not None]),'assisted_pipeline_median_ms':median([j[i]['pipeline_ms'] for i in scopeids if j[i]['pipeline_ms'] is not None]),'paired_pipeline_minus_e2e_mean_ms':mean([j[i]['pipeline_ms']-j[i]['e2e_ms'] for i in paired]),'e2e_cost_mean_rub':mean(e_cost),'assisted_api_cost_mean_rub':mean(a_cost),'cost_kind':'provider_reported' if p=='gemini' else 'tariff_estimate','local_cas_cost_included':False})
    write_csv(OUT/'efficiency_comparison.csv',efficiency,list(efficiency[0]))
    # Figures.
    dnames=sorted({x['domain'] for x in domains.values()}); lookup={(x['domain'],x['provider']):x for x in domain_rows}
    bar(plots/'coverage_by_domain.svg','Assisted CAS determinate coverage (all domain IDs)',[(d,lookup[d,'gemini']['cas_coverage'] or 0,lookup[d,'gigachat']['cas_coverage'] or 0) for d in dnames])
    bar(plots/'e2e_vs_assisted_effectiveness.svg','Correct determinate / all domain IDs: E2E vs Assisted CAS',[(d,lookup[d,'gemini']['e2e_accuracy'] or 0,lookup[d,'gemini']['cas_correct_determinate_over_n'] or 0) for d in dnames])
    # Report and scenarios.
    counts=Counter((x['provider'],x['primary_category']) for x in failures)
    lines=['# Эффективность нейросимвольной архитектуры в области её применимости','', '## Дизайн и ограничения','', 'Анализ полностью офлайн: использованы frozen final-80 v2 raw-artifacts, canonical GT, CAS diagnostics и независимая доменная разметка. Никаких новых API/CAS-вызовов или изменений исходных результатов не было. Gemini monetary figures — provider-reported Polza usage; GigaChat — tariff estimate. Денежная стоимость локального CAS не измерялась и не включена.','', '## Доменные результаты','', '| Область | n | Gemini: coverage / selective accuracy / E2E | GigaChat: coverage / selective accuracy / E2E |','|---|---:|---|---|']
    for d in dnames:
        a,b=lookup[d,'gemini'],lookup[d,'gigachat']; lines.append(f"| {d} | {a['n']} | {a['cas_covered']}/{a['n']} ({fmt(a['cas_coverage'])}) / {fmt(a['cas_selective_accuracy'])} / {a['e2e_correct']}/{a['n']} ({fmt(a['e2e_accuracy'])}) | {b['cas_covered']}/{b['n']} ({fmt(b['cas_coverage'])}) / {fmt(b['cas_selective_accuracy'])} / {b['e2e_correct']}/{b['n']} ({fmt(b['e2e_accuracy'])}) |")
    lines += ['', 'Selective accuracy относится только к determinate CAS-выводам. Во всех выводах coverage считается по всем ID домена; domains n=1 остаются описательными.', '', '## Парное сравнение на CAS-covered подмножестве','']
    for p in ('gemini','gigachat'):
        rows=[x for x in covered_rows if x['provider']==p]; c=Counter(x['outcome'] for x in rows); e=sum(x['e2e_correct'] for x in rows); ca=sum(x['cas_correct'] for x in rows); bad=[x for x in rows if x['gt_verdict']=='incorrect']; ef=sum(x['e2e_first_error_correct'] is True for x in bad); cf=sum(x['cas_first_error_correct'] is True for x in bad)
        lines += [f'### {p}: n={len(rows)} (условная выборка)', '', f'- E2E: {e}/{len(rows)} ({fmt(rate(e,len(rows)))}, Wilson {wilson(e,len(rows))}); CAS: {ca}/{len(rows)} ({fmt(rate(ca,len(rows)))}, Wilson {wilson(ca,len(rows))}).', f"- CAS correct / E2E wrong: {c['cas_correct_e2e_wrong']}; CAS wrong / E2E correct: {c['cas_wrong_e2e_correct']}; оба correct: {c['both_correct']}; оба wrong: {c['both_wrong']}.", f'- First-error exact match среди GT incorrect: E2E {ef}/{len(bad)}, CAS {cf}/{len(bad)}. Это строгая проверка ID шага и чувствительна к различной сегментации.', '']
    lines += ['## Эффективность времени и стоимости','']
    for x in efficiency:
        lines.append(f"- {x['provider']} / {x['scope']} (n={x['n']}): E2E median {x['e2e_latency_median_ms']:.0f} ms; Assisted pipeline median {x['assisted_pipeline_median_ms']:.0f} ms; mean paired difference pipeline−E2E {x['paired_pipeline_minus_e2e_mean_ms']:.0f} ms; E2E API cost {x['e2e_cost_mean_rub']:.3f} ₽/image; Assisted VLM API cost {x['assisted_api_cost_mean_rub']:.3f} ₽/image ({x['cost_kind']}; CAS local cost excluded).")
    lines += ['', 'Ни на all-final80, ни на determinate CAS subset не следует заявлять измеренное универсальное преимущество Assisted по latency: полный pipeline включает вызов VLM и CAS. Заявление о денежной экономии возможно только там, где это подтверждает case-level cost и с оговоркой о невключённом локальном CAS.', '', '## Отказы CAS и перспектива расширения','']
    for p in ('gemini','gigachat'):
        total=sum(v for (provider,_),v in counts.items() if provider==p); parts=', '.join(f'{cat}: {n}/{total} ({n/total:.1%})' for (provider,cat),n in sorted(counts.items()) if provider==p); lines.append(f'- {p}: {parts}.')
    review_count=sum(x['needs_manual_review'] for x in failures)
    lines += ['', f'`cas_failures_classified.csv` помечает {review_count}/{len(failures)} отказов `needs_manual_review`: в них H2 сохранил extraction mismatch, поэтому diagnostics не позволяют приписать отказ только CAS/parser. Классификация диагностическая, а не причинная. Только `unsupported_math` является кандидатом на расширение математических правил. `parser_limitation` требует улучшения формального парсинга; `task_formalization` и `dependencies_or_branching` — лучшего TaskSpec/структуры. Даже устранение отказа не гарантирует корректный будущий verdict.', '', '## Вывод','', 'На данных final-80 v2 есть локальные случаи высокой selective accuracy, но при малом coverage и широких Wilson-интервалах. Это демонстрирует область применимости текущего Assisted→Task-aware CAS, но не измеренное преимущество над Direct E2E на всей выборке. Для проверки конкурентоспособности расширенного подхода нужны заранее заданные доменные strata с достаточным n, независимый CAS holdout, измеренная стоимость локального исполнения и повторный фиксированный прогон без отбора по CAS outcome.']
    (OUT/'cas_applicability_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (OUT/'cas_expansion_scenarios.md').write_text('# Сценарии расширения CAS\n\nЭто не измеренные результаты. По `cas_failures_classified.csv` можно рассматривать только условные верхние границы: если конкретные unsupported/parser diagnostics будут устранены, соответствующие indeterminate могут стать попытками проверки, но не предполагаются автоматически правильными. Cases с `task_formalization`, `dependencies_or_branching`, `recognition_or_latex` и `segmentation_or_structure` не являются простым резервом математических правил. Необходимы отдельные pre-registered эксперименты: ручная проверка первопричин, до/после на неизменном holdout, измерение coverage/accuracy/latency/cost и анализ новых ложных determinate verdicts.\n',encoding='utf-8')
    (OUT/'nirs_subsection.md').write_text('# Анализ области применимости нейросимвольного подхода\n\n'+'\n'.join(lines[3:])+'\n',encoding='utf-8')
    print(f'Wrote applicability analysis: {len(domain_rows)} domain rows, {len(covered_rows)} covered pairs, {len(failures)} indeterminate cases.')

if __name__=='__main__': main()
