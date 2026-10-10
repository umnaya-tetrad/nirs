# Experiment evaluation

- experiment_id: `final80_v2_four_routes`
- split: final-80-v2 (80 IDs)
- evaluation_note: final
- manifest: `evaluator\manifests\final80_v2_four_routes_template.json` (sha256 999ac0a4d13c)
- All declared runs are non-simulated.

- **Incomplete input:** missing IDs are retained in all-denominator metrics; this is not a complete final experiment.

## Runs

| Run | System | Provider | Simulated | OK | api_failed | invalid_contract | missing | Correct determinate / all | Coverage | Indeterminate | Selective risk |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gemini_e2e | e2e | gemini | no | 80 | 0 | 0 | 0 | 73.8% | 100.0% | 0.0% | 26.2% |
| gemini_assisted_cas | assisted_cas | gemini | no | 80 | 0 | 0 | 0 | 12.5% | 21.2% | 78.8% | 41.2% |
| gigachat_e2e | e2e | gigachat | no | 80 | 0 | 0 | 0 | 55.0% | 100.0% | 0.0% | 45.0% |
| gigachat_assisted_cas | assisted_cas | gigachat | no | 79 | 0 | 0 | 1 | 13.8% | 20.0% | 78.8% | 31.2% |

## H1 — paired Direct E2E vs Assisted Extraction → Task-aware CAS (gemini:gemini_e2e__gemini_assisted_cas)

Provider `gemini`. E2E run `gemini_e2e`, CAS run `gemini_assisted_cas`.

- Correct determinate verdicts / all IDs: E2E 73.8% vs CAS 12.5% (Δ +0.613, paired bootstrap 95% CI [+0.487, +0.725])
- McNemar exact p = 0.0000 (E2E-only correct 51, CAS-only correct 2)
- Correctness-outcome agreement over all IDs: 33.8%; both correct 8, both wrong 19
- Verdict agreement: 12/17 = 70.6% (only pairs with two determinate verdicts).

| Pair metric | E2E | CAS |
|---|---|---|
| Correct determinate / all IDs | 73.8% | 12.5% |
| Selective accuracy on covered | 73.8% | 58.8% |
| Coverage | 100.0% | 21.2% |
| Indeterminate share | 0.0% | 78.8% |
| Mean VLM latency, ms | 14739.875 | 14733.300 |
| Mean CAS latency, ms | — | 2415.425 |
| Mean end-to-end latency, ms | 14739.875 | 17148.725 |
| Provider-reported cost, ₽ | 65.742 | 73.979 |
| Token-rate estimate, ₽ | 64.923 | 0.000 |
| First-error acc, aligned (incorrect GT) | 43.9% | 17.1% |
| Incorrect F1 (covered only) | 0.764 | 0.741 |
| Specificity (correct) | 64.1% | 0.0% |
| Balanced accuracy (covered only) | 73.5% | 41.7% |
| Always Incorrect baseline | 51.2% | 51.2% |

## H1 — paired Direct E2E vs Assisted Extraction → Task-aware CAS (gigachat:gigachat_e2e__gigachat_assisted_cas)

Provider `gigachat`. E2E run `gigachat_e2e`, CAS run `gigachat_assisted_cas`.

- Correct determinate verdicts / all IDs: E2E 55.0% vs CAS 13.8% (Δ +0.413, paired bootstrap 95% CI [+0.300, +0.537])
- McNemar exact p = 0.0000 (E2E-only correct 35, CAS-only correct 2)
- Correctness-outcome agreement over all IDs: 53.8%; both correct 9, both wrong 34
- Verdict agreement: 10/16 = 62.5% (only pairs with two determinate verdicts).

| Pair metric | E2E | CAS |
|---|---|---|
| Correct determinate / all IDs | 55.0% | 13.8% |
| Selective accuracy on covered | 55.0% | 68.8% |
| Coverage | 100.0% | 20.0% |
| Indeterminate share | 0.0% | 78.8% |
| Mean VLM latency, ms | 8312.312 | 10607.177 |
| Mean CAS latency, ms | — | 2226.937 |
| Mean end-to-end latency, ms | 8312.312 | 12834.114 |
| Provider-reported cost, ₽ | — | — |
| Token-rate estimate, ₽ | — | — |
| First-error acc, aligned (incorrect GT) | 7.3% | 9.8% |
| Incorrect F1 (covered only) | 0.486 | 0.706 |
| Specificity (correct) | 69.2% | 62.5% |
| Balanced accuracy (covered only) | 55.3% | 68.8% |
| Always Incorrect baseline | 51.2% | 51.2% |

## H2 — OCR quality and propagation

### gemini:gemini_e2e__gemini_assisted_cas

Run `gemini_assisted_cas`. Exactly transcribed: 10/80 (12.5%). Mean step edit distance 19.738 (0.487 normalized).

Assisted determinate-verdict accuracy: 12.5%; indeterminate: 63/80 (78.8%).

| Transcription error class | Cases | Share | Final wrong | Failure share |
|---|---|---|---|---|
No GT→step-only CAS was used. TaskSpec fields have no independent GT and are reported only as structural diagnostics.

| extra_line | 30 | 37.5% | 86.7% | 37.1% |
| segmentation | 17 | 21.2% | 88.2% | 21.4% |
| missed_line | 12 | 15.0% | 100.0% | 17.1% |
| exact | 10 | 12.5% | 70.0% | 10.0% |
| ambiguous | 5 | 6.2% | 100.0% | 7.1% |
| variable | 3 | 3.8% | 100.0% | 4.3% |
| operator | 2 | 2.5% | 50.0% | 1.4% |
| digit | 1 | 1.2% | 100.0% | 1.4% |
### gigachat:gigachat_e2e__gigachat_assisted_cas

Run `gigachat_assisted_cas`. Exactly transcribed: 2/80 (2.5%). Mean step edit distance 42.575 (0.635 normalized).

Assisted determinate-verdict accuracy: 13.8%; indeterminate: 64/80 (80.0%).

| Transcription error class | Cases | Share | Final wrong | Failure share |
|---|---|---|---|---|
No GT→step-only CAS was used. TaskSpec fields have no independent GT and are reported only as structural diagnostics.

| extra_line | 35 | 43.8% | 85.7% | 43.5% |
| segmentation | 28 | 35.0% | 89.3% | 36.2% |
| missed_line | 8 | 10.0% | 87.5% | 10.1% |
| ambiguous | 3 | 3.8% | 100.0% | 4.3% |
| exact | 2 | 2.5% | 50.0% | 1.4% |
| variable | 2 | 2.5% | 100.0% | 2.9% |
| operator | 1 | 1.2% | 0.0% | 0.0% |
| transcription_error | 1 | 1.2% | 100.0% | 1.4% |

## H3 — selective automation

| Policy | Correct automated / all | Accuracy (automated) | Automation rate | Manual E2E errors | Captured E2E errors |
|---|---|---|---|---|---|
| gemini:gemini_e2e__gemini_assisted_cas: disagreement_only | 70.0% | 74.7% | 93.8% | 2/5 (40.0%) | 2/21 (9.5%) |
| gemini:gemini_e2e__gemini_assisted_cas: disagreement_or_cas_indeterminate | 10.0% | 66.7% | 15.0% | 17/68 (25.0%) | 17/21 (81.0%) |
| gigachat:gigachat_e2e__gigachat_assisted_cas: disagreement_only | 50.0% | 54.1% | 92.5% | 2/6 (33.3%) | 2/36 (5.6%) |
| gigachat:gigachat_e2e__gigachat_assisted_cas: disagreement_or_cas_indeterminate | 11.2% | 90.0% | 12.5% | 35/70 (50.0%) | 35/36 (97.2%) |

## Limitations

- Frozen and simulated sources keep api_failed/invalid_contract/missing cases in every denominator.
- The final comparison contains only Direct E2E and Assisted Extraction → Task-aware CAS; no GT→step-only CAS architecture is reported.
- Prompt configurations were frozen after dev-20 selection (docs/final_prompt_freeze.md). The CAS implementation was tuned using all 100 GT examples, so CAS-related final-80 results are not an independent CAS holdout.
- CDN/OS availability noise and OCR failures are reported as statuses and are not silently dropped.
