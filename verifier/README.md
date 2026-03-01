# Standalone Schema Verifier

`verifier/` is self-contained and independent from the repo’s main `tests/` suite.

## Install

From repo root:

```bash
cd verifier
../venv/bin/pip install -e .
```

Or from inside `verifier/`:

```bash
../venv/bin/pip install -e .
```

## Run Standalone Verifier Tests

From inside `verifier/`:

```bash
../venv/bin/pytest
```

Only contract tests:

```bash
../venv/bin/pytest -m contract
```

Only parity tests:

```bash
../venv/bin/pytest -m parity
```

Increase Schemathesis coverage:

```bash
SAFRS_CONTRACT_MAX_EXAMPLES=25 \
SAFRS_CONTRACT_PHASES=examples,fuzzing \
../venv/bin/pytest -m contract
```

Keep artifacts:

```bash
SAFRS_VERIFY_KEEP_ARTIFACTS=1 ../venv/bin/pytest -m contract
```

## Run Verifier Directly (Flask/FastAPI)

From inside `verifier/`:

```bash
../venv/bin/python verify_flask.py
../venv/bin/python verify_fastapi.py
```

These commands:

- start the selected demo app
- discover runtime schema automatically (`/openapi.json` or `/api/swagger.json`)
- patch schema from `/seed`
- run Schemathesis with JSON:API headers

## Artifacts

Artifacts are written to:

```text
verifier/.artifacts/<run_id>/
```

They include runtime schema, patched schema, Schemathesis output, app logs, and run metadata.

Default behavior: keep artifacts only on failure.  
Set `SAFRS_VERIFY_KEEP_ARTIFACTS=1` to always keep them.

## Environment Variables

Harness options:

- `SAFRS_CONTRACT_MAX_EXAMPLES` (default `5`)
- `SAFRS_CONTRACT_PHASES` (default `examples`)
- `SAFRS_CONTRACT_REQUEST_TIMEOUT` (default `10`)
- `SAFRS_VERIFY_APP_LOG_LINES` (default `200`)
- `SAFRS_VERIFY_KEEP_ARTIFACTS` (default `0`)

Demo app options (set by harness automatically):

- `SAFRS_EXAMPLE_DB_PATH` (SQLite path per run)
- `SAFRS_EXAMPLE_RESET_DB` (default `1`)
