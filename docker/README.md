# Docker test environment

`docker-compose.yml` runs a small web app with an SSH server next to it, to produce real logs for the project.

| Service | What it is | Host port |
|---|---|---|
| `nginx` | Reverse proxy: `/` is the nginx home page, `/api/` goes to the app | http://localhost:8080 |
| `app` | Node.js (Express) app: `GET /` health check, `GET /items`, `POST /items` | only through nginx |
| `postgres` | Database for the app, data kept in the `pgdata` volume | `localhost:5433` |
| `ssh` | OpenSSH server with one test user | `127.0.0.1:2222` (this machine only) |

Test logins (local use only): database `loguser` / `logpass`, SSH `testuser` / `testpass`. To change them, set `POSTGRES_USER`, `POSTGRES_PASSWORD`, `SSH_USER` and `SSH_PASSWORD` in a `docker/.env` file before the first start.

Run the commands from this `docker/` folder, with the project venv active (`source ../venv/bin/activate`).

## 1. Start

```bash
docker compose up -d --build --wait
docker compose ps        # nginx, app, postgres and ssh should be running
curl http://localhost:8080/api/items
```

## 2. Generate normal traffic

Run these two in separate terminals at the same time. Both take 10 minutes.

```bash
locust -f locust/locustfile.py --headless -u 20 -r 2 -t 10m --host http://localhost:8080
python ../scripts/ssh_normal_activity.py --minutes 10 --logins 6
```

Locust runs 20 users who mostly read `/api/items`, sometimes add an item and now and then open the home page, waiting 2-8 s between actions. The SSH script logs in 6 times at random moments and runs a couple of ordinary commands each time.

## 3. Collect logs

```bash
python ../scripts/collect_logs.py
```

This saves each service's logs to `data/raw/live/<service>_normal.log` and prints the number of lines per service. Collect before `docker compose down`, because removing the containers also removes their logs.

## 4. Stop

```bash
docker compose stop      # stop the containers, keep them and their logs
docker compose down      # remove the containers (and their logs), keep the database
docker compose down -v   # also delete the database data
```

To look at logs directly: `docker compose logs app`, `docker compose logs -f ssh` (follow live), `docker compose logs --tail 10 nginx`.
