# Assisted-CAS: mixed-20 engineering coverage

| ID | Task class | Verdict | Fallback reason |
|---|---|---|---|
| hf-task13-13-1-1-maximal | trigonometric | indeterminate | assisted context unavailable: parametric trig families require an exact family parser |
| hf-task13-13-1-3-non-maximal | trigonometric | indeterminate | assisted context unavailable: parametric trig families require an exact family parser |
| hf-task13-13-1-4-non-maximal | trigonometric | indeterminate | assisted context unavailable: parametric trig families require an exact family parser |
| hf-task13-13-2-1-maximal | trigonometric | indeterminate | assisted context unavailable: SymPy could not solve the trigonometric equation exactly |
| hf-task13-13-2-2-maximal | trigonometric | indeterminate | assisted context unavailable: SymPy could not solve the trigonometric equation exactly |
| hf-task13-13-2-3-non-maximal | trigonometric | indeterminate | assisted context unavailable: SymPy could not solve the trigonometric equation exactly |
| hf-task13-13-4-3-zero | trigonometric | indeterminate | assisted context unavailable: parametric trig families require an exact family parser |
| hf-task15-15-1-2-non-maximal | inequality | indeterminate | assisted context unavailable: inequality is outside the exact univariate parser subset |
| hf-task15-15-2-1-maximal | inequality | indeterminate | assisted context unavailable: inequality is outside the exact univariate parser subset |
| hf-task15-15-2-2-maximal | inequality | indeterminate | assisted context unavailable: inequality is outside the exact univariate parser subset |
| img_151_pert_5.3 | expression | correct | — |
| img_221_pert_5.3 | expression | incorrect | assisted context unavailable: task has no explicit mathematical target |
| img_373_pert_5.2 | definite_integral | incorrect | Continuation has no readable predecessor; Exact expression identity with preserved domain |
| img_452_pert_5.2 | matrix_system | indeterminate | Symbolic equation is a premise; checked against previous equation when applicable; Separate equation/substitution requires task context |
| img_462_pert_5.1 | determinant | incorrect | — |
| img_471_pert_5.1 | determinant | correct | — |
| img_471_pert_5.2 | determinant | correct | — |
| img_494_pert_5.2 | equation | correct | assisted context unavailable: answer equality does not isolate the task variable |
| img_509_pert_5.1 | function_operation | correct | — |
| img_554_pert_5.1 | equation | indeterminate | assisted context unavailable: requires exactly one exact parsed given |
