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
