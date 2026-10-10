# Experiment evaluation

- experiment_id: `dev20_gemini_assisted_preflight`
- split: fermat-dev-20 (20 IDs)
- evaluation_note: exploratory_preflight_incomplete_e2e_by_design
- manifest: `evaluator\manifests\dev20_gemini_assisted_preflight.json` (sha256 2e02fe59294b)
- All declared runs are non-simulated.

- **Incomplete input:** missing IDs are retained in all-denominator metrics; this is not a complete final experiment.

## Runs

| Run | System | Provider | Simulated | OK | api_failed | invalid_contract | missing | Verdict acc | Coverage | Indeterminate | Selective risk |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gemini_e2e | e2e | gemini | no | 1 | 1 | 0 | 18 | 5.0% | 5.0% | 0.0% | 0.0% |
| gemini_assisted_cas | assisted_cas | gemini | no | 20 | 0 | 0 | 0 | 55.0% | 55.0% | 45.0% | 0.0% |

## H1 — paired Direct E2E vs Assisted Extraction → Task-aware CAS (gemini:gemini_e2e__gemini_assisted_cas)

Provider `gemini`. E2E run `gemini_e2e`, CAS run `gemini_assisted_cas`.

- Verdict accuracy: E2E 5.0% vs CAS 55.0% (Δ -0.500, paired bootstrap 95% CI [-0.700, -0.300])
- McNemar exact p = 0.0020 (E2E-only correct 0, CAS-only correct 10)
- Agreement 50.0%; both correct 1, both wrong 9

| Pair metric | E2E | CAS |
|---|---|---|
| Verdict accuracy (all) | 5.0% | 55.0% |
| Accuracy on covered | 100.0% | 100.0% |
| Coverage | 5.0% | 55.0% |
| Indeterminate share | 0.0% | 45.0% |
| Mean VLM latency, ms | 18702.000 | 17291.250 |
| Mean CAS latency, ms | — | 1523.850 |
| Mean end-to-end latency, ms | 18702.000 | 18815.100 |
| Provider-reported cost, ₽ | 0.818 | 16.745 |
| Token-rate estimate, ₽ | 0.809 | 0.000 |
| First-error acc, aligned (incorrect GT) | 0.0% | 22.2% |
| Incorrect F1 | 0.000 | 0.714 |
| Specificity (correct) | 100.0% | 100.0% |
| Balanced accuracy | 50.0% | 77.8% |
| Always Incorrect baseline | 45.0% | 45.0% |

## H2 — OCR quality and propagation

### gemini:gemini_e2e__gemini_assisted_cas

Run `gemini_assisted_cas`. Exactly transcribed: 7/20 (35.0%). Mean step edit distance 15.450 (0.523 normalized).

Assisted determinate-verdict accuracy: 55.0%; indeterminate: 9/20 (45.0%).

| Transcription error class | Cases | Share | Final wrong | Failure share |
|---|---|---|---|---|
No GT→step-only CAS was used. TaskSpec fields have no independent GT and are reported only as structural diagnostics.

| missed_line | 9 | 45.0% | 44.4% | 44.4% |
| exact | 7 | 35.0% | 14.3% | 11.1% |
| extra_line | 4 | 20.0% | 100.0% | 44.4% |

## H3 — selective automation

| Policy | Accuracy (all) | Accuracy (automated) | Automation rate | Manual E2E error rate | Captured E2E errors |
|---|---|---|---|---|---|
| gemini:gemini_e2e__gemini_assisted_cas: disagreement_only | 5.0% | 100.0% | 5.0% | — | — |
| gemini:gemini_e2e__gemini_assisted_cas: disagreement_or_cas_indeterminate | 5.0% | 100.0% | 5.0% | — | — |

## Limitations

- Frozen and simulated sources keep api_failed/invalid_contract/missing cases in every denominator.
- CAS-on-GT uses reference steps; it bounds the pipeline but is not available at inference time.
- Prompt/CAS tuning saw all 100 GT examples, so results on dev/final splits are exploratory, not independent holdout.
- CDN/OS availability noise and OCR failures are reported as statuses and are not silently dropped.
