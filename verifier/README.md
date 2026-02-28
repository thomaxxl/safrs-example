# Standalone Verifier

This directory is self-contained and does **not** use the main `tests/` tree.

## Setup

From repo root:

```bash
cd /home/t/lab/safrs-example
source venv/bin/activate
pip install -r requirements.txt
```

## Run Verifier Tests (standalone)

```bash
cd /home/t/lab/safrs-example/verifier
pytest -q
```

Optional environment controls:

- `SAFRS_CONTRACT_MAX_EXAMPLES` (default: `5`)
- `SAFRS_CONTRACT_PHASES` (default: `examples,fuzzing`)

## Run Verifier Directly (as before)

From inside `verifier/`:

```bash
python verify_flask.py
python verify_fastapi.py
```

Both commands use runtime spec discovery (`/openapi.json` or `/api/swagger.json`) and SQLite.
