#!/usr/bin/env sh

# Migrate database
flask db migrate
flask db upgrade
python3 -m pip install querystring-parser==1.2.4

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
