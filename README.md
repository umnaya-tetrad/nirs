# NIRS: Gemini baseline

Reproducible P0 baseline for two experiments on handwritten mathematical solutions:

- `e2e`: image → first-error verdict, lifted into `SolutionAnalysis`;
- `extraction`: image → LaTeX transcription, lifted into `MathCoreInput` for the future CAS branch.

The large schemas in `data_contracts/` remain unchanged. Gemini is asked only for the small semantic projection needed for P0; the adapter supplies run metadata and validates the final artifact against those original schemas.

## Local setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Put `POLZA_API_KEY` in `.env`; it is ignored by Git. Create `devset/manifest.json` from `devset/manifest.example.json` and place its images next to the manifest.

## Smoke run

```powershell
python -m nirs_llm.run --mode e2e --manifest devset/manifest.json
python -m nirs_llm.run --mode extraction --manifest devset/manifest.json
pytest -q
```

Every request creates one gitignored JSON artifact under `outputs/`. It contains the raw model response, parsed contract, provider model, token/cost usage when Polza returns it, and measured latency. The baseline uses `google/gemini-3.7-flash`, `temperature=0`, `response_format=json_object`, and the fixed prompt versions `e2e_gemini_v1` / `extraction_gemini_v1`.

`GigaChatAdapter` deliberately exposes the same future provider boundary but raises `NotImplementedError` until a model identifier and credentials are agreed.
