FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY pyproject.toml ./
COPY nirs_cas/ ./nirs_cas/
COPY nirs_llm/ ./nirs_llm/
COPY evaluator/ ./evaluator/
COPY data_contracts/ ./data_contracts/
RUN python -m pip install --no-cache-dir . \
    && groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --create-home app \
    && mkdir -p /reports \
    && chown app:app /reports
COPY data/synthetic_20.json /data/synthetic_20.json

FROM base AS test
RUN python -m pip install --no-cache-dir '.[test]'
COPY tests/ ./tests/
# Tests resolve the fixture relative to the project root.
COPY data/synthetic_20.json ./data/synthetic_20.json
COPY dataset/test_gt.json dataset/final_gt.json ./dataset/
COPY dataset_scripts/selected.json ./dataset_scripts/selected.json
COPY prompts/ ./prompts/
USER app
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]

FROM base AS runtime
USER app
ENTRYPOINT ["python", "-m", "nirs_cas"]
CMD ["--help"]
