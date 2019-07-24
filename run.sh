#!/usr/bin/env bash
up="docker-compose up"
down="docker-compose down"
build="docker-compose build"
exec="docker-compose exec safrs"
flask="$exec flask"
shell="$exec sh"
test="docker-compose run --rm -e CONFIG_MODULE=config/test.py safrs pytest --cov"
logs="docker-compose logs -f --tail 40"
db="docker-compose -p safrs_db -f docker-compose.db.yml"
db_shell="$db exec psql psql -U postgres"

set -x
${!1} ${@:2}
