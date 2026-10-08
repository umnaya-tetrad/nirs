# LLM-assisted extraction: dev-20 experiment

## Scope

This is an exploratory, separate arm.  It does not modify the ordinary
`extraction` OCR contract, `test_gt.json`, `final_gt.json`, or a production
CAS metric.  The assistant may transcribe visible task context and attach
structural links, but it cannot return a verdict, an error step, a correction,
or a proposed correct answer.

The manifest is
[`dataset/manifests/assisted_extraction_dev_20.json`](../../dataset/manifests/assisted_extraction_dev_20.json):

- 10 existing FERMAT dev images, with corresponding `test_gt.json` steps;
- 10 EGE examples from `inputExamples/llmJsonTest`;
- every selected image was visually checked to contain its task statement.

The FERMAT images originally described as possibly missing a task statement
were rechecked: all ten selected images actually show one.  Thus this is a
20/20 *visible-task* experiment; it does not measure the `not_visible` path.

## Contract result

| Provider / prompt | Valid contracts | Notes |
| --- | ---: | --- |
| Gemini v1 | 0 / 20 | The semantic content was often present, but nested JSON did not follow the unstated exact forms: `goal` was a string, `id` was used instead of `given_id`, and constraints were objects. One request had a temporary Polza failure. |
| Gemini v2 | **20 / 20** | All task statements marked `visible`; all outputs passed `llm_assisted_extraction.schema.json`. One request succeeded on retry. |
| GigaChat v1 | not completed | Stopped after the Gemini-v1 diagnosis; its output would not test a sufficiently specified contract. |
| GigaChat v2 | **16 / 20** | One `target_laex` typo caused a contract rejection; three responses were invalid JSON because LaTex backslashes were not escaped. One network retry succeeded. |
| GigaChat v3, v2-failure subset | **3 / 3 answered** | The three former JSON/field-format failures passed after v3. The fourth case, `hf-task15-15-2-2-maximal`, exhausted three retries waiting for the chat endpoint and did not return a model response. |
| GigaChat v3, remaining 16 | **13 / 16** | Three other long EGE/trigonometry answers still returned malformed JSON with a lone LaTex backslash, despite the v3 escaping instruction. |

V1 prompt files remain unchanged research artifacts.  V2 explicitly specifies
every nested field and is the default version for `assisted_extraction`.

GigaChat v3 additionally does not ask for the optional `goal.target_latex` and
requires JSON escaping of every LaTex backslash.  OAuth and the file endpoint
were checked separately after the retry failure and both succeeded; the
unanswered EGE case therefore points to the `chat/completions` request timing
out on a long response, not an expired key or a file-upload problem.  A later
short health-check request succeeded in 10.8 seconds, so the remaining 16 were
run.  In total v3 has 16 valid contracts, 3 malformed-JSON responses, and 1
chat-endpoint timeout across the 20 unique cases.  It therefore is not promoted
to the default prompt version.

## Manual content check

### Gemini v2

All ten EGE task statements and all ten FERMAT task statements were recognised
as present.  Their equations, requested operation, interval constraints and
matrix/determinant data were materially preserved.  The solution transcription
is suitable as a candidate input for a subsequent verifier, with the caveat
that line segmentation differs from GT (for example, all four written
equalities of `img_151_pert_5.3` are one image line and were returned as one
step).

In `img_221_pert_5.3`, the photo writes `5^{-2} \\times 8^{-2}` but then jumps
to `8^2/5^2` and the numerically correct final answer.  The FERMAT source fields
describe this perturbation as harmless, but project GT deliberately follows the
photo and marks `s3` incorrect: a wrong intermediate step remains an error even
when a later answer happens to be correct.  Gemini faithfully transcribed the
photo and must not be scored as an OCR error here.

### GigaChat v2

Valid JSON does not itself establish faithful content.  The manual inspection
found clear visual transcription errors among the valid results: `img_452_pert_5.2`
reads the matrix entry `9` as `q`; `img_494_pert_5.2` reads `2x` as `9x`; and
some determinant lines are restructured rather than copied.  One EGE response
contains only one extracted line despite a multi-line solution.  Therefore the
GigaChat v2 result is insufficient evidence for using this assistant as a
trusted task-context source.

## Conclusion

The hypothesis is supported for Gemini only at this stage: a VLM can honour
the assisted contract and provide task context without emitting a verdict.
This is not evidence that a CAS will improve yet.  The next experiment, if
desired, is to feed *only Gemini v2 accepted fields* into a deterministic
`TaskSpec` compiler and compare CAS coverage with ordinary OCR→CAS on a held
out set.  No `has_error`, FERMAT answer, perturbed answer, or reasoning field
may enter that compiler.
