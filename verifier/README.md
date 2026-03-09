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

This runs a strict default profile (`max_examples=25`, `phases=examples,fuzzing`), so expect longer runtime and possible real contract failures.

Select specific contract targets:

```bash
SAFRS_CONTRACT_TARGETS=flask,fastapi ../venv/bin/pytest -m contract
SAFRS_CONTRACT_TARGETS=nw-flask,nw-fastapi ../venv/bin/pytest -m contract
```

Only parity tests:

```bash
../venv/bin/pytest -m parity
```

JSON response parity (Flask vs FastAPI):

```bash
../venv/bin/pytest -q tests/test_response_parity.py
```

Default parity matrix now covers:
- collection pagination (`page[offset]/page[limit]` and `page[number]/page[size]`)
- multi-sort (`sort=...`)
- bracket CSV filters (`filter[Field]=a,b`)
- sparse fieldsets
- include-heavy instance / relationship fetches
- representative error cases (status + error-code parity)

Override target pair and request list:

```bash
SAFRS_PARITY_TARGETS=nw-flask,nw-fastapi \
SAFRS_PARITY_REQUESTS='/api/Order?page[offset]=0&page[limit]=1&include=Customer,Employee' \
../venv/bin/pytest -q tests/test_response_parity.py
```

For multiple requests, use JSON-array format (recommended):

```bash
SAFRS_PARITY_REQUESTS='["/api/Order?page[offset]=0&page[limit]=1&include=Customer,Employee","/api/Customer?page[offset]=0&page[limit]=1"]' \
../venv/bin/pytest -q tests/test_response_parity.py
```

Request objects are also supported for non-GET parity checks:

```bash
SAFRS_PARITY_REQUESTS='[{"method":"PATCH","path":"/api/Order/{seed:OrderId}/OrderDetailList","body":{}}]' \
../venv/bin/pytest -q tests/test_response_parity.py
```

Seed placeholders use the left target `/seed` payload (for example `{seed:OrderId}`).

Increase Schemathesis coverage:

```bash
SAFRS_CONTRACT_MAX_EXAMPLES=100 \
SAFRS_CONTRACT_PHASES=examples,fuzzing \
../venv/bin/pytest -m contract
```

Keep artifacts:

```bash
../venv/bin/pytest -m contract
```

## Run Verifier Directly (Flask/FastAPI)

From inside `verifier/`:

```bash
../venv/bin/python verify_flask.py
../venv/bin/python verify_fastapi.py
../venv/bin/python verify_nw_flask.py
../venv/bin/python verify_nw_fastapi.py
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
They also include `stats.json` with per-operation status-code histograms.

Default behavior: keep artifacts for all runs (`SAFRS_VERIFY_KEEP_ARTIFACTS=1`).
To only keep artifacts on failure, set `SAFRS_VERIFY_KEEP_ARTIFACTS=0`.

## Environment Variables

Harness options:

- `SAFRS_CONTRACT_MAX_EXAMPLES` (default `25`)
- `SAFRS_CONTRACT_PHASES` (default `examples,fuzzing`)
- `SAFRS_CONTRACT_REQUEST_TIMEOUT` (default `10`)
- `SAFRS_CONTRACT_SUPPRESS_HEALTH_CHECK` (default `filter_too_much`)
- `SAFRS_CONTRACT_DATA_GENERATION_MODE` (default `positive`)
- `SAFRS_VERIFY_APP_LOG_LINES` (default `200`)
- `SAFRS_VERIFY_KEEP_ARTIFACTS` (default `1`)
- `SAFRS_CONTRACT_TARGETS` (default all: `flask,fastapi,nw-flask,nw-fastapi`)
- `LOGLEVEL` (optional integer Python log level; takes precedence over `DEBUG` / `FLASK_DEBUG`)

Demo app options (set by harness automatically):

- `SAFRS_EXAMPLE_DB_PATH` (SQLite path per run)
- `SAFRS_EXAMPLE_RESET_DB` (default `1`)
- `DEBUG=1` (always forced by verifier runner)
- `FLASK_DEBUG=1` (always forced by verifier runner)
- `SAFRS_DISABLE_RELOAD=1` (forced by verifier runner to keep subprocess lifecycle stable)

NW app options:

- `SAFRS_NW_DB_SOURCE` (default `nw-db.sqlite`)
- `SAFRS_NW_DB_PATH` (working copy path; default `apps/nw_<framework>_<port>.sqlite`)
- `SAFRS_NW_RESET_DB` (default `1`, copies source DB into working DB each run)

## Troubleshooting

If you see `PermissionError(1, 'Operation not permitted')` when verifier tests start apps,
your environment is blocking local loopback sockets (`127.0.0.1` bind).

Quick check:

```bash
../venv/bin/python -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', 0)); print('ok', s.getsockname()); s.close()"
```

If that command fails, run verifier tests in an environment that allows local TCP bind:

- local shell (not restricted sandbox)
- CI/container without socket-restricting security profile
- VM/dev container with loopback networking enabled
