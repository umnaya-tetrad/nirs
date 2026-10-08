# Gemini dev-20: ordinary OCR→CAS vs assisted context→TaskSpec→CAS

| Режим | Local step coverage | Indeterminate | Verdict accuracy | First-error accuracy |
|---|---:|---:|---:|---:|
| ordinary | 55% | 45% | 50% | 60% |
| assisted | 55% | 45% | 45% | 50% |

Task-aware coverage assisted: 30% (6 exact-valid, 0 exact-invalid, 14 unsupported).
Local step coverage сопоставима между ordinary и assisted. Task-aware coverage — отдельная, более строгая метрика assisted; она не ухудшает локальный verdict.
Метрики использованы только для FERMAT dev-20. Mixed-20 служит инженерным набором покрытия и в таблицу не включён.
