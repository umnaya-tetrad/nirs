# Final prompt freeze

The four files below are the fixed configurations selected on dev-20.  They are not
retuned on final-80.  Every runner artifact stores the model, temperature (`0`), prompt
version, schema version and SHA-256; evaluator manifests recompute the SHA before use.

| provider | module | files | schema version | SHA-256 |
|---|---|---|---|---|
| Gemini `google/gemini-3.7-flash` | E2E | `prompts/gemini/e2e/v1/` | `e2e_gemini_v1` | `0be3fa5de3f674ee4fcb429083d5282d5f6bef066f70baf534100d66fde8a8ad` |
| Gemini `google/gemini-3.7-flash` | Assisted Extraction | `prompts/gemini/assisted_extraction/v2/` | `assisted_extraction_gemini_v2` | `fbe6f85d18ca8bfac63eeef5a186d273acaed8e8b4d3309b31c65c887bd364f5` |
| GigaChat `GigaChat-2-Pro` | E2E | `prompts/gigachat/e2e/v1/` | `e2e_gigachat_v1` | `9507fca818e2caa7b41c14a62b6415f0d975dd76347047ae591ce80f12f8a10d` |
| GigaChat `GigaChat-2-Pro` | Assisted Extraction | `prompts/gigachat/assisted_extraction/v2/` | `assisted_extraction_gigachat_v2` | `f35da71fe3c123ee868179debc8bcc6fdffe52adcd51b05beb0652617bc286c6` |

Ordinary Extraction returns only visible `steps[].latex` and ambiguity flags. Assisted
Extraction additionally returns the visibly transcribed task (`task`), step roles,
dependencies (`derives_from`), used givens, branch and exactness so the fixed CAS adapter
can build a `TaskSpec`. The inputs are still only the image plus the static prompt: no GT
verdict, first-error label, reference explanation or domain annotation is supplied.

Do not put ordinary-extraction artifacts in the assisted paths named by
`evaluator/manifests/final80_cas_supported_template.json`; mode, schema version and SHA
are checked by the runner/evaluator provenance.
