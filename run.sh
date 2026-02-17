#!/usr/bin/env bash
up="docker-compose up"
down="docker-compose down"
build="docker-compose build --no-cache "
exec="docker-compose exec safrs"
flask="$exec flask"
shell="$exec sh"
dbg_shell="docker-compose run  --entrypoint sh safrs"
test="sudo docker-compose -f docker-compose.yml run --rm -e CONFIG_MODULE=config/test.py safrs pytest --cov=safrs --cov-report term-missing"
logs="docker-compose logs -f --tail 40"
db="docker-compose -p safrs_db -f docker-compose.db.yml"
db_shell="$db exec psql psql -U postgres"
db_mysql="$db exec mysql mysql -p"

set -x
${!1} ${@:2}
