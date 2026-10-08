# Versioned prompt artifacts

Every provider/mode/version directory contains the exact `system.txt` and
`user.txt` sent to the model. Existing versions are immutable research
artifacts: a change is made by adding `v<N+1>`, never by editing an old file.

Run a specific artifact with:

```bash
python -m nirs_llm.run --provider gemini --mode e2e \
  --prompt-version v2 --manifest dataset/manifests/fermat_dev_20.json
```

Each output JSON saves the provider, mode, short version, rendered schema
version, both applied prompt texts, and a SHA-256 fingerprint. The runner can
rerun a fixed subset without changing manifest order:

```bash
python -m nirs_llm.run --provider gigachat --mode e2e \
  --prompt-version v2 --case-ids-file reports/prompt_tuning/gigachat_e2e_v1_errors.json \
  --manifest dataset/manifests/fermat_dev_20.json
```

The case-ID file may be a JSON string array or an object with an `ids` array.
