#!/usr/bin/env sh
set -eu

export PYTHONPATH="/workspace${PYTHONPATH:+:$PYTHONPATH}"

python -m app.bootstrap_db

exec gunicorn \
    --bind :80 \
    --access-logfile - \
    --graceful-timeout 10 \
    --timeout 120 \
    --workers 4 \
    "app:run_app()"
