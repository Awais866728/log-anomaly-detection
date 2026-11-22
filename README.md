# Log Anomaly Detection

Finding problems in system logs automatically: a study of four detection methods on four public log datasets,
and a working real-time system that watches the logs of a small web application and raises explained alerts on a
live dashboard.

Logs are the first place engineers look when something breaks, but a busy system writes thousands of lines per
minute. This project turns raw log lines into structured events, groups them into windows, and uses statistical,
machine-learning and deep-learning models to flag the windows that don't look normal. It then explains each alert
by showing the log events behind it.

**What's in this repository**

- **Offline study:** log parsing with Drain3, and PCA, Isolation Forest, Random Forest and an LSTM (DeepLog)
  compared on HDFS, BGL, OpenSSH and Apache logs. Every threshold is chosen on a separate validation split, never
  on the test data. 17 notebooks show every step.
- **Real-time pipeline:** a Redis stream, a FastAPI detection service that parses, windows, scores and explains
  logs as they arrive, and a Next.js dashboard that updates live.
- **Test environment:** Docker services (nginx, a Node.js app, PostgreSQL, an SSH server) that produce real logs,
  plus scripts that generate normal traffic and inject faults.
- **Fault-injection experiment:** database failures, traffic overloads and SSH password guessing, each injected
  5 times. All 15 faults were detected, about one minute after they started.

---

## Contents

- [How it works](#how-it-works)
- [Datasets](#datasets)
- [Methods](#methods)
- [Results](#results)
- [Repository structure](#repository-structure)
- [Getting started](#getting-started)
- [Reproducing the offline study](#reproducing-the-offline-study)
- [Running the real-time system](#running-the-real-time-system)
- [Fault-injection experiment](#fault-injection-experiment)
- [Limitations](#limitations)
- [References](#references)

---

## How it works

```
 raw log line ──> parsing (Drain3) ──> event id ──> window ──> count vector / event sequence ──> models ──> alert + explanation

   "Received block blk_-160 of size 67108864 from /10.250.19.102"
        └─> template "Received block <BLK> of size <NUM> from <IP>"  =  event E5
```

1. **Parsing:** each line is matched to a *template* (the constant part of the message, with variables like IPs,
   block ids and numbers masked) using the Drain algorithm. Every template gets an event id.
2. **Windowing:** events are grouped into windows: one window per HDFS block, 20 lines for BGL and Apache, and
   1 minute for OpenSSH and the live services.
3. **Detection:** each window is scored by four models (see [Methods](#methods)). PCA, Isolation Forest and the
   LSTM learn what *normal* looks like and flag deviations. Random Forest learns from labelled examples.
4. **Explanation:** each alert lists the log events behind it: SHAP values for Random Forest, and the events
   whose counts differ most from normal for the other models. Events that are expected but missing, and events
   never seen in training, are marked as such.

The same code runs offline (in the notebooks) and in real time (in the detection service). The real-time
pipeline is checked to produce the same windows as the offline one.

```
 replay script (test sets of the 4 datasets) ──┐
                                               ├──> Redis Stream ──> detection service (FastAPI) ──> dashboard (Next.js)
 live collector (Docker services) ─────────────┘                      parse · window · score · explain      live over SSE
```

---

## Datasets

Four public datasets from [Loghub](https://github.com/logpai/loghub), plus logs from our own Docker environment.

| Dataset | System | Lines | Windows | Templates | Labels |
|---|---|---:|---:|---:|---|
| **HDFS** | Hadoop distributed file system | 11.2 M | 575,061 blocks | 45 | per block, 2.9% anomalous |
| **BGL** | Blue Gene/L supercomputer | 4.7 M | 237,398 × 20 lines | 391 | per line, 8.5% of windows anomalous |
| **OpenSSH** | SSH server under attack | 655 k | 13,486 × 1 minute | 51 | none |
| **Apache** | Apache web server error log | 56 k | 2,824 × 20 lines | 30 | none |
| **Live** | our nginx, app, PostgreSQL and SSH containers | collected | 1 minute | per service | faults injected on purpose |

HDFS and BGL have anomaly labels, so precision, recall and F1 can be measured on them. OpenSSH and Apache have
no labels. For those, we report how many windows each model flags and inspect the top-flagged windows by hand.

---

## Methods

| Model | Type | Idea | Trained on |
|---|---|---|---|
| **PCA** | statistical | normal windows lie close to a low-dimensional subspace; a large reconstruction error is anomalous (Xu et al. 2009) | normal windows |
| **Isolation Forest** | unsupervised ML | anomalies are isolated by fewer random splits | normal windows |
| **Random Forest** | supervised ML | classifier on window event counts, class-balanced | labelled windows |
| **LSTM (DeepLog)** | deep learning | predicts the next event from the previous 10; a window is anomalous if a real event is outside the top-k predictions (Du et al. 2017) | normal sequences |

**Evaluation protocol.** Data is split in **time order**, never shuffled: fit on the first 60%, choose settings
(PCA / Isolation Forest percentile, LSTM k, Random Forest balancing method) on the next 10%, and report on the last
30%. Settings are never tuned on the test set. A **hybrid** model, Random Forest plus a rule that flags windows
containing a template never seen in training, is also evaluated.

**Parsing quality.** Drain3 templates were checked against Loghub's ground-truth templates on the 2k-line samples.
Grouping accuracy: HDFS 99.75%, BGL 96.85%, OpenSSH 92.5%, Apache 100%.

---

## Results

### HDFS and BGL (test set, settings chosen on validation)

| Model | HDFS precision | HDFS recall | HDFS F1 | BGL precision | BGL recall | BGL F1 |
|---|---:|---:|---:|---:|---:|---:|
| PCA | 0.860 | 0.817 | 0.838 | 0.095 | 0.980 | 0.173 |
| Isolation Forest | 0.787 | 0.511 | 0.620 | 0.096 | 0.991 | 0.175 |
| Random Forest | **1.000** | **0.997** | **0.9985** | 0.955 | 0.072 | 0.134 |
| LSTM (DeepLog) | 0.802 | 0.430 | 0.560 | 0.097 | 0.993 | 0.177 |
| Hybrid (RF + unseen-template rule) | 1.000 | 0.998 | **0.9988** | 0.086 | 0.840 | 0.156 |

**What this shows**

- **HDFS is close to solved** with labels: Random Forest makes almost no mistakes. Among the methods that need
  no labels, PCA is best (F1 0.84).
- **BGL is much harder.** Its normal behaviour changes over time, so windows from the test period look unusual
  to every model trained on the earlier period. The models that need no labels catch nearly every anomaly
  (recall above 0.98), but they also flag about 75% of normal windows. Random Forest does the opposite: very few
  false alarms, but it misses most anomalies.
- **Settings transfer well between HDFS and BGL:** using the percentile or k chosen on the other dataset changes
  F1 by at most 0.013 (`docs/cross_system_transfer.csv`). The big differences come from the data, not the
  settings.

### OpenSSH and Apache (no labels: share of test windows flagged)

| Model | OpenSSH | Apache |
|---|---:|---:|
| PCA (percentile 99) | 1.4% | 1.2% |
| Isolation Forest (percentile 99.5) | 2.1% | 0.2% |
| LSTM (k = 12) | 4.3% | 0.6% |

These use the settings chosen on BGL. The top-flagged OpenSSH windows are bursts of invalid-user login attempts
and repeated authentication failures, often with a disconnect message never seen in training. That matches what
an operator would want to see.

### Real-time system

| Fault (5 runs each) | Detected | Median latency | Min – max | Models that fired |
|---|---:|---:|---:|---|
| Database failure (PostgreSQL stopped for 60 s) | 5/5 | 60 s | 55 – 60 s | PCA, Isolation Forest (app, nginx, postgres) |
| Traffic overload (+300 users for 60 s) | 5/5 | 57 s | 55 – 59 s | PCA |
| SSH password guessing (30 failed logins in 60 s) | 5/5 | 58 s | 56 – 64 s | Isolation Forest (PCA once) |

- **False alerts:** 1 in about 1 hour of normal traffic.
- **Where the latency comes from:** almost all of it is waiting for the 1-minute window to close. Scoring
  itself takes milliseconds.

Processing time per window in the detection service (one window at a time; HDFS / BGL):

| Step | HDFS | BGL |
|---|---:|---:|
| Drain parsing, per line | 0.02 ms | 0.02 ms |
| PCA | 0.29 ms | 0.32 ms |
| Isolation Forest | 7.5 ms | 7.6 ms |
| Random Forest | 7.9 ms | 10.0 ms |
| LSTM | 0.8 ms | 0.9 ms |

When many windows close at once and are scored in batches of 500, every model except the LSTM takes under
0.1 ms per window. A SHAP explanation of a Random Forest alert takes 28–66 ms.

All result tables are in [`docs/`](docs) as CSV files.

---

## Repository structure

```
src/
  parsing/       Drain3 setup: per-dataset log formats, masking rules, similarity thresholds
  features/      windows and event-count features (HDFS blocks, BGL / Apache line windows, time windows)
  models/        PCA, Isolation Forest, Random Forest (+ SHAP explanations), DeepLog LSTM
  evaluation/    metrics, cross-system comparison, fault-injection analysis
  streaming/     real-time pipeline: Redis replay and collector, model packs, detection service, benchmark
notebooks/       01–17: exploration, parsing, every model on every dataset, real-time experiment
dashboard/       Next.js dashboard (overview, live logs, alerts with explanations, services, models)
docker/          test environment: nginx, Node.js app, PostgreSQL, OpenSSH, Redis; Locust traffic
scripts/         log collection, normal SSH activity, fault injection
docs/            result tables (CSV) and figures
tests/           unit tests (pytest)
data/            raw/ (datasets, not in git) and processed/ (features, built by the notebooks)
models/          trained models and model packs (built locally, not in git)
```

---

## Getting started

### Requirements

- Python 3.12
- Node.js 20 or newer (for the dashboard)
- Docker with Docker Compose (for the live services and Redis)
- A GPU isn't needed: PyTorch is installed as CPU-only. The full HDFS dataset (11 M lines) needs several GB of RAM.

### Install

```bash
git clone <this repository>
cd log-anomaly-detection
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cd dashboard && npm install && cd ..
```

### Get the data

Download the datasets from [Loghub](https://github.com/logpai/loghub) (the full versions are on Zenodo, linked
from the Loghub page) and place them like this:

```
data/raw/HDFS/HDFS.log
data/raw/HDFS/preprocessed/anomaly_label.csv
data/raw/BGL/BGL.log
data/raw/OpenSSH/SSH.log
data/raw/Apache/Apache.log
```

The small `*_2k.log` samples with their `*_structured.csv` files (also from Loghub) are used by the first notebooks
for exploration and for checking parsing accuracy.

---

## Reproducing the offline study

Run the notebooks in order. Each one starts with a short description of what it does and saves its results to
`docs/`.

| Notebooks | What they do |
|---|---|
| 01–04 | explore the 2k samples, check parsing accuracy, first baselines |
| 05, 09, 13 | parse the full HDFS, BGL, OpenSSH and Apache logs into windows (`data/processed/`) |
| 06–08 | HDFS: PCA and Isolation Forest, Random Forest, LSTM |
| 10–12 | BGL: the same models, plus an improved LSTM |
| 14–16 | validation-based settings for every model, the hybrid model, the cross-system comparison |
| 17 | fault injection and processing time of the real-time system |

```bash
source venv/bin/activate
jupyter lab notebooks/
pytest                 # unit tests
```

---

## Running the real-time system

### 1. Build the model packs (one time)

A *model pack* holds everything the detection service needs for one source: the Drain parser state, the fitted
models with their thresholds, and the normal event counts used for explanations.

```bash
python -m src.streaming.packs replay                              # HDFS + BGL (needs notebooks 05 and 09, ~10 min)
python -m src.streaming.packs replay --datasets OpenSSH Apache    # needs notebook 13
```

For the live Docker services, first collect normal logs (see [docker/README.md](docker/README.md), steps 1–3),
then:

```bash
python -m src.streaming.packs live                                # one pack per service: PCA, Isolation Forest, LSTM
```

### 2. Start it (one terminal each)

```bash
cd docker && docker compose up -d --build --wait      # web app, database, SSH server and Redis
uvicorn src.streaming.service:app --port 8000         # detection service (from the project root, venv active)
cd dashboard && npm run dev                           # dashboard on http://localhost:3000
```

### 3. Feed it logs

```bash
python -m src.streaming.collector                     # live: new lines from nginx, app, postgres, ssh

python -m src.streaming.replay hdfs --rate 500        # replay a dataset's test set as if it were live
python -m src.streaming.replay bgl --rate 2000 --limit 200000
python -m src.streaming.replay openssh --rate 500
python -m src.streaming.replay apache --rate 200
```

A replay sends the test part (last 30%) of a dataset into the stream at a chosen speed. The detection service
handles it exactly like live logs. This is how we check that streaming gives the same results as offline: on
HDFS, Random Forest reaches F1 0.9985 in both.

### The dashboard

| Page | Shows |
|---|---|
| Overview | logs per minute, active alerts, detection latency, service health, log volume per service |
| Live logs | the stream of incoming lines per source, with lines that belong to an alert highlighted |
| Alerts | every alert with its level, the model that fired, and an explanation (SHAP / top events, missing and never-seen events, the raw log lines) |
| Services | container state from `docker compose ps`, logs per minute, alerts per service, and the status of each pipeline stage |
| Models | offline results per dataset, and the models loaded for each live service |

There are two alert levels. **Alert** means a model flagged the window. **New template** means the only reason
is a log event never seen in normal training.

### Detection service API

| Endpoint | Returns |
|---|---|
| `GET /api/events` | server-sent events: `logs`, `alert`, `stats` |
| `GET /api/logs`, `/api/alerts` | recent lines and alerts, kept per source |
| `GET /api/stats` | counters, average detection latency, loaded packs |
| `GET /api/system` | container state, log volume per minute, pipeline status |
| `GET /api/models`, `/api/packs` | offline results, models loaded per source |

Settings are environment variables: `REDIS_URL`, `HDFS_IDLE_SECONDS`, `STREAM_START=0` (also read lines already
in the stream), `DEDUPE_NEW_TEMPLATES=0` (a New-template warning on every window) and `ALERT_LOG=<file>` (also
write every alert to a JSON-lines file). The dashboard reads `NEXT_PUBLIC_DETECTOR_URL` (default
`http://localhost:8000`).

---

## Fault-injection experiment

With the detection service, the collector and the dashboard running:

```bash
ALERT_LOG=data/processed/fault_alerts.jsonl uvicorn src.streaming.service:app --port 8000
python scripts/inject_faults.py --runs 5        # ~2 hours: 15 faults with 7 minutes of normal traffic between them
```

The script keeps normal traffic running (Locust users and occasional SSH logins) and injects three faults in
rotation:

- stopping the database for 60 s
- adding 300 users for 60 s
- 30 failed SSH logins in 60 s

It records the exact start and end time of each fault in `docs/fault_runs.csv`. Notebook 17 matches these times
with the alert log to compute the detection rate, the latency and the false alerts during normal periods.

---

## Limitations

- **No labels for some data.** OpenSSH, Apache and the live services have none, so for them we can only report
  how much gets flagged and look at examples. The live faults are labelled only because we injected them.
- **Concept drift on BGL.** Models trained on older data flag most newer normal windows. Retraining over time, or
  drift-aware methods, would be needed in practice.
- **Window length sets the latency.** With 1-minute windows, a live fault is detected after about one minute.
  Shorter windows would react faster but give the models less to work with.
- **The live environment is small.** It has four services and synthetic traffic, so its normal behaviour is
  simpler than a production system's.

---

## References

- Zhu, J., He, S., He, P., Liu, J., Lyu, M. R. *Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics.* ISSRE 2023. https://github.com/logpai/loghub
- He, P., Zhu, J., Zheng, Z., Lyu, M. R. *Drain: An Online Log Parsing Approach with Fixed Depth Tree.* ICWS 2017. Implementation: [Drain3](https://github.com/logpai/Drain3)
- Xu, W., Huang, L., Fox, A., Patterson, D., Jordan, M. I. *Detecting Large-Scale System Problems by Mining Console Logs.* SOSP 2009.
- Liu, F. T., Ting, K. M., Zhou, Z.-H. *Isolation Forest.* ICDM 2008.
- Du, M., Li, F., Zheng, G., Srikumar, V. *DeepLog: Anomaly Detection and Diagnosis from System Logs through Deep Learning.* CCS 2017.
- He, S., Zhu, J., He, P., Lyu, M. R. *Experience Report: System Log Analysis for Anomaly Detection.* ISSRE 2016.
- Lundberg, S. M., Lee, S.-I. *A Unified Approach to Interpreting Model Predictions (SHAP).* NeurIPS 2017.
