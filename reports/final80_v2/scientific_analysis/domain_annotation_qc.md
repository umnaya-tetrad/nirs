# QC доменной разметки final-80 v2

## Проверки целостности

- Records in sidecar: **80/80**; exact manifest ID match: **True**.
- Images present: **80/80**; missing: none.
- Canonical GT present: **80/80**; missing: none.
- Schema: passed `python -m evaluator.domains validate --require-complete`.
- Annotation input intentionally excluded all E2E predictions, CAS verdicts, failures and metrics.

## Taxonomy and evidence

Primary `domain` denotes the mathematical object/operation; `task_type` is descriptive; `features` encode notation/constructions. Thus `word_problem` is not treated as a mathematical domain.
Every sidecar record records `annotation_source`: canonical GT steps for inherited final rows; canonical GT plus original FERMAT question/domain/subdomain for 22 replacement rows.

## Visual review scope

Direct visual checks were deliberately limited and are not represented as an image-by-image manual audit. Confirmed visual samples:
- `img_374_pert_5.1`
- `img_465_pert_1.3`
- `img_65_pert_5.1`

The following **77** source-checked IDs retain `source_checked_not_visually_audited` and are the concrete human visual-review queue:

`img_400_pert_5.1`, `img_19_pert_5.1`, `img_559_pert_5.1`, `img_464_pert_5.1`, `img_387_pert_5.1`, `img_22_pert_5.1`, `img_568_pert_5.2`, `img_482_pert_5.2`, `img_559_pert_5.2`, `img_448_pert_5.2`, `img_173_pert_5.3`, `img_165_pert_5.3`, `img_193_pert_5.3`, `img_375_pert_5.3`, `img_233_pert_3.2`, `img_190_pert_3.2`, `img_559_pert_3.2`, `img_172_pert_3.2`, `img_586_pert_3.2`, `img_448_pert_3.2`, `img_173_pert_2.5`, `img_35_pert_2.5`, `img_375_pert_2.5`, `img_574_pert_2.5`, `img_395_pert_2.5`, `img_68_pert_2.5`, `img_111_pert_1.3`, `img_463_pert_1.3`, `img_108_pert_1.4`, `img_427_pert_1.4`, `img_472_pert_1.4`, `img_503_pert_1.4`, `img_466_pert_1.4`, `img_111_pert_2.1`, `img_98_pert_2.1`, `img_372_pert_2.1`, `img_109_pert_2.1`, `img_223_pert_2.2`, `img_465_pert_2.2`, `img_529_pert_2.2`, `img_573_pert_2.2`, `img_226_pert_2.2`, `img_176_pert_4.3`, `img_92_pert_4.3`, `img_91_pert_2.3`, `img_112_pert_4.4`, `img_115_pert_4.4`, `img_529_pert_4.5`, `img_160_pert_2.4`, `img_560_pert_1.5`, `img_465_pert_1.5`, `img_540_pert_1.5`, `img_153_pert_1.5`, `img_194_pert_1.5`, `img_220_pert_1.5`, `img_220_pert_4.6`, `img_476_pert_5.1`, `img_579_pert_5.1`, `img_578_pert_5.1`, `img_489_pert_5.1`, `img_490_pert_5.1`, `img_483_pert_5.1`, `img_592_pert_5.1`, `img_456_pert_5.1`, `img_455_pert_5.1`, `img_458_pert_5.1`, `img_566_pert_5.1`, `img_572_pert_5.1`, `img_27_pert_5.1`, `img_14_pert_5.1`, `img_49_pert_5.1`, `img_77_pert_5.1`, `img_78_pert_5.1`, `img_37_pert_5.1`, `img_20_pert_5.1`, `img_492_pert_5.1`, `img_488_pert_5.1`

`uncertain=true` records: none. No category was marked uncertain because canonical GT plus relevant FERMAT metadata identify its mathematical object; this does not substitute for the visual-review queue above.

## Interpretation limits

This is a post-hoc, descriptive/exploratory annotation. It was not used to select final-80 v2 or tune prompts/CAS. Small domains (function and inequality, n=1) are reported but are not suitable for comparative inference.
