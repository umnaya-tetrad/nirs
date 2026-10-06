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

Put `POLZA_API_KEY` and/or `GIGACHAT_AUTHORIZATION_KEY` in `.env`; it is ignored by Git. Create `devset/manifest.json` from `devset/manifest.example.json` and place its images next to the manifest.

## Smoke run

```powershell
python -m nirs_llm.run --mode e2e --manifest devset/manifest.json
python -m nirs_llm.run --mode extraction --manifest devset/manifest.json
pytest -q
```

## Direct GigaChat smoke request

`GigaChat-2-Pro` is used through the direct API. The adapter exchanges the authorization
key for a short-lived token, uploads one image, sends its file ID in `attachments`, and
deletes the temporary remote file afterwards. Test the integration with exactly one paid
request before any batch run:

```powershell
python -m nirs_llm.run --provider gigachat --mode e2e --manifest inputExamples/llmJsonTest/manifest.json --max-cases 1 --fail-fast
```

`--fail-fast` writes the diagnostic JSON and exits non-zero for OAuth, upload, HTTP 4xx/5xx,
non-JSON output, wrong prompt schema version, or final contract-validation failure. Therefore
it cannot continue to subsequent cases and spend more inference tokens after a bad response.
Use the same command with `--mode extraction` only after the E2E smoke run passes.
If an execution environment interrupts a successful batch, use `--skip-cases N` to resume
from the next manifest entry without resending the first `N` cases.

GigaChat uses the Russian Ministry of Digital Development certificate chain. On its first
direct request the adapter downloads the official root PEM into the gitignored
`.nirs-certs/` directory, verifies its pinned SHA-256, and then uses it for TLS. The client
uses `trust_env=False` (no system proxy) and never disables TLS verification. Set
`GIGACHAT_CA_BUNDLE` only if your organisation requires a custom trusted CA file.

Every request creates one gitignored JSON artifact under `outputs/`. It contains the raw model response, parsed contract, provider model, token/cost usage when Polza returns it, and measured latency. The baseline uses `google/gemini-3.7-flash`, `temperature=0`, `response_format=json_object`, and the fixed prompt versions `e2e_gemini_v1` / `extraction_gemini_v1`.

The fixed direct GigaChat prompt versions are `e2e_gigachat_v1` and
`extraction_gigachat_v2`; they are semantically identical to the Gemini baseline while
remaining independently versioned for provider-specific corrections.

For direct `GigaChat-2-Pro` responses, `usage.estimated_cost_rub` is calculated from the
fixed synchronous list price of `0.5 ₽ / 1,000 tokens` (including VAT), checked on
2026-10-07. It is a comparable list-price estimate, not a billing statement: the physical
person Freemium allowance can make the actual charge zero.
