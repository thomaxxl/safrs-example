# FastAPI + SAFRS App (Local Models)

This directory contains a FastAPI SAFRS app similar to `safrs/tmp/fastapi_app.py`,
with a cleaned `models.py` placed in this same directory.

## Run

```bash
venv/bin/python fastapi_safrs_from_models/app.py
```

Then open:

- `http://127.0.0.1:5656/health`
- `http://127.0.0.1:5656/docs`
- `http://127.0.0.1:5656/api`

## Environment Variables

- DB path is hardcoded to `fastapi_safrs_from_models/db.sqlite`
- `SAFRS_RESET_DB` (set to `1`/`true`/`yes` to delete the DB file before startup)

## Notes

- The app adds `safrs/` in this workspace to `sys.path` so `import safrs` resolves
  to the package in the nested repository.
- The local `models.py` was cleaned from `/tmp/models.py` as a reference, with
  external Flask-specific base dependencies removed.
