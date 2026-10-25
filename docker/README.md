# Docker services

`docker-compose.yml` runs two services that produce real logs for the project:

| Service | Image | Host port | Notes |
|---|---|---|---|
| `nginx` | `nginx:1.27-alpine` | http://localhost:8080 | Access and error logs go to the container output |
| `postgres` | `postgres:16-alpine` | `localhost:5433` | Port 5433 on the host (not 5432), so it doesn't clash with another local Postgres. Data is kept in the `pgdata` volume |

Default database login: user `loguser`, password `logpass`, database `logs`. These are for local use only. To change them, set `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB` in your shell or in a `docker/.env` file **before the first start**, because Postgres only reads them when it creates the database.

Run all commands from this `docker/` folder.

## Start

```bash
docker compose up -d --wait
docker compose ps
```

`--wait` returns once both containers are running and Postgres reports healthy.

Check that they respond:

```bash
curl -I http://localhost:8080
docker compose exec postgres psql -U loguser -d logs -c "select version();"
```

## Stop

```bash
docker compose stop      # stop the containers, keep them and the data
docker compose down      # remove the containers, keep the database volume
docker compose down -v   # remove the containers AND delete the database data
```

## View logs

```bash
docker compose logs                      # all services
docker compose logs nginx                # one service
docker compose logs --tail 10 postgres   # last 10 lines
docker compose logs -f nginx             # follow new lines live (Ctrl+C to stop)
docker compose logs --no-log-prefix nginx > nginx.log   # save raw lines to a file
```

nginx writes one access-log line per request, for example:

```
172.20.0.1 - - [25/Oct/2026:21:36:09 +0000] "GET / HTTP/1.1" 200 615 "-" "curl/8.5.0" "-"
```

To generate some traffic:

```bash
for i in $(seq 1 20); do curl -s -o /dev/null http://localhost:8080/; done
```
