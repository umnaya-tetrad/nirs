# GigaChat E2E: dev prompt iteration

The v1 baseline is the existing full dev-20 run. The ten cases below follow
FERMAT source fields and the GT derived from them; the photograph is used only
as a transcription cross-check.

| ID | GT verdict | v1 | v2 | Reason for v1 error | Change | v1 latency/tokens | v2 latency/tokens | v2 contract |
|---|---|---|---|---|---|---|---|---|
| `img_110_pert_1.3` | incorrect | correct | — | Missed the erroneous intermediate trigonometric reduction. | contract regression | 18,950 ms / 2,117 | 15,259 ms / 2,179 | invalid: `text` instead of `latex` |
| `img_128_pert_1.5` | incorrect | correct | — | Read `sqrt[3]{9000}` as if it yielded 20. | contract regression | 9,492 ms / 2,072 | — | invalid JSON response |
| `img_136_pert_2.2` | incorrect | correct | correct | Missed that factorisation was replaced by root-finding. | unchanged | 22,496 ms / 2,348 | 32,949 ms / 2,552 | valid |
| `img_157_pert_3.2` | incorrect | correct | correct | Missed a sum changed into a product. | unchanged | 11,589 ms / 2,100 | 15,951 ms / 2,195 | valid |
| `img_225_pert_2.4` | incorrect | correct | correct | Normalised photographed `3^3` into `3^2`. | unchanged | 10,401 ms / 2,085 | 9,479 ms / 2,065 | valid |
| `img_398_pert_4.4` | incorrect | correct | correct | Normalised the final `dz/dx` typo into `dy/dx`. | unchanged | 17,546 ms / 2,252 | 17,871 ms / 2,250 | valid |
| `img_462_pert_5.1` | correct | incorrect | correct | Misread the determinant entries. | verdict fixed | 10,158 ms / 2,104 | 9,107 ms / 2,540 | valid |
| `img_480_pert_2.5` | incorrect | correct | correct | Missed an invalid inequality transformation. | unchanged | 15,383 ms / 2,175 | 13,326 ms / 2,121 | valid |
| `img_494_pert_5.2` | correct | incorrect | incorrect | Misread the leading `2x` as `9x` in v2; v1 already marked the correct work incorrect. | unchanged | 8,685 ms / 1,843 | 8,519 ms / 2,494 | valid |
| `img_96_pert_2.1` | incorrect | correct | correct | Recomputed the photographed `-16/65` as `-56/65`. | unchanged | 29,227 ms / 2,562 | 32,891 ms / 2,559 | valid |

V2 fixes one of ten baseline errors (`img_462_pert_5.1`) but leaves seven
valid responses wrong and introduces two contract-invalid responses.
It is **not selected** for future GigaChat E2E runs: valid-contract coverage
fell from 10/10 to 8/10, so a one-case verdict gain is not sufficient.

The baseline is local at
`outputs/20261008T121908Z_gigachat_e2e_e2e_gigachat_v1/`; the v2 subset is at
`outputs/20261008T125638Z_gigachat_e2e_e2e_gigachat_v2/`.
