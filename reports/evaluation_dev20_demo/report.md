# Experiment evaluation

- experiment_id: `dev20_demo`
- split: dev-20 (20 IDs)
- evaluation_note: exploratory
- manifest: `evaluator/manifests/dev20_demo.json` (sha256 50c35d55cdf2)

## Runs

| Run | System | Provider | Simulated | OK | api_failed | invalid_contract | missing | Verdict acc | Coverage | Indeterminate | Selective risk |
|---|---|---|---|---|---|---|---|---|---|---|---|
| e2e_gemini_v2 | e2e | gemini | yes | 18 | 1 | 1 | 0 | 80.0% | 90.0% | 0.0% | 11.1% |
| cas_gemini_v2 | extraction_cas | gemini | no | 20 | 0 | 0 | 0 | 50.0% | 55.0% | 45.0% | 9.1% |
| assisted_cas_gemini_v2 | assisted_cas | gemini | no | 20 | 0 | 0 | 0 | 25.0% | 35.0% | 65.0% | 28.6% |

## H1 — paired E2E vs extraction→CAS (gemini:e2e_gemini_v2__cas_gemini_v2)

Provider `gemini`. E2E run `e2e_gemini_v2`, CAS run `cas_gemini_v2`.

- Verdict accuracy: E2E 80.0% vs CAS 50.0% (Δ +0.300, paired bootstrap 95% CI [+0.050, +0.550])
- McNemar exact p = 0.0703 (E2E-only correct 7, CAS-only correct 1)
- Agreement 60.0%; both correct 9, both wrong 3

| Pair metric | E2E | CAS |
|---|---|---|
| Verdict accuracy (all) | 80.0% | 50.0% |
| Accuracy on covered | 88.9% | 90.9% |
| Coverage | 90.0% | 55.0% |
| Indeterminate share | 0.0% | 45.0% |
| First-error acc (incorrect GT) | 77.8% | 22.2% |
| Incorrect F1 | 0.889 | 0.933 |

## H1 — paired E2E vs extraction→CAS (gemini:e2e_gemini_v2__assisted_cas_gemini_v2)

Provider `gemini`. E2E run `e2e_gemini_v2`, CAS run `assisted_cas_gemini_v2`.

- Verdict accuracy: E2E 80.0% vs CAS 25.0% (Δ +0.550, paired bootstrap 95% CI [+0.300, +0.800])
- McNemar exact p = 0.0034 (E2E-only correct 12, CAS-only correct 1)
- Agreement 35.0%; both correct 4, both wrong 3

| Pair metric | E2E | CAS |
|---|---|---|
| Verdict accuracy (all) | 80.0% | 25.0% |
| Accuracy on covered | 88.9% | 71.4% |
| Coverage | 90.0% | 35.0% |
| Indeterminate share | 0.0% | 65.0% |
| First-error acc (incorrect GT) | 77.8% | 11.1% |
| Incorrect F1 | 0.889 | 0.833 |

## H2 — OCR quality and propagation

Run `cas_gemini_v2`. Exactly transcribed: 5/20 (25.0%). Mean step edit distance 11.700 (0.431 normalized).

CAS verdict accuracy: 50.0% on OCR steps vs 45.0% on GT steps (drop -0.050). CAS flips due to OCR: 0/20 (0.0%).

| Error class | Cases | Share | CAS flips | Final wrong | Failure share |
|---|---|---|---|---|---|
| missed_line | 7 | 35.0% | 0 (0.0%) | 42.9% | 30.0% |
| extra_line | 6 | 30.0% | 0 (0.0%) | 50.0% | 30.0% |
| exact | 5 | 25.0% | 0 (0.0%) | 60.0% | 30.0% |
| ambiguous | 2 | 10.0% | 0 (0.0%) | 50.0% | 10.0% |

## H3 — selective automation

| Policy | Accuracy (all) | Accuracy (automated) | Automation rate |
|---|---|---|---|
| disagreement_routing | 45.0% | 100.0% | 45.0% |
| e2e_only | 80.0% | 88.9% | 90.0% |
| cas_only | 50.0% | 90.9% | 55.0% |

## Limitations

- Frozen and simulated sources keep api_failed/invalid_contract/missing cases in every denominator.
- CAS-on-GT uses reference steps; it bounds the pipeline but is not available at inference time.
- Prompt/CAS tuning saw all 100 GT examples, so results on dev/final splits are exploratory, not independent holdout.
- CDN/OS availability noise and OCR failures are reported as statuses and are not silently dropped.
