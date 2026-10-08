# Gemini dev-20: ordinary OCR→CAS vs assisted context→TaskSpec→CAS

| Режим | Verified solution coverage | Indeterminate | Verdict accuracy | First-error accuracy |
|---|---:|---:|---:|---:|
| ordinary | 55% | 45% | 50% | 60% |
| assisted | 60% | 40% | 50% | 50% |

Task-aware coverage assisted: 65% (10 exact-valid, 3 exact-invalid, 7 unsupported).
Ordinary coverage строится только из линейной проверки записанных шагов. Assisted coverage дополнительно использует exact graph-rules для независимых answer-ветвей; unsupported context не ухудшает уже установленный локальный verdict.
Метрики использованы только для FERMAT dev-20. Mixed-20 служит инженерным набором покрытия и в таблицу не включён.
