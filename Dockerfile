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
    git \
    && pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -r requirements.txt

# Use CMD instead of ENTRYPOINT to allow easier run of other commands (like "sh")
# Also Pycharm can only handle CMD overrides
CMD ["/app/entrypoint.sh"]
