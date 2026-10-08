# Gemini E2E: dev prompt iteration

The baseline used `e2e/gemini/v1` for all 20 dev cases. The runner saved an
artifact for every case; transient API failures were retried individually.
Nineteen responses ultimately passed the output contract. `img_96_pert_2.1`
remained a `PolzaUnavailableError` after three attempts, so it has no Gemini
verdict and was not used to tune v2. The primary label authority is the FERMAT
source record (`has_error`, `pert_a`, `pert_reasoning`), with GT checked against
it; the photograph is used only to resolve a transcription question.

| ID | GT verdict | v1 | v2 | Reason for v1 error | Change | v1 latency/tokens | v2 latency/tokens | v2 contract |
|---|---|---|---|---|---|---|---|---|
| `img_136_pert_2.2` | incorrect | correct | incorrect | The factorisation task was turned into solving an equation. | verdict fixed | 15,979 ms / 3,204 | 18,060 ms / 2,990 | valid |
| `img_221_pert_5.3` | correct | incorrect | — | V1 falsely flagged the source-recorded correct simplification. | API unavailable after two v2 attempts | 21,891 ms / 3,870 | — | unavailable |

V2 fixes the measured error `img_136_pert_2.2` and now identifies the first
wrong line as `s2`. It is **not yet accepted as the frozen Gemini prompt**:
the second baseline-error case has no v2 model response, so the planned
two-case comparison is incomplete. A later retry must use only
`img_221_pert_5.3` and this same v2 artifact.

The full v1 run is local and ignored under
`outputs/20261008T124440Z_gemini_e2e_e2e_gemini_v1/`; retry artifacts and the
v2 result are in sibling timestamped directories. Every new artifact includes
the full applied prompt and its SHA-256.
