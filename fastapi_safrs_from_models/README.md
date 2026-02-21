# FastAPI + SAFRS App (External Models)

This directory contains a FastAPI SAFRS app similar to `safrs/tmp/fastapi_app.py`,
but it loads SQLAlchemy/SAFRS models from `/tmp/models.py`.

## Run

```bash
venv/bin/python fastapi_safrs_from_models/app.py
```

Then open:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/api`

## Environment Variables

- `SAFRS_MODELS_FILE` (default: `/tmp/models.py`)
- `SAFRS_MODELS_PROJECT_ROOT` (default: `/home/t/lab/ALS/ApiLogicProject`)
- `SAFRS_SQLITE_PATH` (default: `database/db.sqlite` relative to project root)
- `SAFRS_API_PREFIX` (default: `/api`)
- `HOST` (default: `127.0.0.1`)
- `PORT` (default: `8000`)

## Notes

- The app adds `safrs/` in this workspace to `sys.path` so `import safrs` resolves
  to the package in the nested repository.
- Minimal compatibility shims are provided for `flask_login` and `flask_sqlalchemy`
  if they are not installed, because `/tmp/models.py` imports them.
