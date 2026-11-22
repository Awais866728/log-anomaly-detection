# LogSentinel dashboard

Admin dashboard for the log anomaly detection system. All data comes from the detection service
(`src/streaming/service.py`, see the main README); where a value isn't available yet the page shows "no data yet".

```bash
npm install
npm run dev   # http://localhost:3000; detection service at NEXT_PUBLIC_DETECTOR_URL (default http://localhost:8000)
```

| Page | Data |
|---|---|
| Overview | `/api/stats` and `/api/alerts` (live over `/api/events`), services and log volume from `/api/system` |
| Services | `/api/system`: container state from `docker compose ps`, log lines per minute, pipeline status (every 5 s) |
| Alerts, Live logs | `/api/alerts`, `/api/logs` and `/api/events` |
| Models | `/api/models` (docs/cross_system_results.csv) and `/api/packs` (models loaded per service) |

The client code for the service is in `lib/detector.ts`, the shared types in `lib/types.ts`.
