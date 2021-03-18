FROM python:3.7-alpine
WORKDIR /app
ENV PYTHONPATH /app
COPY . .

# psycopg2 needs build tools
RUN apk add --no-cache \
    gcc \
    python3-dev \
    musl-dev \
    postgresql-dev \
    g++ \
    git \
    && ln -sf  /usr/local/bin/python3.8  /usr/bin/python \
    && ln -sf  /usr/local/bin/python3.8  /usr/local/bin/python3 \
    && python3 -m ensurepip \
    && python3 -m pip install --no-cache-dir -U pip \
    && python3 -m pip install --no-cache-dir -r requirements.txt

# Use CMD instead of ENTRYPOINT to allow easier run of other commands (like "sh")
# Also Pycharm can only handle CMD overrides
CMD ["/app/entrypoint.sh"]
