#!/usr/bin/env sh

# Migrate database
export PYTHONPATH=:/app/safrs:/app/src/safrs:${PYTHONPATH}
flask db migrate
flask db upgrade


if [ $FLASK_ENV = "development" ]; then
    ## Skip the workers when in develop mode
    exec gunicorn \
        --bind :80 \
        --access-logfile - \
        --graceful-timeout 2 \
        --timeout 10 \
        --reload \
        "app:run_app()"
else
    exec gunicorn \
        --bind :80 \
        --access-logfile - \
        --graceful-timeout 10 \
        --timeout 120 \
        --workers 4 \
        "app:run_app()"
fi
