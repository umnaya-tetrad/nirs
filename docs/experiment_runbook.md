# Reproducible experiment runbook

The images are local in `data/images/` and both manifests validate them before a request is sent.
All VLM requests below use `--workers 1`. Every result (including a failure diagnostic) is persisted
before the next billable request starts. Transient 429/5xx/network failures receive bounded exponential
backoff and jitter; restart an interrupted named run with `--resume` rather than resending completed IDs.

For example, resume a partially completed Gemini E2E run with:

```powershell
python -m nirs_llm.run --provider gemini --mode e2e --manifest dataset/manifests/fermat_final_80.json --output-dir outputs/final80 --run-name gemini-e2e --workers 1 --resume
```

`run_metadata.json` in every named output directory lists successful, failed and not-attempted IDs.
The evaluator keeps missing/failed IDs in the all-ID denominator and marks the report incomplete.

## Independent mathematical-domain annotation

The optional sidecar has no connection to model prompts or CAS inputs. Fill
`dataset/annotations/math_domains_final80_template.csv`, then transfer rows to
`dataset/annotations/math_domains_final80.json` with one `solution_id`, one `domain`, and zero or
more `features`. Allowed values and ID validity are checked by:

```powershell
python -m evaluator.domains validate --manifest dataset/manifests/fermat_final_80.json --sidecar dataset/annotations/math_domains_final80.json --require-complete
```

The final evaluator manifests already declare this sidecar. Once filled, `domain_metrics.csv`
contains per-domain counts, coverage and accuracy, with a small-sample warning for fewer than five examples.

## Experiment A: final-80 E2E

```powershell
python -m nirs_llm.run --provider gemini --mode e2e --manifest dataset/manifests/fermat_final_80.json --output-dir outputs/final80 --run-name gemini-e2e --workers 1
python -m nirs_llm.run --provider gigachat --mode e2e --manifest dataset/manifests/fermat_final_80.json --output-dir outputs/final80 --run-name gigachat-e2e --workers 1
python -m evaluator experiment --manifest evaluator/manifests/final80_e2e_template.json --output-dir reports/final80/e2e-evaluation
```

## Experiment B: fixed CAS-supported final subset

The subset is generated only from GT→CAS operational statuses, never from agreement with GT labels:

```powershell
python -m nirs_cas supported-subset --oracle-report reports/cas_gt_100/report.json --gt dataset/final_gt.json --output dataset/subsets/cas_supported_final_80.json
```

Use its `ids` array as `--case-ids-file` for all four runs. Save that same JSON under
`dataset/subsets/cas_supported_final_80_ids.json` (or pass the subset file directly, since it has
an `ids` field):

```powershell
python -m nirs_llm.run --provider gemini --mode assisted_extraction --manifest dataset/manifests/fermat_final_80.json --case-ids-file dataset/subsets/cas_supported_final_80.json --output-dir outputs/final80-cas-supported --run-name gemini-assisted-extraction --workers 1
python -m nirs_llm.run --provider gigachat --mode assisted_extraction --manifest dataset/manifests/fermat_final_80.json --case-ids-file dataset/subsets/cas_supported_final_80.json --output-dir outputs/final80-cas-supported --run-name gigachat-assisted-extraction --workers 1

python -m nirs_cas assisted-oracle outputs/final80-cas-supported/gemini-assisted-extraction --output reports/final80-cas-supported/gemini-assisted-cas --split-name final80_cas_supported_gemini --timeout 10
python -m nirs_cas assisted-oracle outputs/final80-cas-supported/gigachat-assisted-extraction --output reports/final80-cas-supported/gigachat-assisted-cas --split-name final80_cas_supported_gigachat --timeout 10
python -m evaluator experiment --manifest evaluator/manifests/final80_cas_supported_template.json --output-dir reports/final80-cas-supported/evaluation
```

The evaluator writes `report.json`, `report.md`, per-case CSVs and `plots/*.svg`. A final manifest
rejects simulated sources and rejects any run or extraction bundle whose IDs differ from the fixed
dataset list.

Experiment B reuses the final-80 E2E artifacts from Experiment A through an explicit
`select_manifest_ids` declaration in its evaluator manifest; it does not resend those 68 requests.

For Gemini, a `cost_rub.provider_reported` value is used whenever Polza returned `usage.cost_rub`.
Otherwise the report labels the calculation as `token_rate_estimate`; the rate in the templates is
the Polza catalogue value checked on 2026-10-10, not a billing receipt.

## Frozen final-80 v2 (the next paid run)

`final-80 v1` remains in place for reproducibility.  Do not reuse its output folders,
manifests or CAS subset for v2.  The v2 release has 80 IDs in
`dataset/manifests/fermat_final_80_v2.json`, canonical labels in
`dataset/final_gt_v2.json`, and its own 28-ID (current local CAS result) subset in
`dataset/subsets/cas_supported_final_80_v2.json`.  The 20 replacement images must be
present under `data/images/final_v2/`; verify the frozen release before sending a request:

```powershell
python dataset_scripts/build_final80_v2.py
python -m pytest tests/test_gt_splits.py
python -m nirs_cas oracle dataset/final_gt_v2.json --output reports/cas_gt_final80_v2_frozen --timeout 10 --workers 4 --split-name final80_v2_gt_frozen
python -m nirs_cas supported-subset --oracle-report reports/cas_gt_final80_v2_frozen/report.json --gt dataset/final_gt_v2.json --output dataset/subsets/cas_supported_final_80_v2.json
```

Experiment A (80 images, no CAS) uses separate persistent output paths:

```powershell
python -m nirs_llm.run --provider gemini --mode e2e --manifest dataset/manifests/fermat_final_80_v2.json --output-dir outputs/final80_v2 --run-name gemini-e2e --workers 1
python -m nirs_llm.run --provider gigachat --mode e2e --manifest dataset/manifests/fermat_final_80_v2.json --output-dir outputs/final80_v2 --run-name gigachat-e2e --workers 1
python -m evaluator experiment --manifest evaluator/manifests/final80_v2_e2e_template.json --output-dir reports/final80_v2/e2e-evaluation
```

Experiment B uses exactly the frozen v2 subset for both providers and reuses the v2 E2E
artifacts via `select_manifest_ids`:

```powershell
python -m nirs_llm.run --provider gemini --mode assisted_extraction --manifest dataset/manifests/fermat_final_80_v2.json --case-ids-file dataset/subsets/cas_supported_final_80_v2.json --output-dir outputs/final80_v2-cas-supported --run-name gemini-assisted-extraction --workers 1
python -m nirs_llm.run --provider gigachat --mode assisted_extraction --manifest dataset/manifests/fermat_final_80_v2.json --case-ids-file dataset/subsets/cas_supported_final_80_v2.json --output-dir outputs/final80_v2-cas-supported --run-name gigachat-assisted-extraction --workers 1
python -m nirs_cas assisted-oracle outputs/final80_v2-cas-supported/gemini-assisted-extraction --output reports/final80_v2-cas-supported/gemini-assisted-cas --split-name final80_v2_cas_supported_gemini --timeout 10
python -m nirs_cas assisted-oracle outputs/final80_v2-cas-supported/gigachat-assisted-extraction --output reports/final80_v2-cas-supported/gigachat-assisted-cas --split-name final80_v2_cas_supported_gigachat --timeout 10
python -m evaluator experiment --manifest evaluator/manifests/final80_v2_cas_supported_template.json --output-dir reports/final80_v2-cas-supported/evaluation
```

For any interrupted paid run, add `--resume` to the same command.  The runner keeps
the already persisted successful and failed IDs and does not resubmit them.
