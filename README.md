# Log Anomaly Detection

Detect anomalies in system logs by parsing raw logs into templates and applying machine-learning models.

## Project structure

```
data/
  raw/          # Original log files (not tracked by git)
  processed/    # Parsed / feature-engineered data
notebooks/      # Exploratory Jupyter notebooks
src/
  parsing/      # Log parsing (e.g. Drain3 template mining)
  models/       # Anomaly detection models
  evaluation/   # Metrics and evaluation
  streaming/    # Real-time / streaming detection
dashboard/      # Visualization dashboard
docker/         # Container configuration
docs/           # Documentation
```

## Setup

Requires Python 3.12.

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Streaming pipeline and dashboard

Logs go into a Redis Stream, the detection service (`src/streaming`) parses them with our Drain setup, cuts them
into the same windows as in training (HDFS blocks, BGL 20-line windows, 1-minute windows for the Docker services),
scores every closed window and sends alerts to the dashboard over server-sent events.

```
replay script (HDFS/BGL test sets) ─┐
                                    ├─> Redis Stream "logs" ─> detection service (FastAPI, :8000) ─> dashboard (:3000)
live collector (Docker services) ───┘
```

Two alert levels: **Alert** when a model flags the window, **New template** when the only reason is an event never
seen in normal training (reported once per new template). Each alert records the time of the last log line in the
window and the time the alert was produced.

### 1. One-time: build the model packs

```bash
source venv/bin/activate
python -m src.streaming.packs replay          # HDFS + BGL: PCA, Isolation Forest, Random Forest, LSTM (~10 min)
```

For live mode, collect normal logs from the Docker services first (docker/README.md, steps 1-3: start, generate
normal traffic, `python scripts/collect_logs.py`), then:

```bash
python -m src.streaming.packs live            # one pack per service: PCA, Isolation Forest, LSTM
```

Random Forest is replay-only, because it needs labels. A service with fewer than 5 normal 1-minute windows gets no
models, only New-template warnings.

### 2. Start everything (one terminal each)

```bash
cd docker && docker compose up -d --build --wait               # services + Redis
uvicorn src.streaming.service:app --port 8000                  # detection service (project root, venv active)
cd dashboard && npm run dev                                    # dashboard on http://localhost:3000
```

Then feed it, either or both:

```bash
python -m src.streaming.collector                              # live: new lines from nginx, app, postgres, ssh
python -m src.streaming.replay hdfs --rate 500                 # replay the HDFS test set, 500 lines/s
python -m src.streaming.replay bgl --rate 2000 --limit 200000  # replay part of the BGL test set
```

HDFS blocks are scored when no line for them has arrived for 4 hours of log time (no test block has a longer gap,
so the block sequences equal the offline ones) or when the replay ends. Settings (environment variables of the
detection service): `REDIS_URL`, `HDFS_IDLE_SECONDS`, `STREAM_START=0` to also read lines already in the stream,
`DEDUPE_NEW_TEMPLATES=0` for a New-template warning on every window. The dashboard reads
`NEXT_PUBLIC_DETECTOR_URL` (default `http://localhost:8000`).
