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

Only parity tests:

```bash
../venv/bin/pytest -m parity
```

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

Default behavior: keep artifacts for all runs (`SAFRS_VERIFY_KEEP_ARTIFACTS=1`).
To only keep artifacts on failure, set `SAFRS_VERIFY_KEEP_ARTIFACTS=0`.

## Environment Variables

Harness options:

- `SAFRS_CONTRACT_MAX_EXAMPLES` (default `25`)
- `SAFRS_CONTRACT_PHASES` (default `examples,fuzzing`)
- `SAFRS_CONTRACT_REQUEST_TIMEOUT` (default `10`)
- `SAFRS_VERIFY_APP_LOG_LINES` (default `200`)
- `SAFRS_VERIFY_KEEP_ARTIFACTS` (default `1`)

Demo app options (set by harness automatically):

- `SAFRS_EXAMPLE_DB_PATH` (SQLite path per run)
- `SAFRS_EXAMPLE_RESET_DB` (default `1`)
- `DEBUG=1` (always forced by verifier runner)
- `FLASK_DEBUG=1` (always forced by verifier runner)

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
