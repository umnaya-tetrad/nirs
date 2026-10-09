# Assisted-CAS: mixed-20 engineering coverage

| ID | Task class | Verdict | Fallback reason |
|---|---|---|---|
| hf-task13-13-1-1-maximal | trigonometric | indeterminate | At least one node/edge proof is unresolved; Unbalanced delimiters; Bare word is not an exact mathematical token; Unsupported input at character 20; Unsupported input at character 20; Unsupported input at character 20; Prose/conditions are not a fully parsed mathematical step; Prose/conditions are not a fully parsed mathematical step; Prose is not a mathematical answer |
| hf-task13-13-1-3-non-maximal | trigonometric | indeterminate | At least one node/edge proof is unresolved; Expected one expression; Expected one expression; Prose/conditions are not a fully parsed mathematical step; At least one node/edge proof is unresolved; At least one node/edge proof is unresolved; At least one node/edge proof is unresolved; Unconsumed token '='; one expression/equation per step |
| hf-task13-13-1-4-non-maximal | trigonometric | indeterminate | At least one node/edge proof is unresolved; Unbalanced delimiters; Bare word is not an exact mathematical token; At least one node/edge proof is unresolved; At least one node/edge proof is unresolved |
| hf-task13-13-2-1-maximal | trigonometric | indeterminate | At least one node/edge proof is unresolved; At least one node/edge proof is unresolved; At least one node/edge proof is unresolved; At least one node/edge proof is unresolved; At least one node/edge proof is unresolved; At least one node/edge proof is unresolved; Bare word is not an exact mathematical token; Unsupported input at character 15; At least one node/edge proof is unresolved; At least one node/edge proof is unresolved; At least one node/edge proof is unresolved; expected string or bytes-like object, got 'NoneType'; At least one node/edge proof is unresolved |
| hf-task13-13-2-2-maximal | trigonometric | indeterminate | At least one node/edge proof is unresolved; At least one node/edge proof is unresolved; At least one node/edge proof is unresolved; Expected one expression; Bare word is not an exact mathematical token; Expected one expression; Unsupported input at character 15; At least one node/edge proof is unresolved; expected string or bytes-like object, got 'NoneType' |
| hf-task13-13-2-3-non-maximal | trigonometric | indeterminate | At least one node/edge proof is unresolved; At least one node/edge proof is unresolved; At least one node/edge proof is unresolved; At least one node/edge proof is unresolved; At least one node/edge proof is unresolved; Unbalanced delimiters; Unsupported input at character 21; Prose/conditions are not a fully parsed mathematical step; At least one node/edge proof is unresolved; At least one node/edge proof is unresolved |
| hf-task13-13-4-3-zero | trigonometric | incorrect | Prose/conditions are not a fully parsed mathematical step; At least one node/edge proof is unresolved; At least one node/edge proof is unresolved; At least one node/edge proof is unresolved; At least one node/edge proof is unresolved; Unsupported input at character 18; Unsupported input at character 27; Unsupported input at character 6; Prose/conditions are not a fully parsed mathematical step; Prose is not a mathematical answer |
| hf-task15-15-1-2-non-maximal | inequality | indeterminate | Prose/conditions are not a fully parsed mathematical step; Unsupported token '\\backslash'; At least one node/edge proof is unresolved; Unsupported input at character 12; Requires one explicit inequality; Requires one explicit inequality; Unsupported input at character 2 |
| hf-task15-15-2-1-maximal | inequality | indeterminate | Unsupported input at character 10; Nonlinear logarithmic inequality; Nonlinear logarithmic inequality; At least one node/edge proof is unresolved; Requires one explicit inequality; Unconsumed token '|'; one expression/equation per step; At least one node/edge proof is unresolved; Unconsumed token '|'; one expression/equation per step; At least one node/edge proof is unresolved; Requires one explicit inequality; At least one node/edge proof is unresolved; At least one node/edge proof is unresolved; Requires one explicit inequality; Unsupported input at character 2 |
| hf-task15-15-2-2-maximal | inequality | indeterminate | Unbalanced delimiters; Prose/conditions are not a fully parsed mathematical step; At least one node/edge proof is unresolved; Unconsumed token ')'; one expression/equation per step; At least one node/edge proof is unresolved; Prose/conditions are not a fully parsed mathematical step; Prose/conditions are not a fully parsed mathematical step; Unconsumed token '|'; one expression/equation per step; At least one node/edge proof is unresolved; Unconsumed token '|'; one expression/equation per step; At least one node/edge proof is unresolved; Prose/conditions are not a fully parsed mathematical step; At least one node/edge proof is unresolved; Prose/conditions are not a fully parsed mathematical step; At least one node/edge proof is unresolved; Requires one explicit inequality; Requires one explicit inequality; Unsupported input at character 2; Unsupported input at character 2 |
| img_151_pert_5.3 | expression | correct | Task has no explicit mathematical target |
| img_221_pert_5.3 | expression | indeterminate | Unsupported input at character 0; Prose/conditions are not a fully parsed mathematical step; Prose/conditions are not a fully parsed mathematical step; Task has no explicit mathematical target |
| img_373_pert_5.2 | definite_integral | indeterminate | Prose/conditions are not a fully parsed mathematical step; Unsupported token '\\int'; Unsupported token '\\int'; Continuation requires one readable dependency |
| img_452_pert_5.2 | matrix_system | correct | — |
| img_462_pert_5.1 | determinant | indeterminate | Symbolic determinant template has no explicit entry bindings; Continuation requires one readable dependency |
| img_471_pert_5.1 | determinant | correct | — |
| img_471_pert_5.2 | determinant | correct | — |
| img_494_pert_5.2 | equation | correct | — |
| img_509_pert_5.1 | function_operation | correct | — |
| img_554_pert_5.1 | equation | indeterminate | Prose/conditions are not a fully parsed mathematical step; At least one node/edge proof is unresolved; Prose/conditions are not a fully parsed mathematical step; Task has no explicit mathematical target |

| Task class | Examples | Verified solution coverage | Task-aware coverage |
|---|---:|---:|---:|
| definite_integral | 1 | 0% | 100% |
| determinant | 3 | 67% | 100% |
| equation | 2 | 50% | 50% |
| expression | 2 | 50% | 0% |
| function_operation | 1 | 100% | 100% |
| inequality | 3 | 0% | 100% |
| matrix_system | 1 | 100% | 100% |
| trigonometric | 7 | 0% | 57% |
